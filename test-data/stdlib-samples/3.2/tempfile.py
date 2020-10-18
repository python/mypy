"""Temporary files.

This module provides generic, low- and high-level interfaces for
creating temporary files and directories.  The interfaces listed
as "safe" just below can be used without fear of race conditions.
Those listed as "unsafe" cannot, and are provided for backward
compatibility only.

This module also provides some data items to the user:

  TMP_MAX  - maximum number of names that will be tried before
             giving up.
  template - the default prefix for all temporary names.
             You may change this to control the default prefix.
  tempdir  - If this is set to a string before the first use of
             any routine from this module, it will be considered as
             another candidate location to store temporary files.
"""

__all__ = [
    "NamedTemporaryFile", "TemporaryFile", # high level safe interfaces
    "SpooledTemporaryFile", "TemporaryDirectory",
    "mkstemp", "mkdtemp",                  # low level safe interfaces
    "mktemp",                              # deprecated unsafe interface
    "TMP_MAX", "gettempprefix",            # constants
    "tempdir", "gettempdir"
   ]


# Imports.

import warnings as _warnings
import sys as _sys
import io as _io
import os as _os
import errno as _errno
from random import Random as _Random

from typing import (
    Any as _Any, Callable as _Callable, Iterator as _Iterator,
    List as _List, Tuple as _Tuple, Dict as _Dict, Iterable as _Iterable,
    IO as _IO, cast as _cast, Optional as _Optional, Type as _Type,
)
from typing_extensions import Literal
from types import TracebackType as _TracebackType

try:
    import fcntl as _fcntl
except ImportError:
    def _set_cloexec(fd: int) -> None:
        pass
else:
    def _set_cloexec(fd: int) -> None:
        try:
            flags = _fcntl.fcntl(fd, _fcntl.F_GETFD, 0)
        except IOError:
            pass
        else:
            # flags read successfully, modify
            flags |= _fcntl.FD_CLOEXEC
            _fcntl.fcntl(fd, _fcntl.F_SETFD, flags)


try:
    import _thread
    _allocate_lock = _thread.allocate_lock # type: _Callable[[], _Any]
except ImportError:
    import _dummy_thread
    _allocate_lock = _dummy_thread.allocate_lock

_text_openflags = _os.O_RDWR | _os.O_CREAT | _os.O_EXCL
if hasattr(_os, 'O_NOINHERIT'):
    _text_openflags |= _os.O_NOINHERIT
if hasattr(_os, 'O_NOFOLLOW'):
    _text_openflags |= _os.O_NOFOLLOW

_bin_openflags = _text_openflags
if hasattr(_os, 'O_BINARY'):
    _bin_openflags |= _os.O_BINARY

if hasattr(_os, 'TMP_MAX'):
    TMP_MAX = _os.TMP_MAX
else:
    TMP_MAX = 10000

template = "tmp"

# Internal routines.

_once_lock = _allocate_lock()

if hasattr(_os, "lstat"):
    _stat = _os.lstat # type: _Callable[[str], object]
elif hasattr(_os, "stat"):
    _stat = _os.stat
else:
    # Fallback.  All we need is something that raises os.error if the
    # file doesn't exist.
    def __stat(fn: str) -> object:
        try:
            f = open(fn)
        except IOError:
            raise _os.error()
        f.close()
        return None
    _stat = __stat

def _exists(fn: str) -> bool:
    try:
        _stat(fn)
    except _os.error:
        return False
    else:
        return True

class _RandomNameSequence(_Iterator[str]):
    """An instance of _RandomNameSequence generates an endless
    sequence of unpredictable strings which can safely be incorporated
    into file names.  Each string is six characters long.  Multiple
    threads can safely use the same instance at the same time.

    _RandomNameSequence is an iterator."""

    characters = "abcdefghijklmnopqrstuvwxyz0123456789_"

    @property
    def rng(self) -> _Random:
        cur_pid = _os.getpid()
        if cur_pid != getattr(self, '_rng_pid', None):
            self._rng = _Random()
            self._rng_pid = cur_pid
        return self._rng

    def __iter__(self) -> _Iterator[str]:
        return self

    def __next__(self) -> str:
        c = self.characters
        choose = self.rng.choice
        letters = [choose(c) for dummy in "123456"]
        return ''.join(letters)

