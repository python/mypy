from email.message import Message
from typing import IO
from urllib.response import addinfourl

__all__ = ["URLError", "HTTPError", "ContentTooShortError"]

class URLError(IOError):
    reason: str | BaseException
    def __init__(self, reason: str | BaseException, filename: str | None = ...) -> None: ...

class HTTPError(URLError, addinfourl):
    @property
    def headers(self) -> Message: ...  # type: ignore[override]
    @property
    def reason(self) -> str: ...  # type: ignore[override]
    code: int
    def __init__(self, url: str, code: int, msg: str, hdrs: Message, fp: IO[bytes] | None) -> None: ...

class ContentTooShortError(URLError):
    content: tuple[str, Message]
    def __init__(self, message: str, content: tuple[str, Message]) -> None: ...
