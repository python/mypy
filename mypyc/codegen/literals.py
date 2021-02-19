from typing import Dict, List, Union


class Literals:
    """Collection of literal values used in a compilation group and related helpers."""

    def __init__(self) -> None:
        # Each dict maps value to literal index (0, 1, ...)
        self.str_literals = {}  # type: Dict[str, int]
        self.bytes_literals = {}  # type: Dict[bytes, int]
        self.int_literals = {}  # type: Dict[int, int]
        self.float_literals = {}  # type: Dict[float, int]
        self.complex_literals = {}  # type: Dict[complex, int]

    def record_literal(self, value: Union[str, bytes, int, float, complex]) -> None:
        """Ensure that the literal value is available in generated code."""
        if isinstance(value, str):
            str_literals = self.str_literals
            if value not in str_literals:
                str_literals[value] = len(str_literals)
        elif isinstance(value, bytes):
            bytes_literals = self.bytes_literals
            if value not in bytes_literals:
                bytes_literals[value] = len(bytes_literals)
        elif isinstance(value, int):
            int_literals = self.int_literals
            if value not in int_literals:
                int_literals[value] = len(int_literals)
        elif isinstance(value, float):
            float_literals = self.float_literals
            if value not in float_literals:
                float_literals[value] = len(float_literals)
        elif isinstance(value, complex):
            complex_literals = self.complex_literals
            if value not in complex_literals:
                complex_literals[value] = len(complex_literals)
        else:
            assert False, 'invalid literal: %r' % value

    def literal_index(self, value: Union[str, bytes, int, float, complex]) -> int:
        """Return the index to the literals array for given value."""
        # The array contains first all str values, followed by bytes values, etc.
        if isinstance(value, str):
            return self.str_literals[value]
        n = len(self.str_literals)
        if isinstance(value, bytes):
            return n + self.bytes_literals[value]
        n += len(self.bytes_literals)
        if isinstance(value, int):
            return n + self.int_literals[value]
        n += len(self.int_literals)
        if isinstance(value, float):
            return n + self.float_literals[value]
        n += len(self.float_literals)
        if isinstance(value, complex):
            return n + self.complex_literals[value]
        assert False, 'invalid literal: %r' % value

    def num_literals(self) -> int:
        return (len(self.str_literals) + len(self.bytes_literals) + len(self.int_literals) +
                len(self.float_literals) + len(self.complex_literals))

    # The following methods return the C encodings of literal values
    # of different types

    def encoded_str_values(self) -> List[bytes]:
        return encode_str_values(self.str_literals)

    def encoded_int_values(self) -> List[bytes]:
        return encode_int_values(self.int_literals)

    def encoded_bytes_values(self) -> List[bytes]:
        return encode_bytes_values(self.bytes_literals)

    def encoded_float_values(self) -> List[str]:
        return encode_float_values(self.float_literals)

    def encoded_complex_values(self) -> List[str]:
        return encode_complex_values(self.complex_literals)


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


def encode_bytes_values(values: Dict[bytes, int]) -> List[bytes]:
    value_by_index = {}
    for value, index in values.items():
        value_by_index[index] = value
    result = []
    num = len(values)
    result.append(format_int(num))
    for i in range(num):
        value = value_by_index[i]
        result.append(format_int(len(value)))
        result.append(value)
    return result


def format_int(n: int) -> bytes:
    """Format an integer using a variable-length binary encoding."""
    if n < 128:
        a = [n]
    else:
        a = []
        while n > 0:
            a.insert(0, n & 0x7f)
            n >>= 7
        for i in range(len(a) - 1):
            # If the highest bit is set, more 7-bit digits follow
            a[i] |= 0x80
    return bytes(a)


def format_str_literal(s: str) -> bytes:
    utf8 = s.encode('utf-8')
    return format_int(len(utf8)) + utf8


def encode_int_values(values: Dict[int, int]) -> List[bytes]:
    """Encode int values into C string fragments.

    Values are stored in base 10 and separated by 0 bytes.
    """
    value_by_index = {}
    for value, index in values.items():
        value_by_index[index] = value
    result = []
    num = len(values)
    result.append(format_int(num))
    for i in range(num):
        value = value_by_index[i]
        result.append(b'%d\0' % value)
    return result


def float_to_c(x: float) -> str:
    """Return C literal representation of a float value."""
    s = str(x)
    if s == 'inf':
        return 'INFINITY'
    elif s == '-inf':
        return '-INFINITY'
    return s


def encode_float_values(values: Dict[float, int]) -> List[str]:
    """Encode float values into a C array values.

    The result contains the number of values followed by individual values.
    """
    value_by_index = {}
    for value, index in values.items():
        value_by_index[index] = value
    result = []
    num = len(values)
    result.append(str(num))
    for i in range(num):
        value = value_by_index[i]
        result.append(float_to_c(value))
    return result


def encode_complex_values(values: Dict[complex, int]) -> List[str]:
    """Encode float values into a C array values.

    The result contains the number of values followed by pairs of doubles
    representing complex numbers.
    """
    value_by_index = {}
    for value, index in values.items():
        value_by_index[index] = value
    result = []
    num = len(values)
    result.append(str(num))
    for i in range(num):
        value = value_by_index[i]
        result.append(float_to_c(value.real))
        result.append(float_to_c(value.imag))
    return result
