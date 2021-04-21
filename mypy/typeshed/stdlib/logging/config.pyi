import sys
from _typeshed import AnyPath, StrPath
from collections.abc import Callable
from configparser import RawConfigParser
from threading import Thread
from typing import IO, Any, Optional, Union

if sys.version_info >= (3, 7):
    _Path = AnyPath
else:
    _Path = StrPath

def dictConfig(config: dict[str, Any]) -> None: ...
def fileConfig(
    fname: Union[_Path, IO[str], RawConfigParser],
    defaults: Optional[dict[str, str]] = ...,
    disable_existing_loggers: bool = ...,
) -> None: ...
def listen(port: int = ..., verify: Optional[Callable[[bytes], Optional[bytes]]] = ...) -> Thread: ...
def stopListening() -> None: ...
