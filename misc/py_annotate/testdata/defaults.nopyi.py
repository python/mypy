from typing import Any
def f1(x="foo"):
    # type: (str) -> None
    pass

def f2(x=
    #
"foo"):
    # type: (str) -> None
    pass

def f3(#
 x#=
  = #
    #
 123#
#
):
    # type: (int) -> None
    pass


def f4(x=(1,2)):
    # type: (Any) -> None
    pass

def f5(x=(1,)):
    # type: (Any) -> None
    pass

def f6(x=int):
    # type: (Any) -> None
    pass

# static analysis would give error here
def f7(x : int=int):
    pass

def f8(x={1:2}):
    # type: (Any) -> None
    pass

def f9(x=[1,2][:1]):
    # type: (Any) -> None
    pass
