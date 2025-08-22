from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

try:
    from native_internal import (
        Buffer as Buffer,
        read_bool as read_bool,
        read_float as read_float,
        read_int as read_int,
        read_str as read_str,
        write_bool as write_bool,
        write_float as write_float,
        write_int as write_int,
        write_str as write_str,
    )
except ImportError:
    # TODO: temporary, remove this after we publish mypy-native on PyPI.
    if not TYPE_CHECKING:

        class Buffer:
            def __init__(self, source: bytes = b"") -> None:
                raise NotImplementedError

            def getvalue(self) -> bytes:
                raise NotImplementedError

        def read_int(data: Buffer) -> int:
            raise NotImplementedError

        def write_int(data: Buffer, value: int) -> None:
            raise NotImplementedError

        def read_str(data: Buffer) -> str:
            raise NotImplementedError

        def write_str(data: Buffer, value: str) -> None:
            raise NotImplementedError

        def read_bool(data: Buffer) -> bool:
            raise NotImplementedError

        def write_bool(data: Buffer, value: bool) -> None:
            raise NotImplementedError

        def read_float(data: Buffer) -> float:
            raise NotImplementedError

        def write_float(data: Buffer, value: float) -> None:
            raise NotImplementedError


LITERAL_INT: Final = 1
LITERAL_STR: Final = 2
LITERAL_BOOL: Final = 3
LITERAL_FLOAT: Final = 4
LITERAL_COMPLEX: Final = 5
LITERAL_NONE: Final = 6


def read_literal(data: Buffer, marker: int) -> int | str | bool | float:
    if marker == LITERAL_INT:
        return read_int(data)
    elif marker == LITERAL_STR:
        return read_str(data)
    elif marker == LITERAL_BOOL:
        return read_bool(data)
    elif marker == LITERAL_FLOAT:
        return read_float(data)
    assert False, f"Unknown literal marker {marker}"


def write_literal(data: Buffer, value: int | str | bool | float | complex | None) -> None:
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


def read_int_opt(data: Buffer) -> int | None:
    if read_bool(data):
        return read_int(data)
    return None


def write_int_opt(data: Buffer, value: int | None) -> None:
    if value is not None:
        write_bool(data, True)
        write_int(data, value)
    else:
        write_bool(data, False)


def read_str_opt(data: Buffer) -> str | None:
    if read_bool(data):
        return read_str(data)
    return None


def write_str_opt(data: Buffer, value: str | None) -> None:
    if value is not None:
        write_bool(data, True)
        write_str(data, value)
    else:
        write_bool(data, False)


def read_int_list(data: Buffer) -> list[int]:
    size = read_int(data)
    return [read_int(data) for _ in range(size)]


def write_int_list(data: Buffer, value: list[int]) -> None:
    write_int(data, len(value))
    for item in value:
        write_int(data, item)


def read_str_list(data: Buffer) -> list[str]:
    size = read_int(data)
    return [read_str(data) for _ in range(size)]


def write_str_list(data: Buffer, value: Sequence[str]) -> None:
    write_int(data, len(value))
    for item in value:
        write_str(data, item)


def read_str_opt_list(data: Buffer) -> list[str | None]:
    size = read_int(data)
    return [read_str_opt(data) for _ in range(size)]


def write_str_opt_list(data: Buffer, value: list[str | None]) -> None:
    write_int(data, len(value))
    for item in value:
        write_str_opt(data, item)
