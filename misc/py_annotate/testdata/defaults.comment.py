def f1(x="foo"):
    # type: (e1) -> r1
    pass

def f2(x=
    #
"foo"):
    # type: (e2) -> r2
    pass

def f3(#
 x#=
  = #
    #
 123#
#
):
    # type: (e3) -> r3
    pass


def f4(x=(1,2)):
    # type: (e4) -> r4
    pass

def f5(x=(1,)):
    # type: (e5) -> r5
    pass

def f6(x=int):
    # type: (e6) -> r6
    pass

# static analysis would give error here
def f7(x : int=int):
    pass

def f8(x={1:2}):
    # type: (e8) -> r8
    pass

def f9(x=[1,2][:1]):
    # type: (e9) -> r9
    pass
