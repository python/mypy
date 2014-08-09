from typing import Any
import asyncio
from asyncio import Future

@asyncio.coroutine
def greet_every_two_seconds() -> 'Future[None]':
    """
    That function won't return nothing, but can be applied to
    yield from or sended to the main_loop (run_until_complete in this case)
    for that reason, the type is Future[None]
    """
    while True:
        print('Hello World')
        yield from asyncio.sleep(2)

loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(greet_every_two_seconds())
finally:
    loop.close()
