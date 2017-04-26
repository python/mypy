from typing import Iterator, Tuple
import time
import os
import sys
import tempfile
from contextlib import contextmanager
from threading import Thread
from unittest import TestCase, main, skipUnless
from mypy import util
from mypy.build import random_string


WIN32 = sys.platform.startswith("win")


@contextmanager
def lock_file(filename: str, duration: float) -> Iterator[Thread]:
    '''
    Opens filename (which must exist) for reading
    After duration sec, releases the handle
    '''
    def _lock_file() -> None:
        with open(filename):
            time.sleep(duration)
    t = Thread(target=_lock_file, daemon=True)
    t.start()
    yield t
    t.join()


@skipUnless(WIN32, "only relevant for Windows")
class ReliableReplace(TestCase):
    # will be cleaned up automatically when this class goes out of scope
    tmpdir = tempfile.TemporaryDirectory(prefix='mypy-test-',
                                         dir=os.path.abspath('tmp-test-dirs'))
    timeout = 0.5
    short_lock = 0.2
    long_lock = 1

    @contextmanager
    def prepare_src_dest(self, src_lock_duration: float, dest_lock_duration: float
                         ) -> Iterator[Tuple[str, str]]:
        # create two temporary files
        src = os.path.join(self.tmpdir.name, random_string())
        dest = os.path.join(self.tmpdir.name, random_string())

        for fname in (src, dest):
            with open(fname, 'w') as f:
                f.write(fname)

        with lock_file(src, src_lock_duration):
            with lock_file(dest, dest_lock_duration):
                yield src, dest

    def replace_ok(self, src_lock_duration: float, dest_lock_duration: float,
                   timeout: float) -> None:
        with self.prepare_src_dest(src_lock_duration, dest_lock_duration) as (src, dest):
            util._replace(src, dest, timeout=timeout)
            self.assertEqual(open(dest).read(), src, 'replace failed')

    def test_normal(self) -> None:
        self.replace_ok(0, 0, self.timeout)

    def test_problem_exists(self) -> None:
        with self.prepare_src_dest(self.short_lock, 0) as (src, dest):
            with self.assertRaises(PermissionError):
                os.replace(src, dest)

    def test_short_lock(self) -> None:
        self.replace_ok(self.short_lock, 0, self.timeout)
        self.replace_ok(0, self.short_lock, self.timeout)

    def test_long_lock(self) -> None:
        with self.assertRaises(PermissionError):
            self.replace_ok(self.long_lock, 0, self.timeout)
        with self.assertRaises(PermissionError):
            self.replace_ok(0, self.long_lock, self.timeout)


if __name__ == '__main__':
    main()
