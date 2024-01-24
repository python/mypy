from enum import Enum
from typing_extensions import assert_never


class MyEnum(Enum):
    A = 1
    B = 2
    C = 3


def my_function(a: MyEnum) -> bool:
    if a == MyEnum.A:
        return True
    elif a in (MyEnum.B, MyEnum.C):
        return False
    assert_never(a)


my_function(MyEnum.A)
