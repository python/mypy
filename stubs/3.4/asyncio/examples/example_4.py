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

def got_result(future: 'Future[str]') -> None:
    """
    This is a normal function, so it's not a Future.
    This function is setted as callback to the future,
    the type of the callback functions is:
        Function[[Future[T]], Any]
    """
    print(future.result())
    loop.stop()

loop = asyncio.get_event_loop() # type: AbstractEventLoop
future = asyncio.Future()  # type: Future[str]
asyncio.Task(slow_operation(future))  # Here create a task with the function. (The Task need a Future[T] as first argument)
future.add_done_callback(got_result)  # and assignt the callback to the future
try:
    loop.run_forever()
finally:
    loop.close()
