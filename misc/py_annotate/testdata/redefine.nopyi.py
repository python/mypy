from typing import Any
def f1(x):
    # type: (Any) -> Any
    return 1
def f1(x):
    # type: (Any) -> Any
    return 'foo'

def f2(x):
    # type: (Any) -> None
    pass
def f2(x,y):
    # type: (Any, Any) -> None
    pass

def f3(x):
    # type: (Any) -> Any
    return 1+x
def f3(x):
    # type: (Any) -> Any
    return 'asd'+x
