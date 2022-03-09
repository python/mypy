import sys
from typing import IO

if sys.version_info >= (3, 10):
    __all__ = [
        "encode",
        "decode",
        "encodebytes",
        "decodebytes",
        "b64encode",
        "b64decode",
        "b32encode",
        "b32decode",
        "b32hexencode",
        "b32hexdecode",
        "b16encode",
        "b16decode",
        "b85encode",
        "b85decode",
        "a85encode",
        "a85decode",
        "standard_b64encode",
        "standard_b64decode",
        "urlsafe_b64encode",
        "urlsafe_b64decode",
    ]
else:
    __all__ = [
        "encode",
        "decode",
        "encodebytes",
        "decodebytes",
        "b64encode",
        "b64decode",
        "b32encode",
        "b32decode",
        "b16encode",
        "b16decode",
        "b85encode",
        "b85decode",
        "a85encode",
        "a85decode",
        "standard_b64encode",
        "standard_b64decode",
        "urlsafe_b64encode",
        "urlsafe_b64decode",
    ]

def b64encode(s: bytes, altchars: bytes | None = ...) -> bytes: ...
def b64decode(s: str | bytes, altchars: bytes | None = ..., validate: bool = ...) -> bytes: ...
def standard_b64encode(s: bytes) -> bytes: ...
def standard_b64decode(s: str | bytes) -> bytes: ...
def urlsafe_b64encode(s: bytes) -> bytes: ...
def urlsafe_b64decode(s: str | bytes) -> bytes: ...
def b32encode(s: bytes) -> bytes: ...
def b32decode(s: str | bytes, casefold: bool = ..., map01: bytes | None = ...) -> bytes: ...
def b16encode(s: bytes) -> bytes: ...
def b16decode(s: str | bytes, casefold: bool = ...) -> bytes: ...

if sys.version_info >= (3, 10):
    def b32hexencode(s: bytes) -> bytes: ...
    def b32hexdecode(s: str | bytes, casefold: bool = ...) -> bytes: ...

def a85encode(b: bytes, *, foldspaces: bool = ..., wrapcol: int = ..., pad: bool = ..., adobe: bool = ...) -> bytes: ...
def a85decode(b: str | bytes, *, foldspaces: bool = ..., adobe: bool = ..., ignorechars: str | bytes = ...) -> bytes: ...
def b85encode(b: bytes, pad: bool = ...) -> bytes: ...
def b85decode(b: str | bytes) -> bytes: ...
def decode(input: IO[bytes], output: IO[bytes]) -> None: ...
def encode(input: IO[bytes], output: IO[bytes]) -> None: ...
def encodebytes(s: bytes) -> bytes: ...
def decodebytes(s: bytes) -> bytes: ...

if sys.version_info < (3, 9):
    def encodestring(s: bytes) -> bytes: ...
    def decodestring(s: bytes) -> bytes: ...
