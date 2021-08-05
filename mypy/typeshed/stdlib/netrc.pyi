from _typeshed import StrOrBytesPath
from typing import Dict, List, Optional, Tuple

class NetrcParseError(Exception):
    filename: Optional[str]
    lineno: Optional[int]
    msg: str
    def __init__(self, msg: str, filename: Optional[StrOrBytesPath] = ..., lineno: Optional[int] = ...) -> None: ...

# (login, account, password) tuple
_NetrcTuple = Tuple[str, Optional[str], Optional[str]]

class netrc:
    hosts: Dict[str, _NetrcTuple]
    macros: Dict[str, List[str]]
    def __init__(self, file: Optional[StrOrBytesPath] = ...) -> None: ...
    def authenticators(self, host: str) -> Optional[_NetrcTuple]: ...
