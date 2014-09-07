# Stubs for subprocess

# Based on http://docs.python.org/3.2/library/subprocess.html

from typing import Sequence, Any, Mapping, Undefined, Function, Tuple, IO

# TODO force keyword arguments
# TODO more keyword arguments
def call(args: Sequence[str], *, stdin: Any = None, stdout: Any = None,
         stderr: Any = None, shell: bool = False,
         env: Mapping[str, str] = None) -> int: pass
def check_call(args: Sequence[str], *, stdin: Any = None, stdout: Any = None,
               stderr: Any = None, shell: bool = False,
               env: Mapping[str, str] = None) -> int: pass
# Return str/bytes
def check_output(args: Sequence[str], *, stdin: Any = None, stderr: Any = None,
                 shell: bool = False, universal_newlines: bool = False,
                 env: Mapping[str, str] = None) -> Any: pass

# TODO types
PIPE = Undefined(Any)
STDOUT = Undefined(Any)

class CalledProcessError(Exception):
    returncode = 0
    cmd = ''
    output = b'' # May be None

class Popen:
    stdin = Undefined(IO[Any])
    stdout = Undefined(IO[Any])
    stderr = Undefined(IO[Any])
    pid = 0
    returncode = 0

    def __init__(self,
                  args: Sequence[str],
                  bufsize: int = 0,
                  executable: str = None,
                  stdin: Any = None,
                  stdout: Any = None,
                  stderr: Any = None,
                  preexec_fn: Function[[], Any] = None,
                  close_fds: bool = True,
                  shell: bool = False,
                  cwd: str = None,
                  env: Mapping[str, str] = None,
                  universal_newlines: bool = False,
                  startupinfo: Any = None,
                  creationflags: int = 0,
                  restore_signals: bool = True,
                  start_new_session: bool = False,
                  pass_fds: Any = ()) -> None: pass

    def poll(self) -> int: pass
    def wait(self) -> int: pass
    # Return str/bytes
    def communicate(self, input=None) -> Tuple[Any, Any]: pass
    def send_signal(self, signal: int) -> None: pass
    def terminatate(self) -> None: pass
    def kill(self) -> None: pass
    def __enter__(self) -> 'Popen': pass
    def __exit__(self, type, value, traceback) -> bool: pass

def getstatusoutput(cmd: str) -> Tuple[int, str]: pass
def getoutput(cmd: str) -> str: pass

# Windows-only: STARTUPINFO etc.
