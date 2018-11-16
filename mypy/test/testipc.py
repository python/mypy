import os
import sys
from unittest import TestCase, main
from multiprocessing import Process

from mypy.ipc import IPCClient, IPCServer, IPCException


if sys.platform == 'win32':
    CONNECTION_NAME = r'\\.\pipe\dmypy-ipc-test.pipe'  # type: Final
else:
    CONNECTION_NAME = 'dmypy-test-ipc.sock'  # type: Final


def server(msg: str) -> None:
    with IPCServer(CONNECTION_NAME) as server:
        server.read()
        server.write(msg.encode())
        server.cleanup()


class IPCTests(TestCase):
    def test_transaction_large(self):
        msg = 't' * 100001  # longer than the max read size of 100_000
        p = Process(target=server, args=(msg,))
        p.start()
        with IPCClient(CONNECTION_NAME, timeout=10) as client:
            client.write(b'')  # signal we are ready for a write from the server
            assert client.read() == msg.encode()
        p.join()


if __name__ == '__main__':
    main()
