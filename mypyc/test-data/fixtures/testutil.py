# Simple support library for our run tests.

from contextlib import contextmanager
from typing import Iterator, TypeVar, Generator, Optional, List, Tuple, Sequence, Union

@contextmanager
def assertRaises(typ: type, msg: str = '') -> Iterator[None]:
    try:
        yield
    except Exception as e:
        assert isinstance(e, typ), f"{e} is not a {typ.__name__}"
        assert msg in str(e), f'Message "{e}" does not match "{msg}"'
    else:
        assert False, f"Expected {typ.__name__} but got no exception"

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
