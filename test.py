from __future__ import annotations

from typing import Generic, TypeVar
from typing_extensions import Self
from abc import ABC

T = TypeVar("T")
K = TypeVar("K")


class ItemSet(Generic[T]):
    def first(self) -> T: ...


class BaseItem(ABC):
    @property
    def set(self) -> ItemSet[Self]: ...


class FooItem(BaseItem):
    name: str

    def test(self) -> None: ...


reveal_type(FooItem().set.first().name)
reveal_type(BaseItem().set)
reveal_type(FooItem().set.first().test())
