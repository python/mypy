from typing import Any
# With heuristics, have to pick between returning None or Any. If generating comment annotations,
# heuristics matter even if we have a pyi


def f1(x):
    # type: (Any) -> Any
    return 1

def f2(x):
    # type: (Any) -> None
    pass

def f3(x):
    # type: (Any) -> None
    return

def f4(x):
    # type: (Any) -> None
    def f(y):
        # type: (Any) -> Any
        return 1

def f5(x):
    # type: (Any) -> Any
    return \
           1

def f6(x):
    # type: (Any) -> None
    return # foo
