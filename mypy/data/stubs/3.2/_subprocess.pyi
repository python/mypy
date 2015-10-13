# Stubs for _subprocess

# NOTE: These are incomplete!

from typing import Mapping, Any, Tuple

CREATE_NEW_CONSOLE = 0
CREATE_NEW_PROCESS_GROUP = 0
STD_INPUT_HANDLE = 0
STD_OUTPUT_HANDLE = 0
STD_ERROR_HANDLE = 0
SW_HIDE = 0
STARTF_USESTDHANDLES = 0
STARTF_USESHOWWINDOW = 0
INFINITE = 0
DUPLICATE_SAME_ACCESS = 0
WAIT_OBJECT_0 = 0

# TODO not exported by the Python module
class Handle:
    def Close(self) -> None: ...

def GetVersion() -> int: ...
def GetExitCodeProcess(handle: Handle) -> int: ...
def WaitForSingleObject(handle: Handle, timeout: int) -> int: ...
def CreateProcess(executable: str, cmd_line: str,
                  proc_attrs, thread_attrs,
                  inherit: int, flags: int,
                  env_mapping: Mapping[str, str],
                  curdir: str,
                  startupinfo: Any) -> Tuple[Any, Handle, int, int]: ...
def GetModuleFileName(module: int) -> str: ...
def GetCurrentProcess() -> Handle: ...
def DuplicateHandle(source_proc: Handle, source: Handle, target_proc: Handle,
                    target: Any, access: int, inherit: int) -> int: ...
def CreatePipe(pipe_attrs, size: int) -> Tuple[Handle, Handle]: ...
def GetStdHandle(arg: int) -> int: ...
def TerminateProcess(handle: Handle, exit_code: int) -> None: ...
