from __future__ import annotations

from collections.abc import Sequence
from typing import Final


class BytesIO:
    def __init__(self, buffer: bytes | None = None) -> None:
        if buffer is None:
            self.write_buffer: bytearray | None = bytearray()
            self.read_buffer = None
        else:
            self.read_buffer = buffer
            self.write_buffer = None
        self.pos = 0

    def read(self, size: int) -> bytes:
        assert self.read_buffer is not None
        pos = self.pos
        self.pos += size
        return self.read_buffer[pos : self.pos]

    def write(self, chunk: bytes) -> None:
        assert self.write_buffer is not None
        self.write_buffer += chunk

    def getvalue(self) -> bytes:
        assert self.write_buffer is not None
        return bytes(self.write_buffer)


INT_LEN: Final = 10
FLOAT_LEN: Final = 24


def read_int(data: BytesIO) -> int:
    return int(data.read(INT_LEN).decode())


def write_int(data: BytesIO, value: int) -> None:
    str_val = str(value)
    str_val = " " * (INT_LEN - len(str_val)) + str_val
    data.write(str_val.encode())


def read_str(data: BytesIO) -> str:
    size = read_int(data)
    encoded = data.read(size)
    return encoded.decode()


def write_str(data: BytesIO, value: str) -> None:
    encoded = value.encode()
    size = len(encoded)
    write_int(data, size)
    data.write(encoded)


def read_bool(data: BytesIO) -> bool:
    return data.read(1) == b"\xff"


def write_bool(data: BytesIO, value: bool) -> None:
    data.write(b"\xff" if value else b"\x00")


def read_float(data: BytesIO) -> float:
    value_str = data.read(FLOAT_LEN).decode()
    return float(value_str)


def write_float(data: BytesIO, value: float) -> None:
    value_str = str(value)
    value_str = "0" * (FLOAT_LEN - len(value_str)) + value_str
    data.write(value_str.encode())


LITERAL_INT: Final = 1
LITERAL_STR: Final = 2
LITERAL_BOOL: Final = 3
LITERAL_FLOAT: Final = 4
LITERAL_COMPLEX: Final = 5
LITERAL_NONE: Final = 6


def read_literal(data: BytesIO, marker: int) -> int | str | bool | float:
    if marker == LITERAL_INT:
        return read_int(data)
    elif marker == LITERAL_STR:
        return read_str(data)
    elif marker == LITERAL_BOOL:
        return read_bool(data)
    elif marker == LITERAL_FLOAT:
        return read_float(data)
    assert False, f"Unknown literal marker {marker}"


def write_literal(data: BytesIO, value: int | str | bool | float | complex | None) -> None:
    if isinstance(value, bool):
        write_int(data, LITERAL_BOOL)
        write_bool(data, value)
    elif isinstance(value, int):
        write_int(data, LITERAL_INT)
        write_int(data, value)
    elif isinstance(value, str):
        write_int(data, LITERAL_STR)
        write_str(data, value)
    elif isinstance(value, float):
        write_int(data, LITERAL_FLOAT)
        write_float(data, value)
    elif isinstance(value, complex):
        write_int(data, LITERAL_COMPLEX)
        write_float(data, value.real)
        write_float(data, value.imag)
    else:
        write_int(data, LITERAL_NONE)


def read_int_opt(data: BytesIO) -> int | None:
    if read_bool(data):
        return read_int(data)
    return None


def write_int_opt(data: BytesIO, value: int | None) -> None:
    if value is not None:
        write_bool(data, True)
        write_int(data, value)
    else:
        write_bool(data, False)


def read_str_opt(data: BytesIO) -> str | None:
    if read_bool(data):
        return read_str(data)
    return None


def write_str_opt(data: BytesIO, value: str | None) -> None:
    if value is not None:
        write_bool(data, True)
        write_str(data, value)
    else:
        write_bool(data, False)


def read_int_list(data: BytesIO) -> list[int]:
    size = read_int(data)
    return [read_int(data) for _ in range(size)]


def write_int_list(data: BytesIO, value: list[int]) -> None:
    write_int(data, len(value))
    for item in value:
        write_int(data, item)


def read_str_list(data: BytesIO) -> list[str]:
    size = read_int(data)
    return [read_str(data) for _ in range(size)]


def write_str_list(data: BytesIO, value: Sequence[str]) -> None:
    write_int(data, len(value))
    for item in value:
        write_str(data, item)


def read_str_opt_list(data: BytesIO) -> list[str | None]:
    size = read_int(data)
    return [read_str_opt(data) for _ in range(size)]


def write_str_opt_list(data: BytesIO, value: list[str | None]) -> None:
    write_int(data, len(value))
    for item in value:
        write_str_opt(data, item)
