"""
Example with concatenated Futures.
The function return type always have one more Future[].
"""
import typing
import asyncio
from asyncio import Future

@asyncio.coroutine
def h4() -> 'Future[Future[int]]':
    yield from asyncio.sleep(1)
    f = asyncio.Future() #type: Future[int]
    return f

@asyncio.coroutine
def h3() -> 'Future[Future[Future[int]]]':
    x = yield from h4()
    x.set_result(42)
    f = asyncio.Future() #type: Future[Future[int]]
    f.set_result(x)
    return f

@asyncio.coroutine
def h() -> 'Future[None]':
    print("Before")
    x = yield from h3()
    y = yield from x
    z = yield from y
    print(z)
    print(y)
    print(x)

loop = asyncio.get_event_loop()
loop.run_until_complete(h())
# loop.run_forever()
loop.close()
