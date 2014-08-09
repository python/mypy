from typing import Any
import asyncio
from asyncio import Future

@asyncio.coroutine
def greet() -> 'Future[None]':
    """
    The function don't return nothing, but is a coroutine, so the
    type is Future[None].
    """
    yield from asyncio.sleep(2)
    print('Hello World')

@asyncio.coroutine
def test() -> 'Future[None]':
    """
    The type of greet() is Future[None], so, we can do "yield from greet()"
    but we can't do "x = yield from greet()", because the function don't return nothing,
    we can't assign to a variable.
    """
    yield from greet()
    x = yield from greet()  # E: Function does not return a value

loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(test())
finally:
    loop.close()
