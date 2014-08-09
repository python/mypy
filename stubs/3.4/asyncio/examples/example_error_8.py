"""
An error because we try to say that we get a 'B' type in the yield from future,
when we are getting an 'A' type
"""
import typing
import asyncio
from asyncio import Future


class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B:
    def __init__(self, x: int) -> None:
        self.x = x


@asyncio.coroutine
def h() -> 'Future[None]':
    x = yield from future # type: B # E: Incompatible types in assignment (expression has type "A", variable has type "B")
    print("h: %s" % x.x)


loop = asyncio.get_event_loop()
future = asyncio.Future()  # type: Future[A]
future.set_result(A(42))
loop.run_until_complete(h())
print("Outside %s" % future.result().x)
loop.close()
