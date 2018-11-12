"""Cross platform abstractions for inter-process communication

On Unix, this uses AF_UNIX sockets.
On Windows, this uses NamedPipes.
"""

import contextlib
import json
import os
import shutil
import socket
import sys
import tempfile

from typing import Iterator, Optional, Callable

MYPY = False
if MYPY:
    from typing import Type

from types import TracebackType

if sys.platform == 'win32':
    # This may be private, but it is needed for IPC on Windows, and is basically stable
    import _winapi
    HANDLE = int


class IPCException(Exception):
    """Exception for IPC issues."""
    pass


class IPCBase:
    """Base class for communication between the dmypy client and server.

    This contains logic shared between the client and server, such as reading
    and writing.
    """

    if sys.platform == 'win32':
        connection = None  # type: int
    else:
        connection = None  # type: socket.socket

    def __init__(self, name: str) -> None:
        self.READ_SIZE = 100000
        self.name = name

    def read(self) -> bytes:
        """Read bytes from an IPC connection until its empty."""
        bdata = bytearray()
        while True:
            if sys.platform == 'win32':
                more, _ = _winapi.ReadFile(self.connection, self.READ_SIZE)
            else:
                more = self.connection.recv(self.READ_SIZE)
            if not more:
                break
            bdata.extend(more)
        return bytes(bdata)

    def write(self, data: bytes) -> None:
        """Write bytes to an IPC connection."""
        if sys.platform == 'win32':
            try:
                _winapi.WriteFile(self.connection, data)
                _winapi.WriteFile(self.connection, b'')
            except WindowsError as e:
                raise IPCException("Failed to write with error: {}".format(e.winerror))
        else:
            self.connection.sendall(data)
            self.connection.shutdown(socket.SHUT_WR)

    def close(self) -> None:
        if sys.platform == 'win32':
            if self.connection != _winapi.NULL:
                _winapi.CloseHandle(self.connection)
        else:
            self.connection.close()


class IPCClient(IPCBase):
    """The client side of an IPC connection."""

    def __init__(self, name: str, timeout: Optional[int]) -> None:
        super().__init__(name)
        if sys.platform == 'win32':
            timeout = timeout or 1000  # we need to set a timeout
            while True:
                try:
                    _winapi.WaitNamedPipe(self.name, timeout * 1000)
                except WindowsError as e:
                    if e.winerror == _winapi.ERROR_SEM_TIMEOUT:
                        raise IPCException("Timed out waiting for connection.")
                try:
                    self.connection = _winapi.CreateFile(
                        self.name,
                        _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
                        0,
                        _winapi.NULL,
                        _winapi.OPEN_EXISTING,
                        0,
                        _winapi.NULL,
                    )
                except WindowsError as e:
                    if e.winerror == _winapi.ERROR_PIPE_BUSY:
                        raise IPCException("The connection is busy.")
                else:
                    break
            _winapi.SetNamedPipeHandleState(self.connection,
                                            _winapi.PIPE_READMODE_MESSAGE,
                                            None,
                                            None)
        else:
            self.connection = socket.socket(socket.AF_UNIX)
            self.connection.settimeout(timeout)
            self.connection.connect(name)

    def __enter__(self) -> 'IPCClient':
        return self

    def __exit__(self,
                 exc_ty: 'Optional[Type[BaseException]]' = None,
                 exc_val: Optional[BaseException] = None,
                 exc_tb: Optional[TracebackType] = None,
                 ) -> bool:
        self.close()
        return False


class IPCServer(IPCBase):

    BUFFER_SIZE = 2**16

    def __init__(self, name: str, timeout: Optional[int] = None) -> None:
        super().__init__(name)
        if sys.platform != 'win32':
            self.sock_directory = tempfile.mkdtemp()
            sockfile = os.path.join(self.sock_directory, self.name)
            self.sock = socket.socket(socket.AF_UNIX)
            self.sock.bind(sockfile)
            self.sock.listen(1)
            if timeout is not None:
                self.sock.settimeout(timeout)

    def __enter__(self) -> 'IPCServer':
        if sys.platform == 'win32':
            self.connection = _winapi.CreateNamedPipe(self.name,
                _winapi.PIPE_ACCESS_DUPLEX | _winapi.FILE_FLAG_FIRST_PIPE_INSTANCE,
                _winapi.PIPE_READMODE_MESSAGE | _winapi.PIPE_TYPE_MESSAGE | _winapi.PIPE_WAIT,
                1,  # one instance
                self.BUFFER_SIZE,
                self.BUFFER_SIZE,
                0,  # PIPE_WAIT, wait for a connection of the client
                0,  # PIPE_ACCEPT_REMOTE_CLIENTS (this is the default, so I guess?)
                                                      )
            if self.connection == -1:  # INVALID_HANDLE_VALUE
                err = _winapi.GetLastError()
                raise IPCException('Invalid handle to pipe: {err}'.format(err))
            # NOTE: It is theoretically possible that this will hang forever if the
            # client never connects, though this can be "solved" by killing the server
            _winapi.ConnectNamedPipe(self.connection, _winapi.NULL)
        else:
            while True:
                try:
                    self.connection, _ = self.sock.accept()
                    break
                except socket.timeout:
                    raise IPCException('The socket timed out')
        return self

    def __exit__(self,
                 exc_ty: 'Optional[Type[BaseException]]' = None,
                 exc_val: Optional[BaseException] = None,
                 exc_tb: Optional[TracebackType] = None,
                 ) -> bool:
        self.close()
        return False

    def cleanup(self) -> None:
        if sys.platform != 'win32':
            shutil.rmtree(self.sock_directory)

    @property
    def connection_name(self) -> str:
        if sys.platform == 'win32':
            return self.name
        else:
            return self.sock.getsockname()
