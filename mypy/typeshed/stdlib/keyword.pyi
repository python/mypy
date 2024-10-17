import sys
from collections.abc import Sequence

if sys.version_info >= (3, 9):
    __all__ = ["iskeyword", "issoftkeyword", "kwlist", "softkwlist"]
else:
    __all__ = ["iskeyword", "kwlist"]

def iskeyword(s: str) -> bool: ...

kwlist: Sequence[str]

if sys.version_info >= (3, 9):
    def issoftkeyword(s: str) -> bool: ...
    softkwlist: Sequence[str]
