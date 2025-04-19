from typing import Callable, TypeVar
from typing_extensions import ParamSpec

R = TypeVar("R")
P = ParamSpec("P")


def dec(f: Callable[P, R]) -> Callable[P, R]:
    return f


@dec
def f() -> None:
    print("hello world")
