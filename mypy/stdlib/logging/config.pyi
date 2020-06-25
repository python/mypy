from _typeshed import AnyPath, StrPath
from typing import Any, Callable, Dict, Optional, IO, Union
from threading import Thread
import sys
if sys.version_info >= (3,):
    from configparser import RawConfigParser
else:
    from ConfigParser import RawConfigParser

if sys.version_info >= (3, 7):
    _Path = AnyPath
else:
    _Path = StrPath


def dictConfig(config: Dict[str, Any]) -> None: ...
if sys.version_info >= (3, 4):
    def fileConfig(fname: Union[_Path, IO[str], RawConfigParser],
                   defaults: Optional[Dict[str, str]] = ...,
                   disable_existing_loggers: bool = ...) -> None: ...
    def listen(port: int = ...,
               verify: Optional[Callable[[bytes], Optional[bytes]]] = ...) -> Thread: ...
else:
    def fileConfig(fname: Union[str, IO[str]],
                   defaults: Optional[Dict[str, str]] = ...,
                   disable_existing_loggers: bool = ...) -> None: ...
    def listen(port: int = ...) -> Thread: ...
def stopListening() -> None: ...
