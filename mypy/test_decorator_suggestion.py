from typing import Callable, ParamSpec, TypeVar

R = TypeVar("R")
P = ParamSpec("P")


def dec(f: Callable[P, R]) -> Callable[P, R]:
    return f


@dec
def f():
    print("hello world")
