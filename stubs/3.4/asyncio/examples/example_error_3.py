"""
Errors about futures.
slow_operation() is the only function that will work.
The other three have errors.
"""

import asyncio
from asyncio import Future

@asyncio.coroutine
def slow_operation(future: 'Future[str]') -> 'Future[None]':
    """
    This function is OK.
    """
    yield from asyncio.sleep(1)
    future.set_result('42')

@asyncio.coroutine
def slow_operation_2(future: 'Future[str]') -> 'Future[None]':
    """
    This function fail trying to set an int as result.
    """
    yield from asyncio.sleep(1)
    future.set_result(42)  #Try to set an int as result to a Future[str]

@asyncio.coroutine
def slow_operation_3(future: 'Future[int]') -> 'Future[None]':
    """
    This function fail because try to get a Future[int] and a Future[str]
    is given.
    """
    yield from asyncio.sleep(1)
    future.set_result(42)


@asyncio.coroutine
def slow_operation_4(future: 'Future[int]') -> 'Future[None]':
    """
    This function fail because try to get a Future[int] and a Future[str]
    is given.
    This function fail trying to set an str as result.
    """
    yield from asyncio.sleep(1)
    future.set_result('42')  #Try to set an str as result to a Future[int]

loop = asyncio.get_event_loop()
future = asyncio.Future()  # type: Future[str]
future2 = asyncio.Future()  # type: Future[str]
future3 = asyncio.Future()  # type: Future[str]
future4 = asyncio.Future()  # type: Future[str]
asyncio.Task(slow_operation(future))
asyncio.Task(slow_operation_2(future2))
asyncio.Task(slow_operation_3(future3))
asyncio.Task(slow_operation_4(future4))
loop.run_until_complete(future)
print(future.result())
loop.close()
