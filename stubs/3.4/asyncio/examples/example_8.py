"""
Example with a Future that have an own class
as type (Future[A])
"""
import typing
import asyncio
from asyncio import Future

class A:
    def __init__(self, x: int) -> None:
        self.x = x


@asyncio.coroutine
def h() -> 'Future[None]':
    x = yield from future
    print("h: %s" % x.x)


loop = asyncio.get_event_loop()
future = asyncio.Future()  # type: Future[A]
future.set_result(A(42))
loop.run_until_complete(h())
print("Outside %s" % future.result().x)
loop.close()
