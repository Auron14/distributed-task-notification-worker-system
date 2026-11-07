"""Worker executes simple square tasks, one at a time."""
import argparse
import socket
import threading
import time
from common import messages, send


def run(server, port, bind_ip=None):
    while True:
        try:
            source = (bind_ip, 0) if bind_ip else None
            with socket.create_connection((server, port), timeout=5, source_address=source) as sock:
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
                    for task in messages(sock):
                        if task.get('type') != 'task':
                            continue
                        print('Working on', task['id'], flush=True)
                        time.sleep(task['delay'])
                        send(sock, {'type': 'result', 'id': task['id'],
                                    'attempt': task['attempt'],
                                    'result': task['number'] ** 2}, send_lock)
                finally:
                    stop.set()
        except (OSError, ValueError) as e:
            print('Disconnected:', e, flush=True)
        print('Reconnecting in 2 seconds...', flush=True)
        time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='10.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--bind', help='optional local IP for testing outside Mininet')
    args = parser.parse_args()
    run(args.server, args.port, args.bind)
