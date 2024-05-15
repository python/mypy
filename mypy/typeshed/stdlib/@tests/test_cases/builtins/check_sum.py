from __future__ import annotations

from typing import Any, List, Literal, Union
from typing_extensions import assert_type


class Foo:
    def __add__(self, other: Any) -> Foo:
        return Foo()


class Bar:
    def __radd__(self, other: Any) -> Bar:
        return Bar()


class Baz:
    def __add__(self, other: Any) -> Baz:
        return Baz()

    def __radd__(self, other: Any) -> Baz:
        return Baz()


literal_list: list[Literal[0, 1]] = [0, 1, 1]

assert_type(sum([2, 4]), int)
assert_type(sum([3, 5], 4), int)

assert_type(sum([True, False]), int)
assert_type(sum([True, False], True), int)
assert_type(sum(literal_list), int)

assert_type(sum([["foo"], ["bar"]], ["baz"]), List[str])

assert_type(sum([Foo(), Foo()], Foo()), Foo)
assert_type(sum([Baz(), Baz()]), Union[Baz, Literal[0]])

# mypy and pyright infer the types differently for these, so we can't use assert_type
# Just test that no error is emitted for any of these
sum([("foo",), ("bar", "baz")], ())  # mypy: `tuple[str, ...]`; pyright: `tuple[()] | tuple[str] | tuple[str, str]`
sum([5.6, 3.2])  # mypy: `float`; pyright: `float | Literal[0]`
sum([2.5, 5.8], 5)  # mypy: `float`; pyright: `float | int`

# These all fail at runtime
sum("abcde")  # type: ignore
sum([["foo"], ["bar"]])  # type: ignore
sum([("foo",), ("bar", "baz")])  # type: ignore
sum([Foo(), Foo()])  # type: ignore
sum([Bar(), Bar()], Bar())  # type: ignore
sum([Bar(), Bar()])  # type: ignore

# TODO: these pass pyright with the current stubs, but mypy erroneously emits an error:
# sum([3, Fraction(7, 22), complex(8, 0), 9.83])
# sum([3, Decimal('0.98')])
