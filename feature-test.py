from enum import Enum
from typing_extensions import assert_never


class MyEnum(Enum):
    A = 1
    B = 2
    C = 3


reveal_type(MyEnum.A)
reveal_type(MyEnum.B)
reveal_type(MyEnum.C)


def my_function(a: MyEnum) -> bool:

    print(type((MyEnum.B, MyEnum.C)))
    if a == MyEnum.A:
        print(type(a))
        return True
    elif a in (MyEnum.B, MyEnum.C):
        return False
    assert_never(a)


print(my_function(MyEnum.A))