def _candidate_tempdir_list() -> _List[str]:
    """Generate a list of candidate temporary directories which
    _get_default_tempdir will try."""

    dirlist = [] # type: _List[str]

    # First, try the environment.
    for envname in 'TMPDIR', 'TEMP', 'TMP':
        dirname = _os.getenv(envname)
        if dirname: dirlist.append(dirname)

    # Failing that, try OS-specific locations.
    if _os.name == 'nt':
        dirlist.extend([ r'c:\temp', r'c:\tmp', r'\temp', r'\tmp' ])
    else:
        dirlist.extend([ '/tmp', '/var/tmp', '/usr/tmp' ])

    # As a last resort, the current directory.
    try:
        dirlist.append(_os.getcwd())
    except (AttributeError, _os.error):
        dirlist.append(_os.curdir)

    return dirlist

def _get_default_tempdir() -> str:
    """Calculate the default directory to use for temporary files.
    This routine should be called exactly once.

    We determine whether or not a candidate temp dir is usable by
    trying to create and write to a file in that directory.  If this
    is successful, the test file is deleted.  To prevent denial of
    service, the name of the test file must be randomized."""

    namer = _RandomNameSequence()
    dirlist = _candidate_tempdir_list()

    for dir in dirlist:
        if dir != _os.curdir:
            dir = _os.path.normcase(_os.path.abspath(dir))
        # Try only a few names per directory.
        for seq in range(100):
            name = next(namer)
            filename = _os.path.join(dir, name)
            try:
                fd = _os.open(filename, _bin_openflags, 0o600)
                fp = _io.open(fd, 'wb')
                fp.write(b'blat')
                fp.close()
                _os.unlink(filename)
                fp = fd = None
                return dir
            except (OSError, IOError) as e:
                if e.args[0] != _errno.EEXIST:
                    break # no point trying more names in this directory
                pass
    raise IOError(_errno.ENOENT,
                  "No usable temporary directory found in %s" % dirlist)

_name_sequence = None # type: _RandomNameSequence

def _get_candidate_names() -> _RandomNameSequence:
    """Common setup sequence for all user-callable interfaces."""

    global _name_sequence
    if _name_sequence is None:
        _once_lock.acquire()
        try:
            if _name_sequence is None:
                _name_sequence = _RandomNameSequence()
        finally:
            _once_lock.release()
    return _name_sequence


def _mkstemp_inner(dir: str, pre: str, suf: str,
                   flags: int) -> _Tuple[int, str]:
    """Code common to mkstemp, TemporaryFile, and NamedTemporaryFile."""

    names = _get_candidate_names()

    for seq in range(TMP_MAX):
        name = next(names)
        file = _os.path.join(dir, pre + name + suf)
        try:
            fd = _os.open(file, flags, 0o600)
            _set_cloexec(fd)
            return (fd, _os.path.abspath(file))
        except OSError as e:
            if e.errno == _errno.EEXIST:
                continue # try again
            raise

    raise IOError(_errno.EEXIST, "No usable temporary file name found")


# User visible interfaces.

def gettempprefix() -> str:
    """Accessor for tempdir.template."""
    return template

tempdir = None # type: str

def gettempdir() -> str:
    """Accessor for tempfile.tempdir."""
    global tempdir
    if tempdir is None:
        _once_lock.acquire()
        try:
            if tempdir is None:
                tempdir = _get_default_tempdir()
        finally:
            _once_lock.release()
    return tempdir

def mkstemp(suffix: str = "", prefix: str = template, dir: str = None,
            text: bool = False) -> _Tuple[int, str]:
    """User-callable function to create and return a unique temporary
    file.  The return value is a pair (fd, name) where fd is the
    file descriptor returned by os.open, and name is the filename.

    If 'suffix' is specified, the file name will end with that suffix,
    otherwise there will be no suffix.

    If 'prefix' is specified, the file name will begin with that prefix,
    otherwise a default prefix is used.

    If 'dir' is specified, the file will be created in that directory,
    otherwise a default directory is used.

    If 'text' is specified and true, the file is opened in text
    mode.  Else (the default) the file is opened in binary mode.  On
    some operating systems, this makes no difference.

    The file is readable and writable only by the creating user ID.
    If the operating system uses permission bits to indicate whether a
    file is executable, the file is executable by no one. The file
    descriptor is not inherited by children of this process.

    Caller is responsible for deleting the file when done with it.
    """

    if dir is None:
        dir = gettempdir()

    if text:
        flags = _text_openflags
    else:
        flags = _bin_openflags

    return _mkstemp_inner(dir, prefix, suffix, flags)


