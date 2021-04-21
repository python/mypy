import sys
import threading
from _typeshed import StrPath, SupportsWrite
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from string import Template
from time import struct_time
from types import FrameType, TracebackType
from typing import IO, Any, ClassVar, Optional, Tuple, Type, Union

_SysExcInfoType = Union[Tuple[type, BaseException, Optional[TracebackType]], Tuple[None, None, None]]
_ExcInfoType = Union[None, bool, _SysExcInfoType, BaseException]
_ArgsType = Union[Tuple[Any, ...], Mapping[str, Any]]
_FilterType = Union[Filter, Callable[[LogRecord], int]]
_Level = Union[int, str]

raiseExceptions: bool
logThreads: bool
logMultiprocessing: bool
logProcesses: bool
_srcfile: Optional[str]

def currentframe() -> FrameType: ...

_levelToName: dict[int, str]
_nameToLevel: dict[str, int]

class Filterer(object):
    filters: list[Filter]
    def __init__(self) -> None: ...
    def addFilter(self, filter: _FilterType) -> None: ...
    def removeFilter(self, filter: _FilterType) -> None: ...
    def filter(self, record: LogRecord) -> bool: ...

class Manager(object):
    root: RootLogger
    disable: int
    emittedNoHandlerWarning: bool
    loggerDict: dict[str, Union[Logger, PlaceHolder]]
    loggerClass: Optional[Type[Logger]]
    logRecordFactory: Optional[Callable[..., LogRecord]]
    def __init__(self, rootnode: RootLogger) -> None: ...
    def getLogger(self, name: str) -> Logger: ...
    def setLoggerClass(self, klass: Type[Logger]) -> None: ...
    def setLogRecordFactory(self, factory: Callable[..., LogRecord]) -> None: ...

