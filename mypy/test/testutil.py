from typing import Iterator, List, Tuple, IO
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


@skipUnless(WIN32, "only relevant for Windows")
class WindowsReplace(TestCase):
    tmpdir = tempfile.TemporaryDirectory(prefix='mypy-test-',
                                         dir=os.path.abspath('tmp-test-dirs'))
    # Choose timeout value that would ensure actual wait inside util.replace is close to timeout
    timeout = 0.0009 * 2 ** 10
    short_lock = timeout / 4
    long_lock = timeout * 2

    threads = []  # type: List[Thread]

    @classmethod
    def close_file_after(cls, file: IO, delay: float) -> Thread:
        """Start a background thread to close file after delay sec."""
        def _close_file_after() -> None:
            time.sleep(delay)
            file.close()

        t = Thread(target=_close_file_after, daemon=True)
        cls.threads.append(t)
        t.start()
        return t

    @classmethod
    def tearDownClass(cls) -> None:
        # Need to wait for threads to complete, otherwise we'll get PermissionError
        # at the end (whether tmpdir goes out of scope or we explicitly call cleanup).
        for t in cls.threads:
            t.join()
        cls.tmpdir.cleanup()

    def prepare_src_dest(self, src_lock_duration: float, dest_lock_duration: float
                         ) -> Tuple[str, str]:
        """Create two files in self.tmpdir random names (src, dest) and unique contents;
        then spawn two threads that lock each of them for a specified duration.

        Return a tuple (src, dest).
        """
        src = os.path.join(self.tmpdir.name, random_string())
        dest = os.path.join(self.tmpdir.name, random_string())

        for fname, delay in zip((src, dest), (src_lock_duration, dest_lock_duration)):
            f = open(fname, 'w')
            f.write(fname)
            if delay:
                self.close_file_after(f, delay)
            else:
                f.close()

        return src, dest

    def replace_ok(self, src_lock_duration: float, dest_lock_duration: float,
                   timeout: float) -> None:
        """Check whether util._replace, called with a specified timeout,
        worked successfully on two newly created files locked for specified
        durations.

        Return True if the replacement succeeded.
        """
        src, dest = self.prepare_src_dest(src_lock_duration, dest_lock_duration)
        util._replace(src, dest, timeout=timeout)
        # Note that dest handle may still be open but reading from it is ok.
        with open(dest) as f:
            self.assertEqual(f.read(), src, 'replace failed')

    def test_no_locks(self) -> None:
        # No files locked.
        self.replace_ok(0, 0, self.timeout)

    def test_original_problem(self) -> None:
        # Make sure we can reproduce https://github.com/python/mypy/issues/3215 with our setup.
        src, dest = self.prepare_src_dest(self.short_lock, 0)
        with self.assertRaises(PermissionError):
            os.replace(src, dest)

    def test_short_locks(self) -> None:
        # Lock files for a time short enough that util.replace won't timeout.
        self.replace_ok(self.short_lock, 0, self.timeout)
        self.replace_ok(0, self.short_lock, self.timeout)

    def test_long_locks(self) -> None:
        # Lock files for a time long enough that util.replace times out.
        with self.assertRaises(PermissionError):
            self.replace_ok(self.long_lock, 0, self.timeout)
        with self.assertRaises(PermissionError):
            self.replace_ok(0, self.long_lock, self.timeout)


if __name__ == '__main__':
    main()
