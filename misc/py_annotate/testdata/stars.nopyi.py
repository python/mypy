from typing import Any
def f1(*a):
    # type: (*Any) -> None
    pass

def f2(**a):
    # type: (**Any) -> None
    pass

def f3(a, *b):
    # type: (Any, *Any) -> None
    pass

def f4(a, **b):
    # type: (Any, **Any) -> None
    pass

## arg with default after *args is valid python3, not python2
def f5(*a, b=1):
    # type: (*Any, int) -> None
    pass

def f6(*a, b=1, **c):
    # type: (*Any, int, **Any) -> None
    pass

def f7(x=1, *a, b=1, **c):
    # type: (int, *Any, int, **Any) -> None
    pass

def f8(#asd
        *a):
    # type: (*Any) -> None
    pass
