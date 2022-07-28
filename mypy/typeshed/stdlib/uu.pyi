from typing import BinaryIO
from typing_extensions import TypeAlias

__all__ = ["Error", "encode", "decode"]

_File: TypeAlias = str | BinaryIO

class Error(Exception): ...

def encode(in_file: _File, out_file: _File, name: str | None = ..., mode: int | None = ..., *, backtick: bool = ...) -> None: ...
def decode(in_file: _File, out_file: _File | None = ..., mode: int | None = ..., quiet: int = ...) -> None: ...
