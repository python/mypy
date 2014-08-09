"""
Simple example about the Future instance.
At Future[str] is declared out and passed to the function.
Inside the function the result is setted to a str.
"""

import asyncio
from asyncio import Future

@asyncio.coroutine
def slow_operation(future: 'Future[str]') -> 'Future[None]':
    yield from asyncio.sleep(1)
    future.set_result('Future is done!')

loop = asyncio.get_event_loop()
future = asyncio.Future()  # type: Future[str]
asyncio.Task(slow_operation(future))
loop.run_until_complete(future)
print(future.result())
loop.close()
