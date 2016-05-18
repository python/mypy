from typing import Any
# tuple unpacking
def f1((a, b)):
    # type: (Any) -> None
    pass

def f1b((a, b)):
    # type: (Any) -> None
    pass

def f2((a, b, (c,d))=(1,2, (3,4))):
    # type: (Any) -> None
    pass

def f3((a, b : int)):
    # type: (Any) -> None
    pass

def f4((a, b : SomeType(a=(3,(4,3))))):
    # type: (Any) -> None
    pass

def f5((((((a,)))))):
    # type: (Any) -> None
    pass

def f6((((((a,)),),))):
    # type: (Any) -> None
    pass

def f7(
        (
        (
        (((a,)),),))):
    # type: (Any) -> None
    pass
