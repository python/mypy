import datetime
import ssl
import sys
from _typeshed import StrPath
from collections.abc import Callable
from logging import FileHandler, Handler, LogRecord
from socket import SocketKind, SocketType
from typing import Any, ClassVar, Optional, Union

if sys.version_info >= (3, 7):
    from queue import Queue, SimpleQueue
else:
    from queue import Queue

DEFAULT_TCP_LOGGING_PORT: int
DEFAULT_UDP_LOGGING_PORT: int
DEFAULT_HTTP_LOGGING_PORT: int
DEFAULT_SOAP_LOGGING_PORT: int
SYSLOG_UDP_PORT: int
SYSLOG_TCP_PORT: int

class WatchedFileHandler(FileHandler):
    dev: int
    ino: int
    def __init__(self, filename: StrPath, mode: str = ..., encoding: Optional[str] = ..., delay: bool = ...) -> None: ...
    def _statstream(self) -> None: ...

class BaseRotatingHandler(FileHandler):
    terminator: str
    namer: Optional[Callable[[str], str]]
    rotator: Optional[Callable[[str, str], None]]
    def __init__(self, filename: StrPath, mode: str, encoding: Optional[str] = ..., delay: bool = ...) -> None: ...
    def rotation_filename(self, default_name: str) -> None: ...
    def rotate(self, source: str, dest: str) -> None: ...

class RotatingFileHandler(BaseRotatingHandler):
    def __init__(
        self,
        filename: StrPath,
        mode: str = ...,
        maxBytes: int = ...,
        backupCount: int = ...,
        encoding: Optional[str] = ...,
        delay: bool = ...,
    ) -> None: ...
    def doRollover(self) -> None: ...

class TimedRotatingFileHandler(BaseRotatingHandler):
    def __init__(
        self,
        filename: StrPath,
        when: str = ...,
        interval: int = ...,
        backupCount: int = ...,
        encoding: Optional[str] = ...,
        delay: bool = ...,
        utc: bool = ...,
        atTime: Optional[datetime.datetime] = ...,
    ) -> None: ...
    def doRollover(self) -> None: ...

class SocketHandler(Handler):
    retryStart: float
    retryFactor: float
    retryMax: float
    def __init__(self, host: str, port: Optional[int]) -> None: ...
    def makeSocket(self, timeout: float = ...) -> SocketType: ...  # timeout is undocumented
    def makePickle(self, record: LogRecord) -> bytes: ...
    def send(self, s: bytes) -> None: ...
    def createSocket(self) -> None: ...

class DatagramHandler(SocketHandler):
    def makeSocket(self) -> SocketType: ...  # type: ignore

class SysLogHandler(Handler):
    LOG_EMERG: int
    LOG_ALERT: int
    LOG_CRIT: int
    LOG_ERR: int
    LOG_WARNING: int
    LOG_NOTICE: int
    LOG_INFO: int
    LOG_DEBUG: int

    LOG_KERN: int
    LOG_USER: int
    LOG_MAIL: int
    LOG_DAEMON: int
    LOG_AUTH: int
    LOG_SYSLOG: int
    LOG_LPR: int
    LOG_NEWS: int
    LOG_UUCP: int
    LOG_CRON: int
    LOG_AUTHPRIV: int
    LOG_FTP: int

    if sys.version_info >= (3, 9):
        LOG_NTP: int
        LOG_SECURITY: int
        LOG_CONSOLE: int
        LOG_SOLCRON: int

    LOG_LOCAL0: int
    LOG_LOCAL1: int
    LOG_LOCAL2: int
    LOG_LOCAL3: int
    LOG_LOCAL4: int
    LOG_LOCAL5: int
    LOG_LOCAL6: int
    LOG_LOCAL7: int
    unixsocket: bool  # undocumented
    socktype: SocketKind  # undocumented
    ident: str  # undocumented
    facility: int  # undocumented
    priority_names: ClassVar[dict[str, int]]  # undocumented
    facility_names: ClassVar[dict[str, int]]  # undocumented
    priority_map: ClassVar[dict[str, str]]  # undocumented
    def __init__(
        self, address: Union[tuple[str, int], str] = ..., facility: int = ..., socktype: Optional[SocketKind] = ...
    ) -> None: ...
    def encodePriority(self, facility: Union[int, str], priority: Union[int, str]) -> int: ...
    def mapPriority(self, levelName: str) -> str: ...

class NTEventLogHandler(Handler):
    def __init__(self, appname: str, dllname: Optional[str] = ..., logtype: str = ...) -> None: ...
    def getEventCategory(self, record: LogRecord) -> int: ...
    # TODO correct return value?
    def getEventType(self, record: LogRecord) -> int: ...
    def getMessageID(self, record: LogRecord) -> int: ...

class SMTPHandler(Handler):
    # TODO `secure` can also be an empty tuple
    def __init__(
        self,
        mailhost: Union[str, tuple[str, int]],
        fromaddr: str,
        toaddrs: list[str],
        subject: str,
        credentials: Optional[tuple[str, str]] = ...,
        secure: Union[tuple[str], tuple[str, str], None] = ...,
        timeout: float = ...,
    ) -> None: ...
    def getSubject(self, record: LogRecord) -> str: ...

class BufferingHandler(Handler):
    buffer: list[LogRecord]
    def __init__(self, capacity: int) -> None: ...
    def shouldFlush(self, record: LogRecord) -> bool: ...

class MemoryHandler(BufferingHandler):
    def __init__(
        self, capacity: int, flushLevel: int = ..., target: Optional[Handler] = ..., flushOnClose: bool = ...
    ) -> None: ...
    def setTarget(self, target: Handler) -> None: ...

class HTTPHandler(Handler):
    def __init__(
        self,
        host: str,
        url: str,
        method: str = ...,
        secure: bool = ...,
        credentials: Optional[tuple[str, str]] = ...,
        context: Optional[ssl.SSLContext] = ...,
    ) -> None: ...
    def mapLogRecord(self, record: LogRecord) -> dict[str, Any]: ...

class QueueHandler(Handler):
    if sys.version_info >= (3, 7):
        def __init__(self, queue: Union[SimpleQueue[Any], Queue[Any]]) -> None: ...
    else:
        def __init__(self, queue: Queue[Any]) -> None: ...
    def prepare(self, record: LogRecord) -> Any: ...
    def enqueue(self, record: LogRecord) -> None: ...

class QueueListener:
    if sys.version_info >= (3, 7):
        def __init__(
            self, queue: Union[SimpleQueue[Any], Queue[Any]], *handlers: Handler, respect_handler_level: bool = ...
        ) -> None: ...
    else:
        def __init__(self, queue: Queue[Any], *handlers: Handler, respect_handler_level: bool = ...) -> None: ...
    def dequeue(self, block: bool) -> LogRecord: ...
    def prepare(self, record: LogRecord) -> Any: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def enqueue_sentinel(self) -> None: ...
