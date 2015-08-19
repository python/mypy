# TODO(MichalPokorny): more precise types

from typing import Any, Tuple, Optional

GLOBAL_SSL = ... # type: int
GLOBAL_WIN32 = ... # type: int
GLOBAL_ALL = ... # type: int
GLOBAL_NOTHING = ... # type: int
GLOBAL_DEFAULT = ... # type: int

def global_init(option: int) -> None: ...
def global_cleanup() -> None: ...

version = ... # type: str

def version_info() -> Tuple[int, str, int, str, int, str,
                            int, str, tuple, Any, int, Any]: ...

class error(Exception):
    pass

class Curl(object):
    def close(self) -> None: ...
    def setopt(self, option: int, value: Any) -> None: ...
    def perform(self) -> None: ...
    def getinfo(self, info: Any) -> Any: ...
    def reset(self) -> None: ...
    def unsetopt(self, option: int) -> Any: ...
    def pause(self, bitmask: Any) -> Any: ...
    def errstr(self) -> str: ...

    # TODO(MichalPokorny): wat?
    USERPWD = ... # type: int

class CurlMulti(object):
    def close(self) -> None: ...
    def add_handle(self, obj: Curl) -> None: ...
    def remove_handle(self, obj: Curl) -> None: ...
    def perform(self) -> Tuple[Any, int]: ...
    def fdset(self) -> tuple: ...
    def select(self, timeout: Any = None) -> Any: ...
    def info_read(self, max_objects: int) -> tuple: ...

class CurlShare(object):
    def close(self) -> None: ...
    def setopt(self, option: int, value: Any) -> Any: ...

NOSIGNAL = ... # type: int
NOPROGRESS = ... # type: int
PROGRESSFUNCTION = ... # type: int
READFUNCTION = ... # type: int
CUSTOMREQUEST = ... # type: int
SSL_VERIFYPEER = ... # type: int
SSL_VERIFYHOST = ... # type: int
FOLLOWLOCATION = ... # type: int
INFILESIE_LARGE = ... # type: int
HTTPGET = ... # type: int
NOBODY = ... # type: int
POST = ... # type: int
POSTFIELDS = ... # type: int
POSTFIELDSIZE = ... # type: int
UPLOAD = ... # type: int
INFILESIZE_LARGE = ... # type: int
CAINFO = ... # type: int
SSLCERT = ... # type: int
SSLCERTPASSWD = ... # type: int
SSLKEY = ... # type: int
SSLKEYPASSWD = ... # type: int
TIMEOUT_MS = ... # type: int
HEADERFUNCTION = ... # type: int
CONNECTTIMEOUT_MS = ... # type: int
PROXY = ... # type: int
HTTPHEADER = ... # type: int
URL = ... # type: int
WRITEFUNCTION = ... # type: int
RESPONSE_CODE = ... # type: int

E_OPERATION_TIMEOUTED = ... # type: int
PRIMARY_IP = ... # type: int
