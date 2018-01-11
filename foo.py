import attr
import typing


@attr.s(cmp=False)
class A:
    x = attr.ib()

a = A()

A() == A()

import pdb; pdb.set_trace()

@attr.s(auto_attribs=True)
class Auto:
    normal: int
    _private: int
    def_arg: int = 18
    _def_kwarg: int = attr.ib(validator=None, default=18)

    FOO: typing.ClassVar[int] = 18

# reveal_type(Auto)
Auto(1, 2, 3)


@attr.s
class Typed:
    normal: int = attr.ib()
    _private: int = attr.ib()
    def_arg: int = attr.ib(18)
    _def_kwarg: int = attr.ib(validator=None, default=18)

    FOO: int = 18

# reveal_type(Typed)
Typed(1, 2, 3)


@attr.s
class UnTyped:
    normal = attr.ib()
    _private = attr.ib()
    def_arg = attr.ib(18)
    _def_kwarg = attr.ib(validator=None, default=18)

    FOO = 18

    def __cmp__(self, other):
        ...

    def __lt__(self, other):
        ...


# reveal_type(UnTyped)
# reveal_type(UnTyped.FOO)
UnTyped(1, 2, 3)

x = UnTyped(1, 2, 3)
y = UnTyped(2, 3, 4)

print(UnTyped(1, 2, 3) == UnTyped(1, 2, 3))
print(x < y)
