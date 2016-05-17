from typing import Any
def f1(x=12):
    # type: (int) -> None
    pass

def f2(x=-12):
    # type: (Any) -> None
    pass

def f3(x=12L):
    # type: (int) -> None
    pass

def f4(x=-12L):
    # type: (Any) -> None
    pass

def f5(x=12.3):
    # type: (float) -> None
    pass

def f6(x=-12.3):
    # type: (Any) -> None
    pass

def f7(x="asd"):
    # type: (str) -> None
    pass

def f8(x=u"asd"):
    # type: (unicode) -> None
    pass

def f9(x=r"asd"):
    # type: (str) -> None
    pass

def f10(x=True):
    # type: (bool) -> None
    pass

def f11(x=False):
    # type: (bool) -> None
    pass

# Broken
def f12(x=3j):
    # type: (float) -> None
    pass

def f13(x=(1+2j)):
    # type: (Any) -> None
    pass

def f14(x=(1.3+2j)):
    # type: (Any) -> None
    pass
