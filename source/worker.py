"""Worker executes up to the configured number of tasks concurrently."""
import argparse
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from common import messages, send
from config import (
    SERVER_IP, SERVER_PORT, WORKER_PARALLELISM,
)


def process_task(sock, send_lock, task):
    """Simulate task work, calculate the result and return it to the server."""
    try:
        time.sleep(task['delay'])
        result = task['number'] ** 2
        send(sock, {
            'type': 'result',
            'id': task['id'],
            'attempt': task['attempt'],
            'result': result,
        }, send_lock)
        print('Completed', task['id'], flush=True)
    except OSError as e:
        # The server may have disconnected while this task was running.
        print('Could not return result for {}: {}'.format(task.get('id'), e),
              flush=True)


def run(server, port, bind_ip=None):
    while True:
        try:
            source = (bind_ip, 0) if bind_ip else None
            with socket.create_connection(
                (server, port), timeout=5, source_address=source
            ) as sock:
                sock.settimeout(None)
                send_lock = threading.Lock()
                stop = threading.Event()
                send(sock, {'type': 'register'}, send_lock)
                print('Connected to server', flush=True)

                def heartbeat():
                    while not stop.wait(2):
                        try:
                            send(sock, {'type': 'heartbeat'}, send_lock)
                        except OSError:
                            return

                threading.Thread(target=heartbeat, daemon=True).start()
                try:
                    # Server capacity is also 2, so each worker can execute
                    # both assigned tasks concurrently rather than queueing
                    # the second task behind the first one.
                    with ThreadPoolExecutor(
                        max_workers=WORKER_PARALLELISM,
                        thread_name_prefix='worker-task',
                    ) as executor:
                        for task in messages(sock):
                            if task.get('type') == 'task':
                                print('Working on', task['id'], flush=True)
                                executor.submit(process_task, sock, send_lock, task)
                finally:
                    stop.set()
        except (OSError, ValueError) as e:
            print('Disconnected:', e, flush=True)
        print('Reconnecting in 2 seconds...', flush=True)
        time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default=SERVER_IP)
    parser.add_argument('--port', type=int, default=SERVER_PORT)
    parser.add_argument('--bind', help='local worker IP; useful for Mininet')
    args = parser.parse_args()
    run(args.server, args.port, args.bind)
