from __future__ import annotations

from collections.abc import Iterator
from typing import Generic, TypeVar
from typing_extensions import assert_type

x: list[int] = []
assert_type(list(reversed(x)), "list[int]")


class MyReversible:
    def __iter__(self) -> Iterator[str]:
        yield "blah"

    def __reversed__(self) -> Iterator[str]:
        yield "blah"


assert_type(list(reversed(MyReversible())), "list[str]")


_T = TypeVar("_T")


class MyLenAndGetItem(Generic[_T]):
    def __len__(self) -> int:
        return 0

    def __getitem__(self, item: int) -> _T:
        raise KeyError


len_and_get_item: MyLenAndGetItem[int] = MyLenAndGetItem()
assert_type(list(reversed(len_and_get_item)), "list[int]")
