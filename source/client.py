"""Submit a batch and print each result and measured completion time."""
import argparse
import socket
import threading
import time
from common import messages, send


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='10.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--count', type=int, default=6)
    parser.add_argument('--delay', type=float, default=3)
    args = parser.parse_args()
    if not 1 <= args.count <= 100 or not 0 <= args.delay <= 5:
        parser.error('count must be 1-100 and delay must be 0-5 seconds')
    start = time.monotonic()
    with socket.create_connection((args.server, args.port), timeout=10) as sock:
        sock.settimeout(120)
        send(sock, {'type': 'submit', 'numbers': list(range(1, args.count + 1)),
                    'delay': args.delay}, threading.Lock())
        remaining = set()
        successes = failures = 0
        for msg in messages(sock):
            kind = msg.get('type')
            if kind == 'accepted':
                remaining = set(msg['ids'])
                print('Submitted', len(remaining), 'tasks', flush=True)
            elif kind in ('result', 'error'):
                task_id = msg.get('id')
                if task_id is None:
                    raise RuntimeError(msg.get('error', 'request failed'))
                if task_id not in remaining:
                    continue
                remaining.remove(task_id)
                if kind == 'result':
                    successes += 1
                    print('{} squared = {} | worker {} | attempts {}'.format(
                        msg['number'], msg['result'], msg['worker'], msg['attempts']), flush=True)
                else:
                    failures += 1
                    print('Task', task_id, 'failed:', msg.get('error'), flush=True)
                if not remaining:
                    elapsed = time.monotonic() - start
                    print('Completed: {} successful, {} failed; {:.2f} seconds; {:.2f} tasks/sec'.format(
                        successes, failures, elapsed, successes / elapsed), flush=True)
                    return
    raise RuntimeError('Server closed before all results arrived')


if __name__ == '__main__':
    main()
