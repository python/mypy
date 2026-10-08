"""Test code geneneration for literals."""

from __future__ import annotations

import unittest

from mypyc.codegen.literals import (
    Literals,
    _encode_bytes_values,
    _encode_int_values,
    _encode_str_values,
    format_str_literal,
    literal_sort_key,
)


class TestLiterals(unittest.TestCase):
    def test_format_str_literal(self) -> None:
        assert format_str_literal("") == b"\x00"
        assert format_str_literal("xyz") == b"\x03xyz"
        assert format_str_literal("x" * 127) == b"\x7f" + b"x" * 127
        assert format_str_literal("x" * 128) == b"\x81\x00" + b"x" * 128
        assert format_str_literal("x" * 131) == b"\x81\x03" + b"x" * 131

    def test_encode_str_values(self) -> None:
        assert _encode_str_values({}) == [b""]
        assert _encode_str_values({"foo": 0}) == [b"\x01\x03foo", b""]
        assert _encode_str_values({"foo": 0, "b": 1}) == [b"\x02\x03foo\x01b", b""]
        assert _encode_str_values({"foo": 0, "x" * 70: 1}) == [
            b"\x01\x03foo",
            bytes([1, 70]) + b"x" * 70,
            b"",
        ]
        assert _encode_str_values({"y" * 100: 0}) == [bytes([1, 100]) + b"y" * 100, b""]

    def test_encode_bytes_values(self) -> None:
        assert _encode_bytes_values({}) == [b""]
        assert _encode_bytes_values({b"foo": 0}) == [b"\x01\x03foo", b""]
        assert _encode_bytes_values({b"foo": 0, b"b": 1}) == [b"\x02\x03foo\x01b", b""]
        assert _encode_bytes_values({b"foo": 0, b"x" * 70: 1}) == [
            b"\x01\x03foo",
            bytes([1, 70]) + b"x" * 70,
            b"",
        ]
        assert _encode_bytes_values({b"y" * 100: 0}) == [bytes([1, 100]) + b"y" * 100, b""]

    def test_encode_int_values(self) -> None:
        assert _encode_int_values({}) == [b""]
        assert _encode_int_values({123: 0}) == [b"\x01123", b""]
        assert _encode_int_values({123: 0, 9: 1}) == [b"\x02123\x009", b""]
        assert _encode_int_values({123: 0, 45: 1, 5 * 10**70: 2}) == [
            b"\x02123\x0045",
            b"\x015" + b"0" * 70,
            b"",
        ]
        assert _encode_int_values({6 * 10**100: 0}) == [b"\x016" + b"0" * 100, b""]

    def test_simple_literal_index(self) -> None:
        lit = Literals()
        lit.record_literal(1)
        lit.record_literal("y")
        lit.record_literal(True)
        lit.record_literal(None)
        lit.record_literal(False)
        assert lit.literal_index(None) == 0
        assert lit.literal_index(False) == 1
        assert lit.literal_index(True) == 2
        assert lit.literal_index("y") == 3
        assert lit.literal_index(1) == 4

    def test_tuple_literal(self) -> None:
        lit = Literals()
        lit.record_literal((1, "y", None, (b"a", "b")))
        lit.record_literal((b"a", "b"))
        lit.record_literal(())
        assert lit.literal_index((b"a", "b")) == 7
        assert lit.literal_index((1, "y", None, (b"a", "b"))) == 8
        assert lit.literal_index(()) == 9
        print(lit.encoded_tuple_values())
        assert lit.encoded_tuple_values() == [
            "3",  # Number of tuples
            "2",
            "5",
            "4",  # First tuple (length=2)
            "4",
            "6",
            "3",
            "0",
            "7",  # Second tuple (length=4)
            "0",  # Third tuple (length=0)
        ]

    def test_frozenset_literal_index_is_deterministic(self) -> None:
        # Index assignment for members must not depend on frozenset iteration
        # order (which is hash-seed dependent), so that generated code is
        # reproducible.
        lit1 = Literals()
        lit1.record_literal(frozenset({"self", "cls"}))
        lit2 = Literals()
        lit2.record_literal(frozenset({"cls", "self"}))
        for s in ("self", "cls"):
            assert lit1.literal_index(s) == lit2.literal_index(s)
        # Members are recorded in sorted order.
        assert lit1.literal_index("cls") == 3
        assert lit1.literal_index("self") == 4

    def test_frozenset_encoding_is_deterministic(self) -> None:
        lit1 = Literals()
        lit1.record_literal(frozenset({"self", "cls"}))
        lit2 = Literals()
        lit2.record_literal(frozenset({"cls", "self"}))
        assert lit1.encoded_frozenset_values() == lit2.encoded_frozenset_values()

    def test_literal_sort_key_is_total_over_types(self) -> None:
        # Heterogeneous, individually unorderable items must still be sorted.
        values = ["x", b"y", 1, None, (1, 2), frozenset({1, 2})]
        values_reversed = list(reversed(values))
        assert sorted(values, key=literal_sort_key) == sorted(
            values_reversed, key=literal_sort_key
        )

    def test_literal_sort_key_with_frozenset(self) -> None:
        assert literal_sort_key(frozenset({"a", "b"})) == literal_sort_key(frozenset({"b", "a"}))
        assert literal_sort_key((frozenset({"a", "b"}),)) == literal_sort_key(
            (frozenset({"b", "a"}),)
        )
        assert literal_sort_key(frozenset({"a", frozenset({"b", "c"})})) == literal_sort_key(
            frozenset({frozenset({"c", "b"}), "a"})
        )

    def test_nested_frozenset_literal_index_is_deterministic(self) -> None:
        lit1 = Literals()
        lit1.record_literal(frozenset({frozenset({"a", "b"}), frozenset({"c", "d"})}))
        lit2 = Literals()
        lit2.record_literal(frozenset({frozenset({"d", "c"}), frozenset({"b", "a"})}))
        for s in ("a", "b", "c", "d"):
            assert lit1.literal_index(s) == lit2.literal_index(s)
        assert lit1.encoded_frozenset_values() == lit2.encoded_frozenset_values()
