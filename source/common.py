"""Small newline-delimited JSON protocol over TCP."""
import json


def send(sock, message, lock):
    data = (json.dumps(message, separators=(',', ':')) + '\n').encode()
    with lock:
        sock.sendall(data)


def messages(sock):
    # A buffered reader handles partial TCP reads and several messages per read.
    with sock.makefile('r', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)
