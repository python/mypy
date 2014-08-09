"""
Example with multiple tasks.
"""
import typing
import asyncio
from asyncio import Task, Future
@asyncio.coroutine
def factorial(name, number) -> 'Future[None]':
    f = 1
    for i in range(2, number+1):
        print("Task %s: Compute factorial(%s)..." % (name, i))
        yield from asyncio.sleep(1)
        f *= i
    print("Task %s: factorial(%s) = %s" % (name, number, f))

loop = asyncio.get_event_loop()
tasks = [
    asyncio.Task(factorial("A", 2)),
    asyncio.Task(factorial("B", 3)),
    asyncio.Task(factorial("C", 4))]
loop.run_until_complete(asyncio.wait(tasks))
loop.close()
