from typing import Optional, Text

class NetrcParseError(Exception):
    filename: str | None
    lineno: int | None
    msg: str
    def __init__(self, msg: str, filename: Text | None = ..., lineno: int | None = ...) -> None: ...

# (login, account, password) tuple
_NetrcTuple = tuple[str, Optional[str], Optional[str]]

class netrc:
    hosts: dict[str, _NetrcTuple]
    macros: dict[str, list[str]]
    def __init__(self, file: Text | None = ...) -> None: ...
    def authenticators(self, host: str) -> _NetrcTuple | None: ...
