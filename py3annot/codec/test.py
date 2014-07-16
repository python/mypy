# coding: py3annot

# very simple script to test type annotations

def f(x: int, y: str='abc') -> [int, 
                                str]:
    return x, y

print(f(123)) #abc123

x = 1 + \
    2


