import os
import sys
from unittest import TestCase, main
from multiprocessing import Process

from mypy.ipc import IPCClient, IPCServer, IPCException


if sys.platform == 'win32':
    CONNECTION_NAME = r'\\.\pipe\dmypy-ipc-test-{}.pipe'
else:
    CONNECTION_NAME = 'dmypy-test-ipc-{}.sock'


def server(msg: str, pid: int) -> None:
    with IPCServer(CONNECTION_NAME.format(pid)) as server:
        server.read()
        server.write(msg.encode())
        server.cleanup()


class IPCTests(TestCase):
    def test_transaction_large(self) -> None:
        pid = os.getpid()
        msg = 't' * 100001  # longer than the max read size of 100_000
        p = Process(target=server, args=(msg, pid), daemon=True)
        p.start()
        with IPCClient(CONNECTION_NAME.format(pid), timeout=10) as client:
            client.write(b'')  # signal we are ready for a write from the server
            assert client.read() == msg.encode()
        p.join()


if __name__ == '__main__':
    main()
