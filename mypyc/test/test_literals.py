"""Test code geneneration for literals."""

import unittest

from mypyc.codegen.literals import format_str_literal


class TestLiterals(unittest.TestCase):
    def test_format_str_literal(self) -> None:
        assert format_str_literal('') == b'\x00'
        assert format_str_literal('xyz') == b'\x03xyz'
        assert format_str_literal('x' * 127) == b'\x7f' + b'x' * 127
        assert format_str_literal('x' * 128) == b'\x81\x00' + b'x' * 128
        assert format_str_literal('x' * 131) == b'\x81\x03' + b'x' * 131
