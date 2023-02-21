import subprocess
import sys
from _typeshed import StrOrBytesPath
from asyncio import events, protocols, streams, transports
from collections.abc import Callable, Collection
from typing import IO, Any
from typing_extensions import Literal, TypeAlias

__all__ = ("create_subprocess_exec", "create_subprocess_shell")

if sys.version_info >= (3, 8):
    _ExecArg: TypeAlias = StrOrBytesPath
else:
    _ExecArg: TypeAlias = str | bytes

PIPE: int
STDOUT: int
DEVNULL: int

class SubprocessStreamProtocol(streams.FlowControlMixin, protocols.SubprocessProtocol):
    stdin: streams.StreamWriter | None
    stdout: streams.StreamReader | None
    stderr: streams.StreamReader | None
    def __init__(self, limit: int, loop: events.AbstractEventLoop) -> None: ...
    def pipe_data_received(self, fd: int, data: bytes | str) -> None: ...

class Process:
    stdin: streams.StreamWriter | None
    stdout: streams.StreamReader | None
    stderr: streams.StreamReader | None
    pid: int
    def __init__(
        self, transport: transports.BaseTransport, protocol: protocols.BaseProtocol, loop: events.AbstractEventLoop
    ) -> None: ...
    @property
    def returncode(self) -> int | None: ...
    async def wait(self) -> int: ...
    def send_signal(self, signal: int) -> None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    async def communicate(self, input: bytes | bytearray | memoryview | None = None) -> tuple[bytes, bytes]: ...

if sys.version_info >= (3, 11):
    async def create_subprocess_shell(
        cmd: str | bytes,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        limit: int = 65536,
        *,
        # These parameters are forced to these values by BaseEventLoop.subprocess_shell
        universal_newlines: Literal[False] = False,
        shell: Literal[True] = True,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        text: Literal[False, None] = ...,
        # These parameters are taken by subprocess.Popen, which this ultimately delegates to
        executable: StrOrBytesPath | None = ...,
        preexec_fn: Callable[[], Any] | None = ...,
        close_fds: bool = ...,
        cwd: StrOrBytesPath | None = ...,
        env: subprocess._ENV | None = ...,
        startupinfo: Any | None = ...,
        creationflags: int = ...,
        restore_signals: bool = ...,
        start_new_session: bool = ...,
        pass_fds: Collection[int] = ...,
        group: None | str | int = ...,
        extra_groups: None | Collection[str | int] = ...,
        user: None | str | int = ...,
        umask: int = ...,
        process_group: int | None = ...,
        pipesize: int = ...,
    ) -> Process: ...
    async def create_subprocess_exec(
        program: _ExecArg,
        *args: _ExecArg,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        limit: int = 65536,
        # These parameters are forced to these values by BaseEventLoop.subprocess_shell
        universal_newlines: Literal[False] = False,
        shell: Literal[True] = True,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        # These parameters are taken by subprocess.Popen, which this ultimately delegates to
        text: bool | None = ...,
        executable: StrOrBytesPath | None = ...,
        preexec_fn: Callable[[], Any] | None = ...,
        close_fds: bool = ...,
        cwd: StrOrBytesPath | None = ...,
        env: subprocess._ENV | None = ...,
        startupinfo: Any | None = ...,
        creationflags: int = ...,
        restore_signals: bool = ...,
        start_new_session: bool = ...,
        pass_fds: Collection[int] = ...,
        group: None | str | int = ...,
        extra_groups: None | Collection[str | int] = ...,
        user: None | str | int = ...,
        umask: int = ...,
        process_group: int | None = ...,
        pipesize: int = ...,
    ) -> Process: ...

