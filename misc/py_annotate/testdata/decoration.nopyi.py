from typing import Any
def decoration(func):
    # type: (Any) -> Any
    return func

@decoration
def f1(a):
    # type: (Any) -> None
    pass
