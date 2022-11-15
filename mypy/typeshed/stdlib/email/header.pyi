from collections.abc import Iterable
from email.charset import Charset
from typing import Any

__all__ = ["Header", "decode_header", "make_header"]

class Header:
    def __init__(
        self,
        s: bytes | bytearray | str | None = ...,
        charset: Charset | str | None = ...,
        maxlinelen: int | None = ...,
        header_name: str | None = ...,
        continuation_ws: str = ...,
        errors: str = ...,
    ) -> None: ...
    def append(self, s: bytes | bytearray | str, charset: Charset | str | None = ..., errors: str = ...) -> None: ...
    def encode(self, splitchars: str = ..., maxlinelen: int | None = ..., linesep: str = ...) -> str: ...
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, __other: object) -> bool: ...

# decode_header() either returns list[tuple[str, None]] if the header
# contains no encoded parts, or list[tuple[bytes, str | None]] if the header
# contains at least one encoded part.
def decode_header(header: Header | str) -> list[tuple[Any, Any | None]]: ...
def make_header(
    decoded_seq: Iterable[tuple[bytes | bytearray | str, str | None]],
    maxlinelen: int | None = ...,
    header_name: str | None = ...,
    continuation_ws: str = ...,
) -> Header: ...
