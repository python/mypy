from __future__ import annotations

from contextlib import ExitStack
from typing_extensions import assert_type


# See issue #7961
class Thing(ExitStack):
    pass


stack = ExitStack()
thing = Thing()
assert_type(stack.enter_context(Thing()), Thing)
assert_type(thing.enter_context(ExitStack()), ExitStack)

with stack as cm:
    assert_type(cm, ExitStack)
with thing as cm2:
    assert_type(cm2, Thing)