class Logger(Filterer):
    name: str
    level: int
    parent: Union[Logger, PlaceHolder]
    propagate: bool
    handlers: list[Handler]
    disabled: int
    root: ClassVar[RootLogger]  # undocumented
    manager: ClassVar[Manager]  # undocumented
    def __init__(self, name: str, level: _Level = ...) -> None: ...
    def setLevel(self, level: _Level) -> None: ...
    def isEnabledFor(self, level: int) -> bool: ...
    def getEffectiveLevel(self) -> int: ...
    def getChild(self, suffix: str) -> Logger: ...
    if sys.version_info >= (3, 8):
        def debug(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def info(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warning(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warn(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def error(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def exception(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def critical(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def log(
            self,
            level: int,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def _log(
            self,
            level: int,
            msg: Any,
            args: _ArgsType,
            exc_info: Optional[_ExcInfoType] = ...,
            extra: Optional[dict[str, Any]] = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
        ) -> None: ...  # undocumented
    else:
        def debug(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def info(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warning(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warn(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def error(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def critical(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        fatal = critical
        def log(
            self,
            level: int,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def exception(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def _log(
            self,
            level: int,
            msg: Any,
            args: _ArgsType,
            exc_info: Optional[_ExcInfoType] = ...,
            extra: Optional[dict[str, Any]] = ...,
            stack_info: bool = ...,
        ) -> None: ...  # undocumented
    def filter(self, record: LogRecord) -> bool: ...
    def addHandler(self, hdlr: Handler) -> None: ...
    def removeHandler(self, hdlr: Handler) -> None: ...
    if sys.version_info >= (3, 8):
        def findCaller(self, stack_info: bool = ..., stacklevel: int = ...) -> tuple[str, int, str, Optional[str]]: ...
    else:
        def findCaller(self, stack_info: bool = ...) -> tuple[str, int, str, Optional[str]]: ...
    def handle(self, record: LogRecord) -> None: ...
    def makeRecord(
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: Any,
        args: _ArgsType,
        exc_info: Optional[_SysExcInfoType],
        func: Optional[str] = ...,
        extra: Optional[Mapping[str, Any]] = ...,
        sinfo: Optional[str] = ...,
    ) -> LogRecord: ...
    def hasHandlers(self) -> bool: ...

CRITICAL: int
FATAL: int
ERROR: int
WARNING: int
WARN: int
INFO: int
DEBUG: int
NOTSET: int

class Handler(Filterer):
    level: int  # undocumented
    formatter: Optional[Formatter]  # undocumented
    lock: Optional[threading.Lock]  # undocumented
    name: Optional[str]  # undocumented
    def __init__(self, level: _Level = ...) -> None: ...
    def createLock(self) -> None: ...
    def acquire(self) -> None: ...
    def release(self) -> None: ...
    def setLevel(self, level: _Level) -> None: ...
    def setFormatter(self, fmt: Formatter) -> None: ...
    def filter(self, record: LogRecord) -> bool: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    def handle(self, record: LogRecord) -> None: ...
    def handleError(self, record: LogRecord) -> None: ...
    def format(self, record: LogRecord) -> str: ...
    def emit(self, record: LogRecord) -> None: ...

class Formatter:
    converter: Callable[[Optional[float]], struct_time]
    _fmt: Optional[str]
    datefmt: Optional[str]
    _style: PercentStyle
    default_time_format: str
    default_msec_format: str

    if sys.version_info >= (3, 8):
        def __init__(
            self, fmt: Optional[str] = ..., datefmt: Optional[str] = ..., style: str = ..., validate: bool = ...
        ) -> None: ...
    else:
        def __init__(self, fmt: Optional[str] = ..., datefmt: Optional[str] = ..., style: str = ...) -> None: ...
    def format(self, record: LogRecord) -> str: ...
    def formatTime(self, record: LogRecord, datefmt: Optional[str] = ...) -> str: ...
    def formatException(self, ei: _SysExcInfoType) -> str: ...
    def formatMessage(self, record: LogRecord) -> str: ...  # undocumented
    def formatStack(self, stack_info: str) -> str: ...

class Filter:
    def __init__(self, name: str = ...) -> None: ...
    def filter(self, record: LogRecord) -> bool: ...

class LogRecord:
    args: _ArgsType
    asctime: str
    created: int
    exc_info: Optional[_SysExcInfoType]
    exc_text: Optional[str]
    filename: str
    funcName: str
    levelname: str
    levelno: int
    lineno: int
    module: str
    msecs: int
    message: str
    msg: str
    name: str
    pathname: str
    process: int
    processName: str
    relativeCreated: int
    stack_info: Optional[str]
    thread: int
    threadName: str
    def __init__(
        self,
        name: str,
        level: int,
        pathname: str,
        lineno: int,
        msg: Any,
        args: _ArgsType,
        exc_info: Optional[_SysExcInfoType],
        func: Optional[str] = ...,
        sinfo: Optional[str] = ...,
    ) -> None: ...
    def getMessage(self) -> str: ...

class LoggerAdapter:
    logger: Logger
    extra: Mapping[str, Any]
    def __init__(self, logger: Logger, extra: Mapping[str, Any]) -> None: ...
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]: ...
    if sys.version_info >= (3, 8):
        def debug(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def info(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warning(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warn(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def error(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def exception(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def critical(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def log(
            self,
            level: int,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            stacklevel: int = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
    else:
        def debug(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def info(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warning(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def warn(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def error(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def exception(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def critical(
            self,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
        def log(
            self,
            level: int,
            msg: Any,
            *args: Any,
            exc_info: _ExcInfoType = ...,
            stack_info: bool = ...,
            extra: Optional[dict[str, Any]] = ...,
            **kwargs: Any,
        ) -> None: ...
    def isEnabledFor(self, level: int) -> bool: ...
    def getEffectiveLevel(self) -> int: ...
    def setLevel(self, level: Union[int, str]) -> None: ...
    def hasHandlers(self) -> bool: ...
    def _log(
        self,
        level: int,
        msg: Any,
        args: _ArgsType,
        exc_info: Optional[_ExcInfoType] = ...,
        extra: Optional[dict[str, Any]] = ...,
        stack_info: bool = ...,
    ) -> None: ...  # undocumented

def getLogger(name: Optional[str] = ...) -> Logger: ...
def getLoggerClass() -> type: ...
def getLogRecordFactory() -> Callable[..., LogRecord]: ...

if sys.version_info >= (3, 8):
    def debug(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def info(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def warning(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def warn(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def error(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def critical(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def exception(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def log(
        level: int,
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        stacklevel: int = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...

else:
    def debug(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def info(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def warning(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def warn(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def error(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def critical(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def exception(
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def log(
        level: int,
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = ...,
        stack_info: bool = ...,
        extra: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...

fatal = critical

if sys.version_info >= (3, 7):
    def disable(level: int = ...) -> None: ...

else:
    def disable(level: int) -> None: ...

def addLevelName(level: int, levelName: str) -> None: ...
def getLevelName(level: Union[int, str]) -> Any: ...
def makeLogRecord(dict: Mapping[str, Any]) -> LogRecord: ...

if sys.version_info >= (3, 8):
    def basicConfig(
        *,
        filename: Optional[StrPath] = ...,
        filemode: str = ...,
        format: str = ...,
        datefmt: Optional[str] = ...,
        style: str = ...,
        level: Optional[_Level] = ...,
        stream: Optional[SupportsWrite[str]] = ...,
        handlers: Optional[Iterable[Handler]] = ...,
        force: bool = ...,
    ) -> None: ...

else:
    def basicConfig(
        *,
        filename: Optional[StrPath] = ...,
        filemode: str = ...,
        format: str = ...,
        datefmt: Optional[str] = ...,
        style: str = ...,
        level: Optional[_Level] = ...,
        stream: Optional[SupportsWrite[str]] = ...,
        handlers: Optional[Iterable[Handler]] = ...,
    ) -> None: ...

def shutdown(handlerList: Sequence[Any] = ...) -> None: ...  # handlerList is undocumented
def setLoggerClass(klass: type) -> None: ...
def captureWarnings(capture: bool) -> None: ...
def setLogRecordFactory(factory: Callable[..., LogRecord]) -> None: ...

lastResort: Optional[StreamHandler]

class StreamHandler(Handler):
    stream: SupportsWrite[str]  # undocumented
    terminator: str
    def __init__(self, stream: Optional[SupportsWrite[str]] = ...) -> None: ...
    if sys.version_info >= (3, 7):
        def setStream(self, stream: SupportsWrite[str]) -> Optional[SupportsWrite[str]]: ...

class FileHandler(StreamHandler):
    baseFilename: str  # undocumented
    mode: str  # undocumented
    encoding: Optional[str]  # undocumented
    delay: bool  # undocumented
    def __init__(self, filename: StrPath, mode: str = ..., encoding: Optional[str] = ..., delay: bool = ...) -> None: ...
    def _open(self) -> IO[Any]: ...

class NullHandler(Handler): ...

class PlaceHolder:
    def __init__(self, alogger: Logger) -> None: ...
    def append(self, alogger: Logger) -> None: ...

# Below aren't in module docs but still visible

class RootLogger(Logger):
    def __init__(self, level: int) -> None: ...

root: RootLogger

class PercentStyle(object):
    default_format: str
    asctime_format: str
    asctime_search: str
    _fmt: str
    def __init__(self, fmt: str) -> None: ...
    def usesTime(self) -> bool: ...
    def format(self, record: Any) -> str: ...

class StrFormatStyle(PercentStyle): ...

class StringTemplateStyle(PercentStyle):
    _tpl: Template

_STYLES: dict[str, tuple[PercentStyle, str]]

BASIC_FORMAT: str