def mkdtemp(suffix: str = "", prefix: str = template, dir: str = None) -> str:
    """User-callable function to create and return a unique temporary
    directory.  The return value is the pathname of the directory.

    Arguments are as for mkstemp, except that the 'text' argument is
    not accepted.

    The directory is readable, writable, and searchable only by the
    creating user.

    Caller is responsible for deleting the directory when done with it.
    """

    if dir is None:
        dir = gettempdir()

    names = _get_candidate_names()

    for seq in range(TMP_MAX):
        name = next(names)
        file = _os.path.join(dir, prefix + name + suffix)
        try:
            _os.mkdir(file, 0o700)
            return file
        except OSError as e:
            if e.errno == _errno.EEXIST:
                continue # try again
            raise

    raise IOError(_errno.EEXIST, "No usable temporary directory name found")

def mktemp(suffix: str = "", prefix: str = template, dir: str = None) -> str:
    """User-callable function to return a unique temporary file name.  The
    file is not created.

    Arguments are as for mkstemp, except that the 'text' argument is
    not accepted.

    This function is unsafe and should not be used.  The file name
    refers to a file that did not exist at some point, but by the time
    you get around to creating it, someone else may have beaten you to
    the punch.
    """

##    from warnings import warn as _warn
##    _warn("mktemp is a potential security risk to your program",
##          RuntimeWarning, stacklevel=2)

    if dir is None:
        dir = gettempdir()

    names = _get_candidate_names()
    for seq in range(TMP_MAX):
        name = next(names)
        file = _os.path.join(dir, prefix + name + suffix)
        if not _exists(file):
            return file

    raise IOError(_errno.EEXIST, "No usable temporary filename found")


class _TemporaryFileWrapper:
    """Temporary file wrapper

    This class provides a wrapper around files opened for
    temporary use.  In particular, it seeks to automatically
    remove the file when it is no longer needed.
    """

    def __init__(self, file: _IO[_Any], name: str,
                 delete: bool = True) -> None:
        self.file = file
        self.name = name
        self.close_called = False
        self.delete = delete

        if _os.name != 'nt':
            # Cache the unlinker so we don't get spurious errors at
            # shutdown when the module-level "os" is None'd out.  Note
            # that this must be referenced as self.unlink, because the
            # name TemporaryFileWrapper may also get None'd out before
            # __del__ is called.
            self.unlink = _os.unlink

    def __getattr__(self, name: str) -> _Any:
        # Attribute lookups are delegated to the underlying file
        # and cached for non-numeric results
        # (i.e. methods are cached, closed and friends are not)
        file = _cast(_Any, self).__dict__['file'] # type: _IO[_Any]
        a = getattr(file, name)
        if not isinstance(a, int):
            setattr(self, name, a)
        return a

    # The underlying __enter__ method returns the wrong object
    # (self.file) so override it to return the wrapper
    def __enter__(self) -> '_TemporaryFileWrapper':
        self.file.__enter__()
        return self

    # iter() doesn't use __getattr__ to find the __iter__ method
    def __iter__(self) -> _Iterator[_Any]:
        return iter(self.file)

    # NT provides delete-on-close as a primitive, so we don't need
    # the wrapper to do anything special.  We still use it so that
    # file.name is useful (i.e. not "(fdopen)") with NamedTemporaryFile.
    if _os.name != 'nt':
        def close(self) -> None:
            if not self.close_called:
                self.close_called = True
                self.file.close()
                if self.delete:
                    self.unlink(self.name)

        def __del__(self) -> None:
            self.close()

        # Need to trap __exit__ as well to ensure the file gets
        # deleted when used in a with statement
        def __exit__(self, exc: _Type[BaseException], value: BaseException,
                     tb: _Optional[_TracebackType]) -> bool:
            result = self.file.__exit__(exc, value, tb)
            self.close()
            return result
    else:
        def __exit__(self,  # type: ignore[misc]
                     exc: _Type[BaseException],
                     value: BaseException,
                     tb: _Optional[_TracebackType]) -> Literal[False]:
            self.file.__exit__(exc, value, tb)
            return False


