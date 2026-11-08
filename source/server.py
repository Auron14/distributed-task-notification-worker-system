"""Task server: concurrent clients, worker scheduling, timeouts and recovery."""
import argparse
import json
import os
import socket
import threading
import time
import uuid
from collections import deque

from common import messages, send
from config import (
    SERVER_PORT, WORKER_IPS, LOAD_FILE, WORKER_CAPACITY,
    TASK_TIMEOUT, HEARTBEAT_TIMEOUT, MAX_ATTEMPTS,
    MAX_BATCH_SIZE, MAX_ABS_NUMBER, MAX_TASK_DELAY,
)

lock = threading.RLock()
workers = {}                 # IP -> connection and assigned task IDs
tasks = {}                   # ID -> task details
pending = deque()


def publish_load():
    # Mininet processes and Ryu share the VM filesystem. Atomic replace means
    # the controller never reads a half-written JSON file.
    data = {ip: len(w['jobs']) for ip, w in workers.items()}
    temp = LOAD_FILE + '.tmp'
    try:
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(temp, LOAD_FILE)
    except OSError as e:
        print('Cannot publish SDN load:', e, flush=True)


def reply(task, message):
    try:
        send(task['client'], message, task['client_lock'])
    except OSError:
        pass


def remove_worker(ip, worker, reason):
    # Identity check prevents an old connection from removing a replacement.
    if workers.get(ip) is not worker:
        return
    del workers[ip]
    print('Worker', ip, 'removed:', reason, flush=True)
    for task_id in list(worker['jobs']):
        task = tasks.get(task_id)
        if not task:
            continue
        task['worker'] = None
        if task['attempt'] >= MAX_ATTEMPTS:
            reply(task, {
                'type': 'error', 'id': task_id, 'error': 'retry limit reached'
            })
            del tasks[task_id]
        else:
            pending.appendleft(task_id)
            print('Requeued task', task_id, flush=True)
    publish_load()
    try:
        worker['socket'].shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    worker['socket'].close()


def dispatch():
    # Called while holding lock. Choose the least busy worker.
    while pending:
        available = [
            (len(w['jobs']), ip, w)
            for ip, w in workers.items()
            if len(w['jobs']) < WORKER_CAPACITY
        ]
        if not available:
            return
        _, ip, worker = min(available, key=lambda item: (item[0], item[1]))
        task_id = pending.popleft()
        task = tasks.get(task_id)
        if not task:
            continue
        task['attempt'] += 1
        task['worker'] = ip
        task['started'] = time.monotonic()
        worker['jobs'].add(task_id)
        publish_load()
        try:
            send(worker['socket'], {
                'type': 'task', 'id': task_id,
                'attempt': task['attempt'], 'number': task['number'],
                'delay': task['delay'],
            }, worker['send_lock'])
            print('Assigned', task_id, 'to', ip,
                  'attempt', task['attempt'], flush=True)
        except OSError:
            remove_worker(ip, worker, 'send failed')


def handle_worker(sock, ip, stream):
    if ip not in WORKER_IPS:
        print('Rejected worker from', ip, flush=True)
        return
    worker = {
        'socket': sock,
        'send_lock': threading.Lock(),
        'jobs': set(),
        'last_seen': time.monotonic(),
    }
    with lock:
        if ip in workers:
            remove_worker(ip, workers[ip], 'replaced by new connection')
        workers[ip] = worker
        publish_load()
        print('Registered worker', ip, flush=True)
        dispatch()

    try:
        for msg in stream:
            with lock:
                if workers.get(ip) is not worker:
                    break
                worker['last_seen'] = time.monotonic()
                if msg.get('type') != 'result':
                    continue
                task_id = msg.get('id')
                task = tasks.get(task_id)
                if (not task or task['worker'] != ip or
                        task['attempt'] != msg.get('attempt')):
                    continue  # late result from an obsolete attempt
                worker['jobs'].discard(task_id)
                publish_load()
                reply(task, {
                    'type': 'result', 'id': task_id,
                    'number': task['number'], 'result': msg.get('result'),
                    'worker': ip, 'attempts': task['attempt'],
                })
                del tasks[task_id]
                print('Completed', task_id, 'by', ip, flush=True)
                dispatch()
    finally:
        with lock:
            remove_worker(ip, worker, 'connection closed')
            dispatch()


def handle_client(sock, first):
    numbers = first.get('numbers')
    delay = first.get('delay')
    if (
        not isinstance(numbers, list) or
        not 1 <= len(numbers) <= MAX_BATCH_SIZE or
        any(type(n) is not int or abs(n) > MAX_ABS_NUMBER for n in numbers) or
        type(delay) not in (int, float) or not 0 <= delay <= MAX_TASK_DELAY
    ):
        send(sock, {'type': 'error', 'error': 'Invalid batch'}, threading.Lock())
        return

    client_lock = threading.Lock()
    ids = [uuid.uuid4().hex for _ in numbers]
    send(sock, {'type': 'accepted', 'ids': ids}, client_lock)
    with lock:
        for task_id, number in zip(ids, numbers):
            tasks[task_id] = {
                'number': number, 'delay': delay, 'client': sock,
                'client_lock': client_lock, 'attempt': 0, 'worker': None,
            }
            pending.append(task_id)
        dispatch()

    # Keep this client's socket open until all its tasks have finished.
    while True:
        time.sleep(0.2)
        with lock:
            if not any(task_id in tasks for task_id in ids):
                return


def handle_connection(sock, address):
    try:
        stream = messages(sock)
        first = next(stream, {})
        if first.get('type') == 'register':
            handle_worker(sock, address[0], stream)
        elif first.get('type') == 'submit':
            handle_client(sock, first)
    except (OSError, ValueError, UnicodeError) as e:
        print('Connection ended:', e, flush=True)
    finally:
        sock.close()


def monitor():
    while True:
        time.sleep(1)
        with lock:
            now = time.monotonic()
            for ip, worker in list(workers.items()):
                overdue = any(
                    now - tasks[task_id]['started'] > TASK_TIMEOUT
                    for task_id in worker['jobs'] if task_id in tasks
                )
                if (now - worker['last_seen'] > HEARTBEAT_TIMEOUT or overdue):
                    remove_worker(
                        ip, worker,
                        'task timeout' if overdue else 'heartbeat timeout',
                    )
            dispatch()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=SERVER_PORT)
    args = parser.parse_args()
    publish_load()
    threading.Thread(target=monitor, daemon=True).start()
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', args.port))
        server.listen()
        print('Task server listening on port', args.port, flush=True)
        while True:
            sock, address = server.accept()
            threading.Thread(
                target=handle_connection, args=(sock, address), daemon=True
            ).start()


if __name__ == '__main__':
    main()
