"""Test code geneneration for literals."""

import unittest

from mypyc.codegen.literals import (
    format_str_literal, _encode_str_values, _encode_bytes_values, _encode_int_values
)


class TestLiterals(unittest.TestCase):
    def test_format_str_literal(self) -> None:
        assert format_str_literal('') == b'\x00'
        assert format_str_literal('xyz') == b'\x03xyz'
        assert format_str_literal('x' * 127) == b'\x7f' + b'x' * 127
        assert format_str_literal('x' * 128) == b'\x81\x00' + b'x' * 128
        assert format_str_literal('x' * 131) == b'\x81\x03' + b'x' * 131

    def test_encode_str_values(self) -> None:
        assert _encode_str_values({}) == [b'']
        assert _encode_str_values({'foo': 0}) == [b'\x01\x03foo', b'']
        assert _encode_str_values({'foo': 0, 'b': 1}) == [b'\x02\x03foo\x01b', b'']
        assert _encode_str_values({'foo': 0, 'x' * 70: 1}) == [
            b'\x01\x03foo',
            bytes([1, 70]) + b'x' * 70,
            b''
        ]
        assert _encode_str_values({'y' * 100: 0}) == [
            bytes([1, 100]) + b'y' * 100,
            b''
        ]

    def test_encode_bytes_values(self) -> None:
        assert _encode_bytes_values({}) == [b'']
        assert _encode_bytes_values({b'foo': 0}) == [b'\x01\x03foo', b'']
        assert _encode_bytes_values({b'foo': 0, b'b': 1}) == [b'\x02\x03foo\x01b', b'']
        assert _encode_bytes_values({b'foo': 0, b'x' * 70: 1}) == [
            b'\x01\x03foo',
            bytes([1, 70]) + b'x' * 70,
            b''
        ]
        assert _encode_bytes_values({b'y' * 100: 0}) == [
            bytes([1, 100]) + b'y' * 100,
            b''
        ]

    def test_encode_int_values(self) -> None:
        assert _encode_int_values({}) == [b'']
        assert _encode_int_values({123: 0}) == [b'\x01123', b'']
        assert _encode_int_values({123: 0, 9: 1}) == [b'\x02123\x009', b'']
        assert _encode_int_values({123: 0, 45: 1, 5 * 10**70: 2}) == [
            b'\x02123\x0045',
            b'\x015' + b'0' * 70,
            b''
        ]
        assert _encode_int_values({6 * 10**100: 0}) == [
            b'\x016' + b'0' * 100,
            b''
        ]
