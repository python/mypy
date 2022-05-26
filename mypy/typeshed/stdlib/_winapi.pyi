import sys
from collections.abc import Sequence
from typing import Any, NoReturn, overload
from typing_extensions import Literal, final

if sys.platform == "win32":
    if sys.version_info >= (3, 7):
        ABOVE_NORMAL_PRIORITY_CLASS: Literal[32768]
        BELOW_NORMAL_PRIORITY_CLASS: Literal[16384]
        CREATE_BREAKAWAY_FROM_JOB: Literal[16777216]
        CREATE_DEFAULT_ERROR_MODE: Literal[67108864]
        CREATE_NO_WINDOW: Literal[134217728]
    CREATE_NEW_CONSOLE: Literal[16]
    CREATE_NEW_PROCESS_GROUP: Literal[512]
    if sys.version_info >= (3, 7):
        DETACHED_PROCESS: Literal[8]
    DUPLICATE_CLOSE_SOURCE: Literal[1]
    DUPLICATE_SAME_ACCESS: Literal[2]

    ERROR_ALREADY_EXISTS: Literal[183]
    ERROR_BROKEN_PIPE: Literal[109]
    ERROR_IO_PENDING: Literal[997]
    ERROR_MORE_DATA: Literal[234]
    ERROR_NETNAME_DELETED: Literal[64]
    ERROR_NO_DATA: Literal[232]
    ERROR_NO_SYSTEM_RESOURCES: Literal[1450]
    ERROR_OPERATION_ABORTED: Literal[995]
    ERROR_PIPE_BUSY: Literal[231]
    ERROR_PIPE_CONNECTED: Literal[535]
    ERROR_SEM_TIMEOUT: Literal[121]

    FILE_FLAG_FIRST_PIPE_INSTANCE: Literal[524288]
    FILE_FLAG_OVERLAPPED: Literal[1073741824]
    FILE_GENERIC_READ: Literal[1179785]
    FILE_GENERIC_WRITE: Literal[1179926]
    if sys.version_info >= (3, 8):
        FILE_MAP_ALL_ACCESS: Literal[983071]
        FILE_MAP_COPY: Literal[1]
        FILE_MAP_EXECUTE: Literal[32]
        FILE_MAP_READ: Literal[4]
        FILE_MAP_WRITE: Literal[2]
    if sys.version_info >= (3, 7):
        FILE_TYPE_CHAR: Literal[2]
        FILE_TYPE_DISK: Literal[1]
        FILE_TYPE_PIPE: Literal[3]
        FILE_TYPE_REMOTE: Literal[32768]
        FILE_TYPE_UNKNOWN: Literal[0]

    GENERIC_READ: Literal[2147483648]
    GENERIC_WRITE: Literal[1073741824]
    if sys.version_info >= (3, 7):
        HIGH_PRIORITY_CLASS: Literal[128]
    INFINITE: Literal[4294967295]
    if sys.version_info >= (3, 8):
        INVALID_HANDLE_VALUE: int  # very large number
    if sys.version_info >= (3, 7):
        IDLE_PRIORITY_CLASS: Literal[64]
        NORMAL_PRIORITY_CLASS: Literal[32]
        REALTIME_PRIORITY_CLASS: Literal[256]
    NMPWAIT_WAIT_FOREVER: Literal[4294967295]

    if sys.version_info >= (3, 8):
        MEM_COMMIT: Literal[4096]
        MEM_FREE: Literal[65536]
        MEM_IMAGE: Literal[16777216]
        MEM_MAPPED: Literal[262144]
        MEM_PRIVATE: Literal[131072]
        MEM_RESERVE: Literal[8192]

    NULL: Literal[0]
    OPEN_EXISTING: Literal[3]

    PIPE_ACCESS_DUPLEX: Literal[3]
    PIPE_ACCESS_INBOUND: Literal[1]
    PIPE_READMODE_MESSAGE: Literal[2]
    PIPE_TYPE_MESSAGE: Literal[4]
    PIPE_UNLIMITED_INSTANCES: Literal[255]
    PIPE_WAIT: Literal[0]
    if sys.version_info >= (3, 8):
        PAGE_EXECUTE: Literal[16]
        PAGE_EXECUTE_READ: Literal[32]
        PAGE_EXECUTE_READWRITE: Literal[64]
        PAGE_EXECUTE_WRITECOPY: Literal[128]
        PAGE_GUARD: Literal[256]
        PAGE_NOACCESS: Literal[1]
        PAGE_NOCACHE: Literal[512]
        PAGE_READONLY: Literal[2]
        PAGE_READWRITE: Literal[4]
        PAGE_WRITECOMBINE: Literal[1024]
        PAGE_WRITECOPY: Literal[8]

    PROCESS_ALL_ACCESS: Literal[2097151]
    PROCESS_DUP_HANDLE: Literal[64]
    if sys.version_info >= (3, 8):
        SEC_COMMIT: Literal[134217728]
        SEC_IMAGE: Literal[16777216]
        SEC_LARGE_PAGES: Literal[2147483648]
        SEC_NOCACHE: Literal[268435456]
        SEC_RESERVE: Literal[67108864]
        SEC_WRITECOMBINE: Literal[1073741824]
    STARTF_USESHOWWINDOW: Literal[1]
    STARTF_USESTDHANDLES: Literal[256]
    STD_ERROR_HANDLE: Literal[4294967284]
    STD_INPUT_HANDLE: Literal[4294967286]
    STD_OUTPUT_HANDLE: Literal[4294967285]
    STILL_ACTIVE: Literal[259]
    SW_HIDE: Literal[0]
    if sys.version_info >= (3, 8):
        SYNCHRONIZE: Literal[1048576]
    WAIT_ABANDONED_0: Literal[128]
    WAIT_OBJECT_0: Literal[0]
    WAIT_TIMEOUT: Literal[258]
    def CloseHandle(__handle: int) -> None: ...
    @overload
    def ConnectNamedPipe(handle: int, overlapped: Literal[True]) -> Overlapped: ...
    @overload
    def ConnectNamedPipe(handle: int, overlapped: Literal[False] = ...) -> None: ...
    @overload
    def ConnectNamedPipe(handle: int, overlapped: bool) -> Overlapped | None: ...
    def CreateFile(
        __file_name: str,
        __desired_access: int,
        __share_mode: int,
        __security_attributes: int,
        __creation_disposition: int,
        __flags_and_attributes: int,
        __template_file: int,
    ) -> int: ...
    def CreateJunction(__src_path: str, __dst_path: str) -> None: ...
    def CreateNamedPipe(
        __name: str,
        __open_mode: int,
        __pipe_mode: int,
        __max_instances: int,
        __out_buffer_size: int,
        __in_buffer_size: int,
        __default_timeout: int,
        __security_attributes: int,
    ) -> int: ...
    def CreatePipe(__pipe_attrs: Any, __size: int) -> tuple[int, int]: ...
    def CreateProcess(
        __application_name: str | None,
        __command_line: str | None,
        __proc_attrs: Any,
        __thread_attrs: Any,
        __inherit_handles: bool,
        __creation_flags: int,
        __env_mapping: dict[str, str],
        __current_directory: str | None,
        __startup_info: Any,
    ) -> tuple[int, int, int, int]: ...
    def DuplicateHandle(
        __source_process_handle: int,
        __source_handle: int,
        __target_process_handle: int,
        __desired_access: int,
        __inherit_handle: bool,
        __options: int = ...,
    ) -> int: ...
    def ExitProcess(__ExitCode: int) -> NoReturn: ...
    if sys.version_info >= (3, 7):
        def GetACP() -> int: ...
        def GetFileType(handle: int) -> int: ...

    def GetCurrentProcess() -> int: ...
    def GetExitCodeProcess(__process: int) -> int: ...
    def GetLastError() -> int: ...
    def GetModuleFileName(__module_handle: int) -> str: ...
    def GetStdHandle(__std_handle: int) -> int: ...
    def GetVersion() -> int: ...
    def OpenProcess(__desired_access: int, __inherit_handle: bool, __process_id: int) -> int: ...
    def PeekNamedPipe(__handle: int, __size: int = ...) -> tuple[int, int] | tuple[bytes, int, int]: ...
    @overload
    def ReadFile(handle: int, size: int, overlapped: Literal[True]) -> tuple[Overlapped, int]: ...
    @overload
    def ReadFile(handle: int, size: int, overlapped: Literal[False] = ...) -> tuple[bytes, int]: ...
    @overload
    def ReadFile(handle: int, size: int, overlapped: int | bool) -> tuple[Any, int]: ...
    def SetNamedPipeHandleState(
        __named_pipe: int, __mode: int | None, __max_collection_count: int | None, __collect_data_timeout: int | None
    ) -> None: ...
    def TerminateProcess(__handle: int, __exit_code: int) -> None: ...
    def WaitForMultipleObjects(__handle_seq: Sequence[int], __wait_flag: bool, __milliseconds: int = ...) -> int: ...
    def WaitForSingleObject(__handle: int, __milliseconds: int) -> int: ...
    def WaitNamedPipe(__name: str, __timeout: int) -> None: ...
    @overload
    def WriteFile(handle: int, buffer: bytes, overlapped: Literal[True]) -> tuple[Overlapped, int]: ...
    @overload
    def WriteFile(handle: int, buffer: bytes, overlapped: Literal[False] = ...) -> tuple[int, int]: ...
    @overload
    def WriteFile(handle: int, buffer: bytes, overlapped: int | bool) -> tuple[Any, int]: ...
    @final
    class Overlapped:
        event: int
        def GetOverlappedResult(self, __wait: bool) -> tuple[int, int]: ...
        def cancel(self) -> None: ...
        def getbuffer(self) -> bytes | None: ...
