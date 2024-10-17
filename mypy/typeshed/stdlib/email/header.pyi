from email.charset import Charset

__all__ = ["Header", "decode_header", "make_header"]

class Header:
    def __init__(
        self,
        s: bytes | str | None = ...,
        charset: Charset | str | None = ...,
        maxlinelen: int | None = ...,
        header_name: str | None = ...,
        continuation_ws: str = ...,
        errors: str = ...,
    ) -> None: ...
    def append(self, s: bytes | str, charset: Charset | str | None = ..., errors: str = ...) -> None: ...
    def encode(self, splitchars: str = ..., maxlinelen: int | None = ..., linesep: str = ...) -> str: ...
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, __other: object) -> bool: ...

def decode_header(header: Header | str) -> list[tuple[bytes, str | None]]: ...
def make_header(
    decoded_seq: list[tuple[bytes, str | None]],
    maxlinelen: int | None = ...,
    header_name: str | None = ...,
    continuation_ws: str = ...,
) -> Header: ...
