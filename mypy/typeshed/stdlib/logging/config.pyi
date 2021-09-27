import sys
from _typeshed import StrOrBytesPath, StrPath
from collections.abc import Callable
from configparser import RawConfigParser
from threading import Thread
from typing import IO, Any, Pattern

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if sys.version_info >= (3, 7):
    _Path = StrOrBytesPath
else:
    _Path = StrPath

DEFAULT_LOGGING_CONFIG_PORT: int
RESET_ERROR: int  # undocumented
IDENTIFIER: Pattern[str]  # undocumented

def dictConfig(config: dict[str, Any]) -> None: ...

if sys.version_info >= (3, 10):
    def fileConfig(
        fname: _Path | IO[str] | RawConfigParser,
        defaults: dict[str, str] | None = ...,
        disable_existing_loggers: bool = ...,
        encoding: str | None = ...,
    ) -> None: ...

else:
    def fileConfig(
        fname: _Path | IO[str] | RawConfigParser, defaults: dict[str, str] | None = ..., disable_existing_loggers: bool = ...
    ) -> None: ...

def valid_ident(s: str) -> Literal[True]: ...  # undocumented
def listen(port: int = ..., verify: Callable[[bytes], bytes | None] | None = ...) -> Thread: ...
def stopListening() -> None: ...
