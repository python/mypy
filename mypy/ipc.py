"""Cross platform abstractions for inter-process communication

On Unix, this uses AF_UNIX sockets.
On Windows, this uses NamedPipes.

Portions of this file were modified from Python's multiprocess.connection module.
"""

import base64
import os
import sys

from typing import Iterator, Optional, Callable

MYPY = False
if MYPY:
    from typing import Type

from types import TracebackType

from multiprocessing.connection import address_type

if sys.platform == 'win32':
    # This may be private, but it is needed for IPC on Windows, and is basically stable
    import _winapi
    from multiprocessing.connection import PipeListener as Listener
    from multiprocessing.connection import PipeClient as Client
    from multiprocessing.connection import PipeConnection as Connection
else:
    import socket
    from multiprocessing.connection import SocketListener as Listener
    from multiprocessing.connection import SocketClient as Client
    from multiprocessing.connection import Connection


if sys.platform == 'win32':
    CONNECTION_FAMILY = 'AF_PIPE'
else:
    CONNECTION_FAMILY = 'AF_UNIX'


class IPCException(Exception):
    """Exception for IPC issues."""
    pass


class IPCClient:
    """Client side of an IPC connection based on multiprocessing.connection.Client."""

    def __init__(self, address: str, timeout: Optional[int] = None) -> None:
        if sys.platform == 'win32':
            timeout = timeout * 1000 if timeout is not None else _winapi.NMPWAIT_WAIT_FOREVER
            while 1:
                try:
                    _winapi.WaitNamedPipe(address, timeout)
                    h = _winapi.CreateFile(
                        address, _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
                        0, _winapi.NULL, _winapi.OPEN_EXISTING,
                        _winapi.FILE_FLAG_OVERLAPPED, _winapi.NULL
                    )
                except FileNotFoundError:
                    raise IPCException("The NamedPipe at {} was not found.".format(address))
                except WindowsError as e:
                    if e.winerror == _winapi.ERROR_PIPE_BUSY:
                        continue
                    elif e.winerror == _winapi.ERROR_SEM_TIMEOUT:
                        raise IPCException("Timed out waiting for connection.")
                    else:
                        raise
                else:
                    break

            _winapi.SetNamedPipeHandleState(
                h, _winapi.PIPE_READMODE_MESSAGE, None, None
            )
            self.connection = Connection(h)
        else:
            family = address_type(address)
            with socket.socket(getattr(socket, family)) as s:
                if timeout is not None:
                    s.settimeout(timeout)
                s.connect(address)
            self.connection = Connection(s.detach())

    def __enter__(self) -> Connection:
        return self.connection

    def __exit__(self,
                exc_ty: 'Optional[Type[BaseException]]' = None,
                exc_val: Optional[BaseException] = None,
                exc_tb: Optional[TracebackType] = None,
                 ) -> bool:
        self.connection.close()
        return False


class IPCServer(Listener):
    """Server side of an IPC connection based on multiprocessing.connection.Listener."""

    def __init__(self, name: str,
                 timeout: Optional[int] = None
                 ) -> None:
        if sys.platform == 'win32':
            self._name = r'\\.\pipe\{}-{}.pipe'.format(name,
                                                       base64.b64encode(os.urandom(6)).decode())
            super().__init__(self._name, backlog=1)
            self._timeout = timeout * 1000 if timeout else _winapi.INFINITE
        else:
            super().__init__(name, CONNECTION_FAMILY, backlog=1)
            if timeout is not None:
                self._sock.settimeout(timeout)

    def accept(self) -> Connection:
        if sys.platform == 'win32':
            self._handle_queue.append(self._new_handle())
            handle = self._handle_queue.pop(0)
            try:
                ov = _winapi.ConnectNamedPipe(handle, overlapped=True)
            except WindowsError as e:
                if e.winerror != _winapi.ERROR_NO_DATA:
                    raise
                # ERROR_NO_DATA can occur if a client has already connected,
                # written data and then disconnected -- see Python Issue 14725.
            else:
                try:
                    _ = _winapi.WaitForMultipleObjects(
                        [ov.event], True, self._timeout)
                    print(self._timeout)
                except Exception:
                    ov.cancel()
                    _winapi.CloseHandle(handle)
                    raise
                finally:
                    _, err = ov.GetOverlappedResult(False)
                    if err != 0:
                        raise IPCException('Timed out waiting for client to connect.')
            self.connection = Connection(handle)
        else:
            try:
                s, self._last_accepted = self._socket.accept()
            except socket.timeout:
                raise IPCException('Timed out waiting for client to connect.')
            self.connection = Connection(s.detatch())
        return self.connection

    @property
    def connection_name(self) -> str:
        if sys.platform == 'win32':
            return self._name
        else:
            return self._sock.getsockname()

    def __enter__(self) -> Connection:
        return self.accept()

    def __exit__(self,
                 exc_ty: 'Optional[Type[BaseException]]' = None,
                 exc_val: Optional[BaseException] = None,
                 exc_tb: Optional[TracebackType] = None,
                 ) -> bool:
        self.connection.close()
        return False
