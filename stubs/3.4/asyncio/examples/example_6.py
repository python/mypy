"""
Example with concatenated coroutines.
"""
import typing
import asyncio
from asyncio import Future

@asyncio.coroutine
def h4() -> 'Future[int]':
    x = yield from future
    return x

@asyncio.coroutine
def h3() -> 'Future[int]':
    x = yield from h4()
    print("h3: %s" % x)
    return x

@asyncio.coroutine
def h2() -> 'Future[int]':
    x = yield from h3()
    print("h2: %s" % x)
    return x

@asyncio.coroutine
def h() -> 'Future[None]':
    x = yield from h2()
    print("h: %s" % x)

loop = asyncio.get_event_loop()
future = asyncio.Future()  # type: Future[int]
future.set_result(42)
loop.run_until_complete(h())
print("Outside %s" % future.result())
loop.close()
