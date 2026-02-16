"""Utilities for generating C string literals."""

from __future__ import annotations

from typing import Final

_TRANSLATION_TABLE: Final[dict[int, str]] = {}


def _init_translation_table() -> None:
    for i in range(256):
        if i == ord("\n"):
            s = "\\n"
        elif i == ord("\r"):
            s = "\\r"
        elif i == ord("\t"):
            s = "\\t"
        elif i == ord('"'):
            s = '\\"'
        elif i == ord("\\"):
            s = "\\\\"
        elif 32 <= i < 127:
            s = chr(i)
        else:
            s = "\\x%02x" % i
        _TRANSLATION_TABLE[i] = s


_init_translation_table()


def c_string_initializer(value: bytes) -> str:
    """Convert a bytes object to a C string literal initializer.

    Returns a string like '"foo\\nbar"'.
    """
    return '"' + value.decode("latin1").translate(_TRANSLATION_TABLE) + '"'