from __future__ import annotations

import unittest
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import TypedDict
from typing_extensions import assert_type
from unittest.mock import MagicMock, Mock, patch

case = unittest.TestCase()

###
# Tests for assertAlmostEqual
###

case.assertAlmostEqual(1, 2.4)
case.assertAlmostEqual(2.4, 2.41)
case.assertAlmostEqual(Fraction(49, 50), Fraction(48, 50))
case.assertAlmostEqual(3.14, complex(5, 6))
case.assertAlmostEqual(datetime(1999, 1, 2), datetime(1999, 1, 2, microsecond=1), delta=timedelta(hours=1))
case.assertAlmostEqual(datetime(1999, 1, 2), datetime(1999, 1, 2, microsecond=1), None, "foo", timedelta(hours=1))
case.assertAlmostEqual(Decimal("1.1"), Decimal("1.11"))
case.assertAlmostEqual(2.4, 2.41, places=8)
case.assertAlmostEqual(2.4, 2.41, delta=0.02)
case.assertAlmostEqual(2.4, 2.41, None, "foo", 0.02)

case.assertAlmostEqual(2.4, 2.41, places=9, delta=0.02)  # type: ignore
case.assertAlmostEqual("foo", "bar")  # type: ignore
case.assertAlmostEqual(datetime(1999, 1, 2), datetime(1999, 1, 2, microsecond=1))  # type: ignore
case.assertAlmostEqual(Decimal("0.4"), Fraction(1, 2))  # type: ignore
case.assertAlmostEqual(complex(2, 3), Decimal("0.9"))  # type: ignore

###
# Tests for assertNotAlmostEqual
###

case.assertAlmostEqual(1, 2.4)
case.assertNotAlmostEqual(Fraction(49, 50), Fraction(48, 50))
case.assertAlmostEqual(3.14, complex(5, 6))
case.assertNotAlmostEqual(datetime(1999, 1, 2), datetime(1999, 1, 2, microsecond=1), delta=timedelta(hours=1))
case.assertNotAlmostEqual(datetime(1999, 1, 2), datetime(1999, 1, 2, microsecond=1), None, "foo", timedelta(hours=1))

case.assertNotAlmostEqual(2.4, 2.41, places=9, delta=0.02)  # type: ignore
case.assertNotAlmostEqual("foo", "bar")  # type: ignore
case.assertNotAlmostEqual(datetime(1999, 1, 2), datetime(1999, 1, 2, microsecond=1))  # type: ignore
case.assertNotAlmostEqual(Decimal("0.4"), Fraction(1, 2))  # type: ignore
case.assertNotAlmostEqual(complex(2, 3), Decimal("0.9"))  # type: ignore

###
# Tests for assertGreater
###


class Spam:
    def __lt__(self, other: object) -> bool:
        return True


class Eggs:
    def __gt__(self, other: object) -> bool:
        return True


class Ham:
    def __lt__(self, other: Ham) -> bool:
        if not isinstance(other, Ham):
            return NotImplemented
        return True


class Bacon:
    def __gt__(self, other: Bacon) -> bool:
        if not isinstance(other, Bacon):
            return NotImplemented
        return True


case.assertGreater(5.8, 3)
case.assertGreater(Decimal("4.5"), Fraction(3, 2))
case.assertGreater(Fraction(3, 2), 0.9)
case.assertGreater(Eggs(), object())
case.assertGreater(object(), Spam())
case.assertGreater(Ham(), Ham())
case.assertGreater(Bacon(), Bacon())

case.assertGreater(object(), object())  # type: ignore
case.assertGreater(datetime(1999, 1, 2), 1)  # type: ignore
case.assertGreater(Spam(), Eggs())  # type: ignore
case.assertGreater(Ham(), Bacon())  # type: ignore
case.assertGreater(Bacon(), Ham())  # type: ignore


###
# Tests for assertDictEqual
###


class TD1(TypedDict):
    x: int
    y: str


class TD2(TypedDict):
    a: bool
    b: bool


class MyMapping(Mapping[str, int]):
    def __getitem__(self, __key: str) -> int:
        return 42

    def __iter__(self) -> Iterator[str]:
        return iter([])

    def __len__(self) -> int:
        return 0


td1: TD1 = {"x": 1, "y": "foo"}
td2: TD2 = {"a": True, "b": False}
m = MyMapping()

case.assertDictEqual({}, {})
case.assertDictEqual({"x": 1, "y": 2}, {"x": 1, "y": 2})
case.assertDictEqual({"x": 1, "y": "foo"}, {"y": "foo", "x": 1})
case.assertDictEqual({"x": 1}, {})
case.assertDictEqual({}, {"x": 1})
case.assertDictEqual({1: "x"}, {"y": 222})
case.assertDictEqual({1: "x"}, td1)
case.assertDictEqual(td1, {1: "x"})
case.assertDictEqual(td1, td2)

case.assertDictEqual(1, {})  # type: ignore
case.assertDictEqual({}, 1)  # type: ignore

# These should fail, but don't due to TypedDict limitations:
# case.assertDictEqual(m, {"": 0})  # xtype: ignore
# case.assertDictEqual({"": 0}, m)  # xtype: ignore

###
# Tests for mock.patch
###


@patch("sys.exit")
def f_default_new(i: int, mock: MagicMock) -> str:
    return "asdf"


@patch("sys.exit", new=42)
def f_explicit_new(i: int) -> str:
    return "asdf"


assert_type(f_default_new(1), str)
f_default_new("a")  # Not an error due to ParamSpec limitations
assert_type(f_explicit_new(1), str)
f_explicit_new("a")  # type: ignore[arg-type]


@patch("sys.exit", new=Mock())
class TestXYZ(unittest.TestCase):
    attr: int = 5

    @staticmethod
    def method() -> int:
        return 123


assert_type(TestXYZ.attr, int)
assert_type(TestXYZ.method(), int)
