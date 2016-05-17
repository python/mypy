from typing import Any
# With heuristics, have to pick between returning None or Any. If generating comment annotations,
# heuristics matter even if we have a pyi


def f1(x):
    # type: (e1) -> Any
    return 1

def f2(x):
    # type: (e2) -> None
    pass

def f3(x):
    # type: (e3) -> None
    return

def f4(x):
    # type: (e4) -> None
    def f(y):
        return 1

def f5(x):
    # type: (e5) -> Any
    return \
           1

def f6(x):
    # type: (e6) -> None
    return # foo
