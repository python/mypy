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

    def num_literals(self) -> int:
        n = 0
        for _, values in self.literals.items():
            n += len(values)
        return n

    def encoded_str_values(self) -> List[bytes]:
        return encode_str_values(self.literals[str])


def encode_str_values(values: Dict[str, int]) -> List[bytes]:
    value_by_index = {}
    for value, index in values.items():
        value_by_index[index] = value
    result = []
    num = len(values)
    result.append(format_int(num))
    for i in range(num):
        value = value_by_index[i]
        c_literal = format_str_literal(value)
        result.append(c_literal)
    return result


def format_int(n: int) -> bytes:
    if n < 128:
        a = [n]
    else:
        a = []
        while n > 0:
            a.insert(0, n & 0x7f)
            n >>= 7
        for i in range(len(a) - 1):
            a[i] |= 0x80
    return bytes(a)


def format_str_literal(s: str) -> bytes:
    utf8 = s.encode('utf-8')
    return format_int(len(utf8)) + utf8
