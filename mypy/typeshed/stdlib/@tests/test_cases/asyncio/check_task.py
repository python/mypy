from __future__ import annotations

import asyncio


class Waiter:
    def __init__(self) -> None:
        self.tasks: list[asyncio.Task[object]] = []

    def add(self, t: asyncio.Task[object]) -> None:
        self.tasks.append(t)

    async def join(self) -> None:
        await asyncio.wait(self.tasks)


async def foo() -> int:
    return 42


async def main() -> None:
    # asyncio.Task is covariant in its type argument, which is unusual since its parent class
    # asyncio.Future is invariant in its type argument. This is only sound because asyncio.Task
    # is not actually Liskov substitutable for asyncio.Future: it does not implement set_result.
    w = Waiter()
    t: asyncio.Task[int] = asyncio.create_task(foo())
    w.add(t)
    await w.join()
