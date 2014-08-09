"""
Simple error about return types.
The function return type is Future[int]
we are trying to return a str (that is wrapped in a Future[str])
and the type-check fail.
"""
import asyncio
from asyncio import Future

@asyncio.coroutine
def compute(x: int, y: int) -> 'Future[int]':
    """
    This function will try to return a str, will be wrapped in a Future[str] and
    will fail the type check with Future[int]
    """
    print("Compute %s + %s ..." % (x, y))
    yield from asyncio.sleep(1.0)
    return str(x + y)   # E: Incompatible return value type: expected asyncio.futures.Future[builtins.int], got asyncio.futures.Future[builtins.str]

@asyncio.coroutine
def print_sum(x: int, y: int) -> 'Future[None]':
    """
    Don't return nothing, but is a coroutine, so is a Future.
    """
    result = yield from compute(x, y)
    print("%s + %s = %s" % (x, y, result))

loop = asyncio.get_event_loop()
loop.run_until_complete(print_sum(1, 2))
loop.close()
