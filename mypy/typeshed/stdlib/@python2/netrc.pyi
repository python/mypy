from typing import Dict, List, Optional, Text, Tuple

class NetrcParseError(Exception):
    filename: Optional[str]
    lineno: Optional[int]
    msg: str
    def __init__(self, msg: str, filename: Optional[Text] = ..., lineno: Optional[int] = ...) -> None: ...

# (login, account, password) tuple
_NetrcTuple = Tuple[str, Optional[str], Optional[str]]

class netrc:
    hosts: Dict[str, _NetrcTuple]
    macros: Dict[str, List[str]]
    def __init__(self, file: Optional[Text] = ...) -> None: ...
    def authenticators(self, host: str) -> Optional[_NetrcTuple]: ...
