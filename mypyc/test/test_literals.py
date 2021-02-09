"""Test code geneneration for literals."""

import unittest

from mypyc.codegen.literals import format_str_literal, Literals


class TestLiterals(unittest.TestCase):
    def test_format_str_literal(self) -> None:
        assert format_str_literal('') == b'\x00'
        assert format_str_literal('xyz') == b'\x03xyz'
        assert format_str_literal('x' * 127) == b'\x7f' + b'x' * 127
        assert format_str_literal('x' * 128) == b'\x81\x00' + b'x' * 128
        assert format_str_literal('x' * 131) == b'\x81\x03' + b'x' * 131

    def test_simple_literal_index(self) -> None:
        lit = Literals()
        lit.record_literal(1)
        lit.record_literal('y')
        lit.record_literal(True)
        lit.record_literal(None)
        lit.record_literal(False)
        assert lit.literal_index(None) == 0
        assert lit.literal_index(False) == 1
        assert lit.literal_index(True) == 2
        assert lit.literal_index('y') == 3
        assert lit.literal_index(1) == 4

    def test_tuple_literal(self) -> None:
        lit = Literals()
        lit.record_literal((1, 'y', None, (b'a', 'b')))
        lit.record_literal((b'a', 'b'))
        lit.record_literal(())
        assert lit.literal_index((b'a', 'b')) == 7
        assert lit.literal_index((1, 'y', None, (b'a', 'b'))) == 8
        assert lit.literal_index(()) == 9
        print(lit.encoded_tuple_values())
        assert lit.encoded_tuple_values() == [
            '3',  # Number of tuples
            '2', '5', '4',  # First tuple (length=2)
            '4', '6', '3', '0', '7',  # Second tuple (length=4)
            '0',  # Third tuple (length=0)
        ]
