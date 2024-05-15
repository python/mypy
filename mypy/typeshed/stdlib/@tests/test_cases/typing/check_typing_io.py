from __future__ import annotations

import mmap
from typing import IO, AnyStr


def check_write(io_bytes: IO[bytes], io_str: IO[str], io_anystr: IO[AnyStr], any_str: AnyStr, buf: mmap.mmap) -> None:
    io_bytes.write(b"")
    io_bytes.write(buf)
    io_bytes.write("")  # type: ignore
    io_bytes.write(any_str)  # type: ignore

    io_str.write(b"")  # type: ignore
    io_str.write(buf)  # type: ignore
    io_str.write("")
    io_str.write(any_str)  # type: ignore

    io_anystr.write(b"")  # type: ignore
    io_anystr.write(buf)  # type: ignore
    io_anystr.write("")  # type: ignore
    io_anystr.write(any_str)
