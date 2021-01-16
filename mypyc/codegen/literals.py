from typing import Dict, Type, List

from mypyc.codegen.cstring import encode_bytes_as_c_string


class Literals:
    """Collection of literal values used in a compilation group."""

    def __init__(self) -> None:
        self.literals = {}  # type: Dict[Type[object], Dict[str, int]]

    def record_literal(self, value: str) -> None:
        """Ensure that the literal value is available in generated code."""
        literals = self.literals
        t = type(value)
        if t not in literals:
            literals[t] = {}
        d = literals[t]
        if value not in d:
            d[value] = len(d)

    def literal_index(self, value: str) -> int:
        """Return the index to the literals array for given value."""
        return self.literals[str][value]

    def encoded_str_values(self) -> List[bytes]:
        return encode_str_values(self.literals[str])


def encode_str_values(values: Dict[str, int]) -> List[bytes]:
    value_by_index = {}
    for value, index in values.items():
        value_by_index[index] = value
    result = []
    for i in range(len(values)):
        value = value_by_index[i]
        c_literal = format_str_literal(value)
        result.append(c_literal)
    return result


def format_int(n: int) -> bytes:
    if n < 128:
        return bytes([n])
    result = b''
    while n >= 128:
        result += bytes([(n & 0x7f) | 128])
        n >>= 7
    result += bytes([n])
    return result


def format_str_literal(s: str) -> bytes:
    utf8 = s.encode('utf-8')
    return format_int(len(utf8)) + utf8
