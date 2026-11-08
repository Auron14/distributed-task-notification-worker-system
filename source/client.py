"""Submit a task batch and report results, completion time and throughput."""
import argparse
import socket
import threading
import time

from common import messages, send
from config import (
    SERVER_IP, SERVER_PORT, MAX_BATCH_SIZE, DEFAULT_TASK_DELAY,
    MAX_TASK_DELAY, CLIENT_RESPONSE_TIMEOUT,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default=SERVER_IP)
    parser.add_argument('--port', type=int, default=SERVER_PORT)
    parser.add_argument('--count', type=int, default=6)
    parser.add_argument('--delay', type=float, default=DEFAULT_TASK_DELAY)
    parser.add_argument('--client-name', default='client',
                        help='label shown in this client\'s output')
    args = parser.parse_args()

    if not 1 <= args.count <= MAX_BATCH_SIZE or not 0 <= args.delay <= MAX_TASK_DELAY:
        parser.error(
            'count must be 1-{} and delay must be between 0 and {} seconds'.format(
                MAX_BATCH_SIZE, MAX_TASK_DELAY
            )
        )

    label = '[{}]'.format(args.client_name)
    start = time.monotonic()
    with socket.create_connection((args.server, args.port), timeout=10) as sock:
        sock.settimeout(CLIENT_RESPONSE_TIMEOUT)
        send(sock, {
            'type': 'submit',
            'numbers': list(range(1, args.count + 1)),
            'delay': args.delay,
        }, threading.Lock())

        remaining = set()
        successes = failures = 0
        for msg in messages(sock):
            kind = msg.get('type')
            if kind == 'accepted':
                remaining = set(msg['ids'])
                print(label, 'Submitted', len(remaining), 'tasks', flush=True)
            elif kind in ('result', 'error'):
                task_id = msg.get('id')
                if task_id is None:
                    raise RuntimeError(msg.get('error', 'request failed'))
                if task_id not in remaining:
                    continue
                remaining.remove(task_id)
                if kind == 'result':
                    successes += 1
                    print(
                        '{} {} squared = {} | worker {} | attempts {}'.format(
                            label, msg['number'], msg['result'],
                            msg['worker'], msg['attempts'],
                        ), flush=True,
                    )
                else:
                    failures += 1
                    print(label, 'Task', task_id, 'failed:',
                          msg.get('error'), flush=True)

                if not remaining:
                    elapsed = time.monotonic() - start
                    throughput = successes / elapsed if elapsed > 0 else 0.0
                    print(
                        '{} Completed: {} successful, {} failed; '
                        '{:.2f} seconds; {:.2f} successful tasks/sec'.format(
                            label, successes, failures, elapsed, throughput,
                        ), flush=True,
                    )
                    return

    raise RuntimeError('Server closed before all results arrived')


if __name__ == '__main__':
    main()
