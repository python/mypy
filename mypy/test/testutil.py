from typing import Iterator
import time
import os
import sys
import tempfile
from contextlib import contextmanager
from threading import Thread
from unittest import TestCase, main, skipUnless
from mypy import util


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
    tmpdir = tempfile.TemporaryDirectory(prefix='mypy-test-',
                                         dir=os.path.abspath('tmp-test-dirs'))
    src = os.path.join(tmpdir.name, 'tmp1')
    dest = os.path.join(tmpdir.name, 'tmp2')

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmpdir.cleanup()

    def setUp(self) -> None:
        # create two temporary files
        for fname in (self.src, self.dest):
            with open(fname, 'w') as f:
                f.write(fname)

    def replace_ok(self) -> None:
        util._replace(self.src, self.dest, timeout=0.25)
        self.assertEqual(open(self.dest).read(), self.src, 'replace failed')

    def test_normal(self) -> None:
        self.replace_ok()

    def test_problem_exists(self) -> None:
        with lock_file(self.src, 0.1):
            with self.assertRaises(PermissionError):
                os.replace(self.src, self.dest)

    def test_short_lock_src(self) -> None:
        with lock_file(self.src, 0.1):
            self.replace_ok()

    def test_short_lock_dest(self) -> None:
        with lock_file(self.dest, 0.1):
            self.replace_ok()

    def test_long_lock_src(self) -> None:
        with lock_file(self.src, 0.4):
            with self.assertRaises(PermissionError):
                self.replace_ok()

    def test_long_lock_dest(self) -> None:
        with lock_file(self.dest, 0.4):
            with self.assertRaises(PermissionError):
                self.replace_ok()


if __name__ == '__main__':
    main()