def NamedTemporaryFile(mode: str = 'w+b', buffering: int = -1,
                       encoding: str = None, newline: str = None,
                       suffix: str = "", prefix: str = template,
                       dir: str = None, delete: bool = True) -> _IO[_Any]:
    """Create and return a temporary file.
    Arguments:
    'prefix', 'suffix', 'dir' -- as for mkstemp.
    'mode' -- the mode argument to io.open (default "w+b").
    'buffering' -- the buffer size argument to io.open (default -1).
    'encoding' -- the encoding argument to io.open (default None)
    'newline' -- the newline argument to io.open (default None)
    'delete' -- whether the file is deleted on close (default True).
    The file is created as mkstemp() would do it.

    Returns an object with a file-like interface; the name of the file
    is accessible as file.name.  The file will be automatically deleted
    when it is closed unless the 'delete' argument is set to False.
    """

    if dir is None:
        dir = gettempdir()

    flags = _bin_openflags

    # Setting O_TEMPORARY in the flags causes the OS to delete
    # the file when it is closed.  This is only supported by Windows.
    if _os.name == 'nt' and delete:
        flags |= _os.O_TEMPORARY

    (fd, name) = _mkstemp_inner(dir, prefix, suffix, flags)
    file = _io.open(fd, mode, buffering=buffering,
                    newline=newline, encoding=encoding)

    return _cast(_IO[_Any], _TemporaryFileWrapper(file, name, delete))

if _os.name != 'posix' or _sys.platform == 'cygwin':
    # On non-POSIX and Cygwin systems, assume that we cannot unlink a file
    # while it is open.
    TemporaryFile = NamedTemporaryFile

else:
    def _TemporaryFile(mode: str = 'w+b', buffering: int = -1,
                       encoding: str = None, newline: str = None,
                       suffix: str = "", prefix: str = template,
                       dir: str = None, delete: bool = True) -> _IO[_Any]:
        """Create and return a temporary file.
        Arguments:
        'prefix', 'suffix', 'dir' -- as for mkstemp.
        'mode' -- the mode argument to io.open (default "w+b").
        'buffering' -- the buffer size argument to io.open (default -1).
        'encoding' -- the encoding argument to io.open (default None)
        'newline' -- the newline argument to io.open (default None)
        The file is created as mkstemp() would do it.

        Returns an object with a file-like interface.  The file has no
        name, and will cease to exist when it is closed.
        """

        if dir is None:
            dir = gettempdir()

        flags = _bin_openflags

        (fd, name) = _mkstemp_inner(dir, prefix, suffix, flags)
        try:
            _os.unlink(name)
            return _io.open(fd, mode, buffering=buffering,
                            newline=newline, encoding=encoding)
        except:
            _os.close(fd)
            raise
    TemporaryFile = _TemporaryFile

