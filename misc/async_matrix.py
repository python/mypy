#!/usr/bin/env python3
"""Test various combinations of generators/coroutines.

This was used to cross-check the errors in the test case
testFullCoroutineMatrix in test-data/unit/check-async-await.test.
"""

import sys
from types import coroutine
from typing import Any, Awaitable, Generator, Iterator

# The various things you might try to use in `await` or `yield from`.

def plain_generator() -> Generator[str, None, int]:
    yield 'a'
    return 1

async def plain_coroutine() -> int:
    return 1

@coroutine
def decorated_generator() -> Generator[str, None, int]:
    yield 'a'
    return 1

@coroutine
async def decorated_coroutine() -> int:
    return 1

class It(Iterator[str]):
    stop = False
    def __iter__(self) -> 'It':
        return self
    def __next__(self) -> str:
        if self.stop:
            raise StopIteration('end')
        else:
            self.stop = True
            return 'a'

def other_iterator() -> It:
    return It()

class Aw(Awaitable[int]):
    def __await__(self) -> Generator[str, Any, int]:
        yield 'a'
        return 1

def other_coroutine() -> Aw:
    return Aw()

# The various contexts in which `await` or `yield from` might occur.

def plain_host_generator(func) -> Generator[str, None, None]:
    yield 'a'
    x = 0
    f = func()
    try:
        x = yield from f
    finally:
        try:
            f.close()
        except AttributeError:
            pass

async def plain_host_coroutine(func) -> None:
    x = 0
    x = await func()

@coroutine
def decorated_host_generator(func) -> Generator[str, None, None]:
    yield 'a'
    x = 0
    f = func()
    try:
        x = yield from f
    finally:
        try:
            f.close()
        except AttributeError:
            pass

@coroutine
async def decorated_host_coroutine(func) -> None:
    x = 0
    x = await func()

# Main driver.

def main():
    verbose = ('-v' in sys.argv)
    for host in [plain_host_generator, plain_host_coroutine,
                 decorated_host_generator, decorated_host_coroutine]:
        print()
        print("==== Host:", host.__name__)
        for func in [plain_generator, plain_coroutine,
                     decorated_generator, decorated_coroutine,
                     other_iterator, other_coroutine]:
            print("  ---- Func:", func.__name__)
            try:
                f = host(func)
                for i in range(10):
                    try:
                        x = f.send(None)
                        if verbose:
                            print("    yield:", x)
                    except StopIteration as e:
                        if verbose:
                            print("    stop:", e.value)
                        break
                else:
                    if verbose:
                        print("    ???? still going")
            except Exception as e:
                print("    error:", repr(e))

# Run main().

if __name__ == '__main__':
    main()
