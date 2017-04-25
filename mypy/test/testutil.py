import sys
from typing import Type, Callable, List
import time
try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc  # type: ignore # PY32 and earlier
from unittest import TestCase, main, skipUnless
from mypy import util


def create_bad_function(lag: float, exc: BaseException) -> Callable[[], None]:
    start_time = time.perf_counter()

    def f() -> None:
        if time.perf_counter() - start_time < lag:
            raise exc
        else:
            return
    return f


def create_funcs() -> List[Callable[[], None]]:

    def linux_function() -> None: pass
    windows_function1 = create_bad_function(0.1, PermissionError())
    windows_function2 = create_bad_function(0.2, FileExistsError())
    return [windows_function1, windows_function2, linux_function]


class WaitRetryTests(TestCase):
    def test_waitfor(self) -> None:
        with self.assertRaises(OSError):
            util.wait_for(create_funcs(), (PermissionError, FileExistsError), 0.1)
        util.wait_for(create_funcs(), (PermissionError, FileExistsError), 1)
        util.wait_for(create_funcs(), (OSError,), 1)
        with self.assertRaises(FileExistsError):
            util.wait_for(create_funcs(), (PermissionError,), 0.4)


if __name__ == '__main__':
    main()