class SpooledTemporaryFile:
    """Temporary file wrapper, specialized to switch from
    StringIO to a real file when it exceeds a certain size or
    when a fileno is needed.
    """
    _rolled = False
    _file = None  # type: _Any   # BytesIO, StringIO or TemporaryFile

    def __init__(self, max_size: int = 0, mode: str = 'w+b',
                 buffering: int = -1, encoding: str = None,
                 newline: str = None, suffix: str = "",
                 prefix: str = template, dir: str = None) -> None:
        if 'b' in mode:
            self._file = _io.BytesIO()
        else:
            # Setting newline="\n" avoids newline translation;
            # this is important because otherwise on Windows we'd
            # hget double newline translation upon rollover().
            self._file = _io.StringIO(newline="\n")
        self._max_size = max_size
        self._rolled = False
        self._TemporaryFileArgs = {
                                   'mode': mode, 'buffering': buffering,
                                   'suffix': suffix, 'prefix': prefix,
                                   'encoding': encoding, 'newline': newline,
                                   'dir': dir} # type: _Dict[str, _Any]

    def _check(self, file: _IO[_Any]) -> None:
        if self._rolled: return
        max_size = self._max_size
        if max_size and file.tell() > max_size:
            self.rollover()

    def rollover(self) -> None:
        if self._rolled: return
        file = self._file
        newfile = self._file = TemporaryFile(**self._TemporaryFileArgs)
        self._TemporaryFileArgs = None

        newfile.write(file.getvalue())
        newfile.seek(file.tell(), 0)

        self._rolled = True

    # The method caching trick from NamedTemporaryFile
    # won't work here, because _file may change from a
    # _StringIO instance to a real file. So we list
    # all the methods directly.

    # Context management protocol
    def __enter__(self) -> 'SpooledTemporaryFile':
        if self._file.closed:
            raise ValueError("Cannot enter context with closed file")
        return self

    def __exit__(self, exc: type, value: BaseException,
                 tb: _TracebackType) -> Literal[False]:
        self._file.close()
        return False

    # file protocol
    def __iter__(self) -> _Iterable[_Any]:
        return self._file.__iter__()

    def close(self) -> None:
        self._file.close()

    @property
    def closed(self) -> bool:
        return self._file.closed

    @property
    def encoding(self) -> str:
        return self._file.encoding

    def fileno(self) -> int:
        self.rollover()
        return self._file.fileno()

    def flush(self) -> None:
        self._file.flush()

    def isatty(self) -> bool:
        return self._file.isatty()

    @property
    def mode(self) -> str:
        return self._file.mode

    @property
    def name(self) -> str:
        return self._file.name

    @property
    def newlines(self) -> _Any:
        return self._file.newlines

    #def next(self):
    #    return self._file.next

    def read(self, n: int = -1) -> _Any:
        return self._file.read(n)

    def readline(self, limit: int = -1) -> _Any:
        return self._file.readline(limit)

    def readlines(self, *args) -> _List[_Any]:
        return self._file.readlines(*args)

    def seek(self, offset: int, whence: int = 0) -> None:
        self._file.seek(offset, whence)

    @property
    def softspace(self) -> bool:
        return self._file.softspace

    def tell(self) -> int:
        return self._file.tell()

    def truncate(self) -> None:
        self._file.truncate()

    def write(self, s: _Any) -> int:
        file = self._file # type: _IO[_Any]
        rv = file.write(s)
        self._check(file)
        return rv

    def writelines(self, iterable: _Iterable[_Any]) -> None:
        file = self._file # type: _IO[_Any]
        file.writelines(iterable)
        self._check(file)

    #def xreadlines(self, *args) -> _Any:
    #    return self._file.xreadlines(*args)


class TemporaryDirectory(object):
    """Create and return a temporary directory.  This has the same
    behavior as mkdtemp but can be used as a context manager.  For
    example:

        with TemporaryDirectory() as tmpdir:
            ...

    Upon exiting the context, the directory and everything contained
    in it are removed.
    """

    def __init__(self, suffix: str = "", prefix: str = template,
                 dir: str = None) -> None:
        self._closed = False
        self.name = None # type: str # Handle mkdtemp throwing an exception
        self.name = mkdtemp(suffix, prefix, dir)

        # XXX (ncoghlan): The following code attempts to make
        # this class tolerant of the module nulling out process
        # that happens during CPython interpreter shutdown
        # Alas, it doesn't actually manage it. See issue #10188
        self._listdir = _os.listdir
        self._path_join = _os.path.join
        self._isdir = _os.path.isdir
        self._islink = _os.path.islink
        self._remove = _os.remove
        self._rmdir = _os.rmdir
        self._os_error = _os.error
        self._warn = _warnings.warn

    def __repr__(self) -> str:
        return "<{} {!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self) -> str:
        return self.name

    def cleanup(self, _warn: bool = False) -> None:
        if self.name and not self._closed:
            try:
                self._rmtree(self.name)
            except (TypeError, AttributeError) as ex:
                # Issue #10188: Emit a warning on stderr
                # if the directory could not be cleaned
                # up due to missing globals
                if "None" not in str(ex):
                    raise
                print("ERROR: {!r} while cleaning up {!r}".format(ex, self,),
                      file=_sys.stderr)
                return
            self._closed = True
            if _warn:
                self._warn("Implicitly cleaning up {!r}".format(self),
                           ResourceWarning)

    def __exit__(self, exc: type, value: BaseException,
                 tb: _TracebackType) -> Literal[False]:
        self.cleanup()
        return False

    def __del__(self) -> None:
        # Issue a ResourceWarning if implicit cleanup needed
        self.cleanup(_warn=True)

    def _rmtree(self, path: str) -> None:
        # Essentially a stripped down version of shutil.rmtree.  We can't
        # use globals because they may be None'ed out at shutdown.
        for name in self._listdir(path):
            fullname = self._path_join(path, name)
            try:
                isdir = self._isdir(fullname) and not self._islink(fullname)
            except self._os_error:
                isdir = False
            if isdir:
                self._rmtree(fullname)
            else:
                try:
                    self._remove(fullname)
                except self._os_error:
                    pass
        try:
            self._rmdir(path)
        except self._os_error:
            pass
