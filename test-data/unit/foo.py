from typing import Tuple

import attr


@attr.s(auto_attribs=True)
class A:
    bar: int
    baz: str

reveal_type(A.__attrs_attrs__)
reveal_type(A.__attrs_attrs__[0])
reveal_type(A.__attrs_attrs__[1])
reveal_type(A.__attrs_attrs__[2])



t: Tuple[int, ...]
reveal_type(t)
t2: Tuple[int, str]
reveal_type(t2)

