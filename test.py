# coding: py3annot

# very simple script to test type annotations

def f(x: int, y: str = 'abc') -> str:
    return y + str(x)

print f(123) #abc123
