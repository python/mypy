# Simple support library for our run tests.

from contextlib import contextmanager
from collections.abc import Iterator
import math
import sys
from typing import (
    Any, Iterator, TypeVar, Generator, Optional, List, Tuple, Sequence,
    Union, Callable, Awaitable, Generic
)
from typing import Final

FLOAT_MAGIC: Final = -113.0

# Various different float values
float_vals = [
    float(n) * 0.25 for n in range(-10, 10)
] + [
    -0.0,
    1.0/3.0,
    math.sqrt(2.0),
    1.23e200,
    -2.34e200,
    5.43e-100,
    -6.532e-200,
    float('inf'),
    -float('inf'),
    float('nan'),
    FLOAT_MAGIC,
    math.pi,
    2.0 * math.pi,
    math.pi / 2.0,
    -math.pi / 2.0,
    -1.7976931348623158e+308,  # Smallest finite value
    -2.2250738585072014e-308,  # Closest to zero negative normal value
    -7.5491e-312,              # Arbitrary negative subnormal value
    -5e-324,                   # Closest to zero negative subnormal value
    1.7976931348623158e+308,   # Largest finite value
    2.2250738585072014e-308,   # Closest to zero positive normal value
    -6.3492e-312,              # Arbitrary positive subnormal value
    5e-324,                    # Closest to zero positive subnormal value
]

@contextmanager
def assertRaises(typ: type, msg: str = '') -> Iterator[None]:
    try:
        yield
    except BaseException as e:
        assert type(e) is typ, f"{e!r} is not a {typ.__name__}"
        assert msg in str(e), f'Message "{e}" does not match "{msg}"'
    else:
        assert False, f"Expected {typ.__name__} but got no exception"

def assertDomainError() -> Any:
    return assertRaises(ValueError, "math domain error")

def assertMathRangeError() -> Any:
    return assertRaises(OverflowError, "math range error")

T = TypeVar('T')
U = TypeVar('U')
V = TypeVar('V')

def run_generator(gen: Generator[T, V, U],
                  inputs: Optional[List[V]] = None,
                  p: bool = False) -> Tuple[Sequence[T], Union[U, str]]:
    res: List[T] = []
    i = -1
    while True:
        try:
            if i >= 0 and inputs:
                # ... fixtures don't have send
                val = gen.send(inputs[i])  # type: ignore
            elif not hasattr(gen, '__next__'):  # type: ignore
                val = gen.send(None)  # type: ignore
            else:
                val = next(gen)
        except StopIteration as e:
            return (tuple(res), e.value)
        except Exception as e:
            return (tuple(res), str(e))
        if p:
            print(val)
        res.append(val)
        i += 1

F = TypeVar('F', bound=Callable)

# Result codes of CPython's C-level send protocol (PySendResult).
PYGEN_RETURN: Final = 0
PYGEN_ERROR: Final = -1
PYGEN_NEXT: Final = 1


def pyiter_send(it: Any, arg: Any) -> Tuple[int, Any]:
    """Resume an iterator using PyIter_Send, the C-level send protocol.

    This calls the am_send slot, if the type of 'it' has one, so it's the only way to
    exercise am_send from Python. It's the path asyncio's C Task and compiled
    'await'/'yield from' use to resume a generator or coroutine. Note that the
    interpreter's own SEND opcode does not use it on Python 3.12 and later.

    Return (result code, value), where the code is PYGEN_NEXT for a yielded value and
    PYGEN_RETURN for normal completion -- completion is reported without raising
    StopIteration. If the iterator raises, the exception propagates, since ctypes
    re-raises whatever exception is pending after the call.
    """
    import ctypes

    send = ctypes.pythonapi.PyIter_Send
    send.argtypes = [ctypes.py_object, ctypes.py_object, ctypes.POINTER(ctypes.py_object)]
    send.restype = ctypes.c_int
    result = ctypes.py_object()
    code = send(it, arg, ctypes.byref(result))
    assert code in (PYGEN_NEXT, PYGEN_RETURN), f"unexpected PySendResult {code}"
    try:
        value = result.value
    except ValueError:
        assert False, f"PyIter_Send returned {code} but left *result NULL"
    return code, value


class async_val(Awaitable[V], Generic[T, V]):
    def __init__(self, val: T) -> None:
        self.val = val

    def __await__(self) -> Generator[T, V, V]:
        z = yield self.val
        return z


# Wrap a mypyc-generated function in a real python function, to allow it to be
# stuck into classes and the like.
def make_python_function(f: F) -> F:
    def g(*args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)
    return g  # type: ignore


def is_gil_disabled() -> bool:
    return hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled()


def is_64_bit_platform() -> bool:
    return getattr(sys, "maxsize") > 2**32