elif sys.version_info >= (3, 10):
    async def create_subprocess_shell(
        cmd: str | bytes,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        limit: int = 65536,
        *,
        # These parameters are forced to these values by BaseEventLoop.subprocess_shell
        universal_newlines: Literal[False] = False,
        shell: Literal[True] = True,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        text: Literal[False, None] = ...,
        # These parameters are taken by subprocess.Popen, which this ultimately delegates to
        executable: StrOrBytesPath | None = ...,
        preexec_fn: Callable[[], Any] | None = ...,
        close_fds: bool = ...,
        cwd: StrOrBytesPath | None = ...,
        env: subprocess._ENV | None = ...,
        startupinfo: Any | None = ...,
        creationflags: int = ...,
        restore_signals: bool = ...,
        start_new_session: bool = ...,
        pass_fds: Collection[int] = ...,
        group: None | str | int = ...,
        extra_groups: None | Collection[str | int] = ...,
        user: None | str | int = ...,
        umask: int = ...,
        pipesize: int = ...,
    ) -> Process: ...
    async def create_subprocess_exec(
        program: _ExecArg,
        *args: _ExecArg,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        limit: int = 65536,
        # These parameters are forced to these values by BaseEventLoop.subprocess_shell
        universal_newlines: Literal[False] = False,
        shell: Literal[True] = True,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        # These parameters are taken by subprocess.Popen, which this ultimately delegates to
        text: bool | None = ...,
        executable: StrOrBytesPath | None = ...,
        preexec_fn: Callable[[], Any] | None = ...,
        close_fds: bool = ...,
        cwd: StrOrBytesPath | None = ...,
        env: subprocess._ENV | None = ...,
        startupinfo: Any | None = ...,
        creationflags: int = ...,
        restore_signals: bool = ...,
        start_new_session: bool = ...,
        pass_fds: Collection[int] = ...,
        group: None | str | int = ...,
        extra_groups: None | Collection[str | int] = ...,
        user: None | str | int = ...,
        umask: int = ...,
        pipesize: int = ...,
    ) -> Process: ...

else:  # >= 3.9
    async def create_subprocess_shell(
        cmd: str | bytes,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        loop: events.AbstractEventLoop | None = None,
        limit: int = 65536,
        *,
        # These parameters are forced to these values by BaseEventLoop.subprocess_shell
        universal_newlines: Literal[False] = False,
        shell: Literal[True] = True,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        text: Literal[False, None] = ...,
        # These parameters are taken by subprocess.Popen, which this ultimately delegates to
        executable: StrOrBytesPath | None = ...,
        preexec_fn: Callable[[], Any] | None = ...,
        close_fds: bool = ...,
        cwd: StrOrBytesPath | None = ...,
        env: subprocess._ENV | None = ...,
        startupinfo: Any | None = ...,
        creationflags: int = ...,
        restore_signals: bool = ...,
        start_new_session: bool = ...,
        pass_fds: Collection[int] = ...,
        group: None | str | int = ...,
        extra_groups: None | Collection[str | int] = ...,
        user: None | str | int = ...,
        umask: int = ...,
    ) -> Process: ...
    async def create_subprocess_exec(
        program: _ExecArg,
        *args: _ExecArg,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        loop: events.AbstractEventLoop | None = None,
        limit: int = 65536,
        # These parameters are forced to these values by BaseEventLoop.subprocess_shell
        universal_newlines: Literal[False] = False,
        shell: Literal[True] = True,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        # These parameters are taken by subprocess.Popen, which this ultimately delegates to
        text: bool | None = ...,
        executable: StrOrBytesPath | None = ...,
        preexec_fn: Callable[[], Any] | None = ...,
        close_fds: bool = ...,
        cwd: StrOrBytesPath | None = ...,
        env: subprocess._ENV | None = ...,
        startupinfo: Any | None = ...,
        creationflags: int = ...,
        restore_signals: bool = ...,
        start_new_session: bool = ...,
        pass_fds: Collection[int] = ...,
        group: None | str | int = ...,
        extra_groups: None | Collection[str | int] = ...,
        user: None | str | int = ...,
        umask: int = ...,
    ) -> Process: ...
