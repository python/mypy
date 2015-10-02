# Stubs for subprocess

# Based on http://docs.python.org/3.2/library/subprocess.html

from typing import Sequence, Any, Mapping, Callable, Tuple, IO

# TODO force keyword arguments
# TODO more keyword arguments
def call(args: Sequence[str], *, stdin: Any = None, stdout: Any = None,
         stderr: Any = None, shell: bool = False,
         env: Mapping[str, str] = None,
         cwd: str = None) -> int: ...
def check_call(args: Sequence[str], *, stdin: Any = None, stdout: Any = None,
               stderr: Any = None, shell: bool = False,
               env: Mapping[str, str] = None,
               cwd: str = None) -> int: ...
# Return str/bytes
def check_output(args: Sequence[str], *, stdin: Any = None, stderr: Any = None,
                 shell: bool = False, universal_newlines: bool = False,
                 env: Mapping[str, str] = None,
                 cwd: str = None) -> Any: ...

# TODO types
PIPE = ... # type: Any
STDOUT = ... # type: Any

class CalledProcessError(Exception):
    returncode = 0
    cmd = ''
    output = b'' # May be None

    def __init__(self, returncode: int, cmd: str, output: str) -> None: ...

class Popen:
    stdin = ... # type: IO[Any]
    stdout = ... # type: IO[Any]
    stderr = ... # type: IO[Any]
    pid = 0
    returncode = 0

    def __init__(self,
                  args: Sequence[str],
                  bufsize: int = 0,
                  executable: str = None,
                  stdin: Any = None,
                  stdout: Any = None,
                  stderr: Any = None,
                  preexec_fn: Callable[[], Any] = None,
                  close_fds: bool = True,
                  shell: bool = False,
                  cwd: str = None,
                  env: Mapping[str, str] = None,
                  universal_newlines: bool = False,
                  startupinfo: Any = None,
                  creationflags: int = 0,
                  restore_signals: bool = True,
                  start_new_session: bool = False,
                  pass_fds: Any = ()) -> None: ...

    def poll(self) -> int: ...
    def wait(self) -> int: ...
    # Return str/bytes
    def communicate(self, input=None) -> Tuple[Any, Any]: ...
    def send_signal(self, signal: int) -> None: ...
    def terminatate(self) -> None: ...
    def kill(self) -> None: ...
    def __enter__(self) -> 'Popen': ...
    def __exit__(self, type, value, traceback) -> bool: ...

def getstatusoutput(cmd: str) -> Tuple[int, str]: ...
def getoutput(cmd: str) -> str: ...

# Windows-only: STARTUPINFO etc.
