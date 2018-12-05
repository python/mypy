import os
import sys
import time
from unittest import TestCase, main
from multiprocessing import Process, Queue

from mypy.ipc import IPCClient, IPCServer, IPCException


CONNECTION_NAME = 'dmypy-test-ipc.sock'


def server(msg: str, q: 'Queue[str]') -> None:
    server = IPCServer(CONNECTION_NAME)
    q.put(server.connection_name)
    data = b''
    while not data:
        with server as s:
            s.send_bytes(msg.encode())
            data = s.recv_bytes()


class IPCTests(TestCase):
    def test_transaction_large(self) -> None:
        queue = Queue()  # type: Queue[str]
        msg = 't' * 100001  # longer than the max read size of 100_000
        p = Process(target=server, args=(msg, queue), daemon=True)
        p.start()
        connection_name = queue.get()
        with IPCClient(connection_name) as client:
            assert client.recv_bytes() == msg.encode()
            client.send_bytes(b'test')
        queue.close()
        queue.join_thread()
        p.join()

    def test_connect_twice(self) -> None:
        queue = Queue()  # type: Queue[str]
        msg = 'this is a test message'
        p = Process(target=server, args=(msg, queue), daemon=True)
        p.start()
        connection_name = queue.get()
        with IPCClient(connection_name) as client:
            assert client.recv_bytes() == msg.encode()
            client.send_bytes(b'')  # don't let the server hang up yet, we want to connect again.

        with IPCClient(connection_name) as client:
            client.send_bytes(b'test')

        queue.close()
        queue.join_thread()
        p.join()


if __name__ == '__main__':
    main()
