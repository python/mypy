from typing import Generic, TypeVar

T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")


class A(Generic[T1]):
    x: T1

class B(Generic[T2]):
    x: T2

class C(B[T3]):
    pass

class D(C[str], A[str]):
    pass


# TypeInfo(
#   Name(test.C)
#   Bases(test.A[builtins.str], test.B[builtins.str])
#   Mro(test.C, test.A, test.B, builtins.object)
#   Names())
# )
# TypeInfo(
#   Name(test.A)
#   Bases(builtins.object)
#   Mro(test.A, builtins.object)
#   Names(
#     x (T`1)
#   )
# )
# TypeInfo(
#   Name(test.B)
#   Bases(builtins.object)
#   Mro(test.B, builtins.object)
#   Names(
#     x (T`1))
# )