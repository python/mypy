# coding: mypy

# very simple script to test type annotations

from typing import Tuple

def f(x: int, y: str='abc') -> Tuple[int,
                                str]:
    return x, y

print(f(123))  # abc123

x = 1 + \
    2
