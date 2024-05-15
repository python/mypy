from __future__ import annotations

import enum
import sys
from typing import Literal, Type
from typing_extensions import assert_type

A = enum.Enum("A", "spam eggs bacon")
B = enum.Enum("B", ["spam", "eggs", "bacon"])
C = enum.Enum("Bar", [("spam", 1), ("eggs", 2), ("bacon", 3)])
D = enum.Enum("Bar", {"spam": 1, "eggs": 2})

assert_type(A, Type[A])
assert_type(B, Type[B])
assert_type(C, Type[C])
assert_type(D, Type[D])


class EnumOfTuples(enum.Enum):
    X = 1, 2, 3
    Y = 4, 5, 6


assert_type(EnumOfTuples((1, 2, 3)), EnumOfTuples)

# TODO: ideally this test would pass:
#
# if sys.version_info >= (3, 12):
#     assert_type(EnumOfTuples(1, 2, 3), EnumOfTuples)


if sys.version_info >= (3, 11):

    class Foo(enum.StrEnum):
        X = enum.auto()

    assert_type(Foo.X, Literal[Foo.X])
    assert_type(Foo.X.value, str)
