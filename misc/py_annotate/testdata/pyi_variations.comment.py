from typing import Any
def f1(x):
    # type: (e1) -> r1
    pass

def f2(x):
    # type: (Any) -> r2
    pass

def f3(x):
    # type: (e3) -> None
    pass

def f4(x):
    # type: (e4) -> r4
    pass

def f5(x):
    # type: (e5) -> r5
    pass

def f6(x):
    # type: (e6) -> r6
    pass

def f7(x):
    # type: (e7) -> r7
    pass

def f8(x):
    # type: (e8) -> \
     r8
    pass

def f9(x):
    # type: (Any) -> """
this is 
valid"""
    pass

def f10(x):
    # type: ("""
this is 
valid""") -> None
    pass
