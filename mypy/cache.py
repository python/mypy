from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from typing import Final

INT_SIZE: Final = 2
LONG_INT_SIZE: Final = 10
FLOAT_LEN: Final = 32


def read_int(data: BytesIO) -> int:
    return int.from_bytes(data.read(INT_SIZE), "big", signed=True)


def write_int(data: BytesIO, value: int) -> None:
    data.write(value.to_bytes(INT_SIZE, "big", signed=True))


def read_long_int(data: BytesIO) -> int:
    return int.from_bytes(data.read(LONG_INT_SIZE), "big", signed=True)


def write_long_int(data: BytesIO, value: int) -> None:
    data.write(value.to_bytes(LONG_INT_SIZE, "big", signed=True))


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
        return read_long_int(data)
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
        write_long_int(data, value)
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


OPT_NO: Final = 0
OPT_YES: Final = 1


def read_int_opt(data: BytesIO) -> int | None:
    marker = read_int(data)
    if marker == OPT_YES:
        return read_int(data)
    assert marker == OPT_NO
    return None


def write_int_opt(data: BytesIO, value: int | None) -> None:
    if value is not None:
        write_int(data, OPT_YES)
        write_int(data, value)
    else:
        write_int(data, OPT_NO)


def read_str_opt(data: BytesIO) -> str | None:
    marker = read_int(data)
    if marker == OPT_YES:
        return read_str(data)
    assert marker == OPT_NO
    return None


def write_str_opt(data: BytesIO, value: str | None) -> None:
    if value is not None:
        write_int(data, OPT_YES)
        write_str(data, value)
    else:
        write_int(data, OPT_NO)


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
