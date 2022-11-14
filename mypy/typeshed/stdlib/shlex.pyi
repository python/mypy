import sys
from _typeshed import Self
from collections.abc import Iterable
from typing import TextIO

if sys.version_info >= (3, 8):
    __all__ = ["shlex", "split", "quote", "join"]
else:
    __all__ = ["shlex", "split", "quote"]

def split(s: str, comments: bool = ..., posix: bool = ...) -> list[str]: ...

if sys.version_info >= (3, 8):
    def join(split_command: Iterable[str]) -> str: ...

def quote(s: str) -> str: ...

class shlex(Iterable[str]):
    commenters: str
    wordchars: str
    whitespace: str
    escape: str
    quotes: str
    escapedquotes: str
    whitespace_split: bool
    infile: str | None
    instream: TextIO
    source: str
    debug: int
    lineno: int
    token: str
    eof: str
    @property
    def punctuation_chars(self) -> str: ...
    def __init__(
        self,
        instream: str | TextIO | None = ...,
        infile: str | None = ...,
        posix: bool = ...,
        punctuation_chars: bool | str = ...,
    ) -> None: ...
    def get_token(self) -> str: ...
    def push_token(self, tok: str) -> None: ...
    def read_token(self) -> str: ...
    def sourcehook(self, newfile: str) -> tuple[str, TextIO]: ...
    def push_source(self, newstream: str | TextIO, newfile: str | None = ...) -> None: ...
    def pop_source(self) -> None: ...
    def error_leader(self, infile: str | None = ..., lineno: int | None = ...) -> None: ...
    def __iter__(self: Self) -> Self: ...
    def __next__(self) -> str: ...
