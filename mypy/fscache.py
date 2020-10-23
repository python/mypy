"""Interface for accessing the file system with automatic caching.

The idea is to cache the results of any file system state reads during
a single transaction. This has two main benefits:

* This avoids redundant syscalls, as we won't perform the same OS
  operations multiple times.

* This makes it easier to reason about concurrent FS updates, as different
  operations targeting the same paths can't report different state during
  a transaction.

Note that this only deals with reading state, not writing.

Properties maintained by the API:

* The contents of the file are always from the same or later time compared
  to the reported mtime of the file, even if mtime is queried after reading
  a file.

* Repeating an operation produces the same result as the first one during
  a transaction.

* Call flush() to start a new transaction (flush the caches).

The API is a bit limited. It's easy to add new cached operations, however.
You should perform all file system reads through the API to actually take
advantage of the benefits.
"""

import os
import stat
from typing import Dict, List
from mypy.util import hash_digest


class FileSystemCache:
    def __init__(self) -> None:
        self.flush()

    def flush(self) -> None:
        """Start another transaction and empty all caches."""
        self.stat_cache = {}  # type: Dict[str, os.stat_result]
        self.stat_error_cache = {}  # type: Dict[str, OSError]
        self.listdir_cache = {}  # type: Dict[str, List[str]]
        self.listdir_error_cache = {}  # type: Dict[str, OSError]
        self.isfile_case_cache = {}  # type: Dict[str, bool]
        self.read_cache = {}  # type: Dict[str, bytes]
        self.read_error_cache = {}  # type: Dict[str, Exception]
        self.hash_cache = {}  # type: Dict[str, str]

    def stat(self, path: str) -> os.stat_result:
        if path in self.stat_cache:
            return self.stat_cache[path]
        if path in self.stat_error_cache:
            raise copy_os_error(self.stat_error_cache[path])
        try:
            st = os.stat(path)
        except OSError as err:
            # Take a copy to get rid of associated traceback and frame objects.
            # Just assigning to __traceback__ doesn't free them.
            self.stat_error_cache[path] = copy_os_error(err)
            raise err
        self.stat_cache[path] = st
        return st

    def listdir(self, path: str) -> List[str]:
        path = os.path.normpath(path)
        if path in self.listdir_cache:
            return self.listdir_cache[path]
        if path in self.listdir_error_cache:
            raise copy_os_error(self.listdir_error_cache[path])
        try:
            results = os.listdir(path)
        except OSError as err:
            # Like above, take a copy to reduce memory use.
            self.listdir_error_cache[path] = copy_os_error(err)
            raise err
        self.listdir_cache[path] = results
        return results

    def isfile(self, path: str) -> bool:
        try:
            st = self.stat(path)
        except OSError:
            return False
        return stat.S_ISREG(st.st_mode)

    def isfile_case(self, path: str, prefix: str) -> bool:
        """Return whether path exists and is a file.

        On case-insensitive filesystems (like Mac or Windows) this returns
        False if the case of path's last component does not exactly match
        the case found in the filesystem.

        We check also the case of other path components up to prefix.
        For example, if path is 'user-stubs/pack/mod.pyi' and prefix is 'user-stubs',
        we check that the case of 'pack' and 'mod.py' matches exactly, 'user-stubs' will be
        case insensitive on case insensitive filesystems.

        The caller must ensure that prefix is a valid file system prefix of path.
        """
        if path in self.isfile_case_cache:
            return self.isfile_case_cache[path]
        head, tail = os.path.split(path)
        if not tail:
            res = False
        else:
            try:
                names = self.listdir(head)
                # This allows one to check file name case sensitively in
                # case-insensitive filesystems.
                res = tail in names and self.isfile(path)
            except OSError:
                res = False

        # Also check the other path components in case sensitive way.
        head, dir = os.path.split(head)
        while res and head and dir and head.startswith(prefix):
            try:
                res = dir in self.listdir(head)
            except OSError:
                res = False
            head, dir = os.path.split(head)

        self.isfile_case_cache[path] = res
        return res

    def isdir(self, path: str) -> bool:
        try:
            st = self.stat(path)
        except OSError:
            return False
        return stat.S_ISDIR(st.st_mode)

    def exists(self, path: str) -> bool:
        try:
            self.stat(path)
        except FileNotFoundError:
            return False
        return True

    def read(self, path: str) -> bytes:
        if path in self.read_cache:
            return self.read_cache[path]
        if path in self.read_error_cache:
            raise self.read_error_cache[path]

        # Need to stat first so that the contents of file are from no
        # earlier instant than the mtime reported by self.stat().
        self.stat(path)

        dirname, basename = os.path.split(path)
        dirname = os.path.normpath(dirname)
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError as err:
            self.read_error_cache[path] = err
            raise

        self.read_cache[path] = data
        self.hash_cache[path] = hash_digest(data)
        return data

    def hash_digest(self, path: str) -> str:
        if path not in self.hash_cache:
            self.read(path)
        return self.hash_cache[path]

    def samefile(self, f1: str, f2: str) -> bool:
        s1 = self.stat(f1)
        s2 = self.stat(f2)
        return os.path.samestat(s1, s2)


def copy_os_error(e: OSError) -> OSError:
    new = OSError(*e.args)
    new.errno = e.errno
    new.strerror = e.strerror
    new.filename = e.filename
    if e.filename2:
        new.filename2 = e.filename2
    return new
