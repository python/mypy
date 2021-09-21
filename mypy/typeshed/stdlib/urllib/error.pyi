from email.message import Message
from typing import IO, Tuple
from urllib.response import addinfourl

# Stubs for urllib.error

class URLError(IOError):
    reason: str | BaseException
    def __init__(self, reason: str | BaseException, filename: str | None = ...) -> None: ...

class HTTPError(URLError, addinfourl):
    code: int
    def __init__(self, url: str, code: int, msg: str, hdrs: Message, fp: IO[bytes] | None) -> None: ...

class ContentTooShortError(URLError):
    content: Tuple[str, Message]
    def __init__(self, message: str, content: Tuple[str, Message]) -> None: ...
