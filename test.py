from __future__ import annotations

from typing import Self, TypeVar, Protocol

T = TypeVar("T")


class InstanceOf(Protocol[T]):
    @property  # type: ignore
    def __class__(self) -> T: ...  # type: ignore


class MyMetaclass(type):
    bar: str

    def __new__(mcs: type[MyMetaclass], *args, **kwargs) -> MyMetaclass:
        cls = super().__new__(mcs, *args, **kwargs)
        cls.bar = "Hello"
        return cls

    def __mul__(
        cls,
        count: int,
    ) -> list[InstanceOf[Self]]:
        print(cls)
        return [cls()] * count

    def __call__(cls, *args, **kwargs) -> InstanceOf[Self]:
        return super().__call__(*args, **kwargs)


class Foo(metaclass=MyMetaclass):
    THIS: int

reveal_type(Foo)
reveal_type(Foo())
foos = Foo * 3
reveal_type(foos)
