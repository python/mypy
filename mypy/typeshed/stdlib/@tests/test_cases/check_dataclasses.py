from __future__ import annotations

import dataclasses as dc
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Tuple, Type, Union
from typing_extensions import Annotated, assert_type

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dc.dataclass
class Foo:
    attr: str


assert_type(dc.fields(Foo), Tuple[dc.Field[Any], ...])

# Mypy correctly emits errors on these
# due to the fact it's a dataclass class, not an instance.
# Pyright, however, handles ClassVar members in protocols differently.
# See https://github.com/microsoft/pyright/issues/4339
#
# dc.asdict(Foo)
# dc.astuple(Foo)
# dc.replace(Foo)

# See #9723 for why we can't make this assertion
# if dc.is_dataclass(Foo):
#     assert_type(Foo, Type[Foo])

f = Foo(attr="attr")

assert_type(dc.fields(f), Tuple[dc.Field[Any], ...])
assert_type(dc.asdict(f), Dict[str, Any])
assert_type(dc.astuple(f), Tuple[Any, ...])
assert_type(dc.replace(f, attr="new"), Foo)

if dc.is_dataclass(f):
    # The inferred type doesn't change
    # if it's already known to be a subtype of _DataclassInstance
    assert_type(f, Foo)


def check_other_isdataclass_overloads(x: type, y: object) -> None:
    # TODO: pyright correctly emits an error on this, but mypy does not -- why?
    # dc.fields(x)

    dc.fields(y)  # type: ignore

    dc.asdict(x)  # type: ignore
    dc.asdict(y)  # type: ignore

    dc.astuple(x)  # type: ignore
    dc.astuple(y)  # type: ignore

    dc.replace(x)  # type: ignore
    dc.replace(y)  # type: ignore

    if dc.is_dataclass(x):
        assert_type(x, Type["DataclassInstance"])
        assert_type(dc.fields(x), Tuple[dc.Field[Any], ...])

        # Mypy correctly emits an error on these due to the fact
        # that it's a dataclass class, not a dataclass instance.
        # Pyright, however, handles ClassVar members in protocols differently.
        # See https://github.com/microsoft/pyright/issues/4339
        #
        # dc.asdict(x)
        # dc.astuple(x)
        # dc.replace(x)

    if dc.is_dataclass(y):
        assert_type(y, Union["DataclassInstance", Type["DataclassInstance"]])
        assert_type(dc.fields(y), Tuple[dc.Field[Any], ...])

        # Mypy correctly emits an error on these due to the fact we don't know
        # whether it's a dataclass class or a dataclass instance.
        # Pyright, however, handles ClassVar members in protocols differently.
        # See https://github.com/microsoft/pyright/issues/4339
        #
        # dc.asdict(y)
        # dc.astuple(y)
        # dc.replace(y)

    if dc.is_dataclass(y) and not isinstance(y, type):
        assert_type(y, "DataclassInstance")
        assert_type(dc.fields(y), Tuple[dc.Field[Any], ...])
        assert_type(dc.asdict(y), Dict[str, Any])
        assert_type(dc.astuple(y), Tuple[Any, ...])
        dc.replace(y)


# Regression test for #11653
D = dc.make_dataclass(
    "D", [("a", Union[int, None]), "y", ("z", Annotated[FrozenSet[bytes], "metadata"], dc.field(default=frozenset({b"foo"})))]
)
# Check that it's inferred by the type checker as a class object of some kind
# (but don't assert the exact type that `D` is inferred as,
# in case a type checker decides to add some special-casing for
# `make_dataclass` in the future)
assert_type(D.__mro__, Tuple[type, ...])
