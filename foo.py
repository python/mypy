import attr
import typing
from attr import attributes

# from typing import Optional
from typing import List

@attr.s(auto_attribs=True)
class Auto:
    normal: int
    _private: int
    def_arg: int = 18
    _def_kwarg: int = attr.ib(validator=None, default=18)

    FOO: typing.ClassVar[int] = 18

reveal_type(Auto)
Auto(1, 2, 3)


@attr.s
class Typed:
    normal: int = attr.ib()
    _private: int = attr.ib()
    def_arg: int = attr.ib(18)
    _def_kwarg: int = attr.ib(validator=None, default=18)

    FOO: int = 18

reveal_type(Typed)
Typed(1, 2, 3)


@attr.s
class UnTyped:
    normal = attr.ib()
    _private = attr.ib()
    def_arg = attr.ib(18)
    _def_kwarg = attr.ib(validator=None, default=18)

    FOO = 18

reveal_type(UnTyped)
UnTyped(1, 2, 3)

# @attr.s
# class UnTyped:
#     pass
#
#
# @attributes
# class UnTyped:
#     pass
#
#
# class Bar(UnTyped, List[str], typing.Mapping, List()):
#     pass
#
#
# UnTyped(6, '17')
#



# @attr.s
# class NonAuto:
#     a: int = attr.ib()
#     b: int = attr.ib(default=18)
#
#     cls_var = 18
#
#     def stuff(self) -> int:
#         return self.b + self.c



# @attr.s(auto_attribs=True)
# class Auto:
#     b: int
#     _parent: Optional['Auto'] = None
#
#     def stuff(self) -> int:
#         return self.b
#
#
# @attr.s(init=False, auto_attribs=True)
# class NoInit:
#     b: int
#
#     def __init__(self, b: int = 18) -> None:
#         pass
#
#
# @attr.s
# class UnTyped:
#     b = attr.ib()
#     c = attr.ib(default=18)
#
#
# if __name__ == "__main__":
#     Auto(7, None)
#     Auto(18, Auto(7, None))
#     a = Auto(7, None)
#     b = Auto(8, None)
#
#     if a > b:
#         print("yay")
