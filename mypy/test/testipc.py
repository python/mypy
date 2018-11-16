import os
import sys
import time
from unittest import TestCase, main
from multiprocessing import Process, Queue

from mypy.ipc import IPCClient, IPCServer, IPCException


if sys.platform == 'win32':
    CONNECTION_NAME = r'\\.\pipe\dmypy-ipc-test-{}.pipe'
else:
    CONNECTION_NAME = 'dmypy-test-ipc-{}.sock'


def server(msg: str, q: 'Queue[str]') -> None:
    server = IPCServer(CONNECTION_NAME.format(os.getpid()))
    q.put(server.connection_name)
    with server:
        server.write(msg.encode())
    server.cleanup()


class IPCTests(TestCase):
    def test_transaction_large(self) -> None:
        queue = Queue()  # type: Queue[str]
        msg = 't' * 100001  # longer than the max read size of 100_000
        p = Process(target=server, args=(msg, queue), daemon=True)
        p.start()
        connection_name = queue.get()
        with IPCClient(connection_name, timeout=10) as client:
            assert client.read() == msg.encode()
        queue.close()
        queue.join_thread()
        p.join()


if __name__ == '__main__':
    main()
