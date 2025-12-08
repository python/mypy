from typing import *

x: Optional[int] = None
y: Optional[int] = None

def f() -> None:
    x = 1
    y = 1
    class C:
        reveal_type(x)  # Incorrectly reveals int, should be Optional[int]
        reveal_type(y)  # Correctly reveals int
        x = 2