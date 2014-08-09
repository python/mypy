import asyncio
from asyncio import Future

@asyncio.coroutine
def compute(x: int, y: int) -> 'Future[int]':
    """
    That function will return a int, but can be "yielded from", so
    the type is Future[int]
    The return type (int) will be wrapped into a Future.
    """
    print("Compute %s + %s ..." % (x, y))
    yield from asyncio.sleep(1.0)
    return x + y   # Here the int is wrapped in Future[int]

@asyncio.coroutine
def print_sum(x: int, y: int) -> 'Future[None]':
    """
    Don't return nothing, but can be "yielded from", so is a Future.
    """
    result = yield from compute(x, y)  # The type of result will be int (is extracted from Future[int]
    print("%s + %s = %s" % (x, y, result))

loop = asyncio.get_event_loop()
loop.run_until_complete(print_sum(1, 2))
loop.close()
