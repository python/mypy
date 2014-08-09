"""
In this example, we have a coroutine function that is wrapped in a Task.
We also have a Future[str] with a callback function.
"""
import typing
import asyncio
from asyncio import Future, AbstractEventLoop

@asyncio.coroutine
def slow_operation(future: 'Future[str]') -> 'Future[None]':
    """
    Simple coroutine (explained in examples before)
    """
    yield from asyncio.sleep(1)
    future.set_result('Future is done!')

def got_result(future: 'Future[int]') -> None:
    """
    We say that we are expecting a Future[int]
    but is assigned to a Future[str], so fails in the add_done_callback()
    """
    print(future.result())
    loop.stop()

loop = asyncio.get_event_loop() # type: AbstractEventLoop
future = asyncio.Future()  # type: Future[str]
asyncio.Task(slow_operation(future))  # Here create a task with the function. (The Task need a Future[T] as first argument)
future.add_done_callback(got_result)  # E: Argument 1 to "add_done_callback" of "Future" has incompatible type Function[[Future[int]] -> None]; expected Function[[Future[str]] -> "Any"]

try:
    loop.run_forever()
finally:
    loop.close()
