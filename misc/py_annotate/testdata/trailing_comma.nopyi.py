from typing import Any
# Test trailing comma after last arg

def h1(a,):
    # type: (Any) -> None
    pass

def h2(a,b,):
    # type: (Any, Any) -> None
    pass

def h3(a):
    # type: (Any) -> None
    pass

def h4(a):
    # type: (Any) -> None
    pass
