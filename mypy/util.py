"""Utility functions with no non-trivial dependencies."""
import genericpath  # type: ignore # no 
import os
from os.path import splitdrive
import re
import subprocess
from xml.sax.saxutils import escape
from typing import TypeVar, List, Tuple, Optional, Dict, Sequence


T = TypeVar('T')

ENCODING_RE = re.compile(br'([ \t\v]*#.*(\r\n?|\n))??[ \t\v]*#.*coding[:=][ \t]*([-\w.]+)')

default_python2_interpreter = ['python2', 'python', '/usr/bin/python', 'C:\\Python27\\python.exe']


def split_module_names(mod_name: str) -> List[str]:
    """Return the module and all parent module names.

    So, if `mod_name` is 'a.b.c', this function will return
    ['a.b.c', 'a.b', and 'a'].
    """
    out = [mod_name]
    while '.' in mod_name:
        mod_name = mod_name.rsplit('.', 1)[0]
        out.append(mod_name)
    return out


def short_type(obj: object) -> str:
    """Return the last component of the type name of an object.

    If obj is None, return 'nil'. For example, if obj is 1, return 'int'.
    """
    if obj is None:
        return 'nil'
    t = str(type(obj))
    return t.split('.')[-1].rstrip("'>")


def array_repr(a: List[T]) -> List[str]:
    """Return the items of an array converted to strings using Repr."""
    aa = []  # type: List[str]
    for x in a:
        aa.append(repr(x))
    return aa


def find_python_encoding(text: bytes, pyversion: Tuple[int, int]) -> Tuple[str, int]:
    """PEP-263 for detecting Python file encoding"""
    result = ENCODING_RE.match(text)
    if result:
        line = 2 if result.group(1) else 1
        encoding = result.group(3).decode('ascii')
        # Handle some aliases that Python is happy to accept and that are used in the wild.
        if encoding.startswith(('iso-latin-1-', 'latin-1-')) or encoding == 'iso-latin-1':
            encoding = 'latin-1'
        return encoding, line
    else:
        default_encoding = 'utf8' if pyversion[0] >= 3 else 'ascii'
        return default_encoding, -1


class DecodeError(Exception):
    """Exception raised when a file cannot be decoded due to an unknown encoding type.

    Essentially a wrapper for the LookupError raised by `bytearray.decode`
    """


def decode_python_encoding(source: bytes, pyversion: Tuple[int, int]) -> str:
    """Read the Python file with while obeying PEP-263 encoding detection.

    Returns:
      A tuple: the source as a string, and the hash calculated from the binary representation.
    """
    # check for BOM UTF-8 encoding and strip it out if present
    if source.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf8'
        source = source[3:]
    else:
        # look at first two lines and check if PEP-263 coding is present
        encoding, _ = find_python_encoding(source, pyversion)

    try:
        source_text = source.decode(encoding)
    except LookupError as lookuperr:
        raise DecodeError(str(lookuperr))
    return source_text


_python2_interpreter = None  # type: Optional[str]


def try_find_python2_interpreter() -> Optional[str]:
    global _python2_interpreter
    if _python2_interpreter:
        return _python2_interpreter
    for interpreter in default_python2_interpreter:
        try:
            retcode = subprocess.Popen([
                interpreter, '-c',
                'import sys, typing; assert sys.version_info[:2] == (2, 7)'
            ]).wait()
            if not retcode:
                _python2_interpreter = interpreter
                return interpreter
        except OSError:
            pass
    return None


PASS_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<testsuite errors="0" failures="0" name="mypy" skips="0" tests="1" time="{time:.3f}">
  <testcase classname="mypy" file="mypy" line="1" name="mypy" time="{time:.3f}">
  </testcase>
</testsuite>
"""

FAIL_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<testsuite errors="0" failures="1" name="mypy" skips="0" tests="1" time="{time:.3f}">
  <testcase classname="mypy" file="mypy" line="1" name="mypy" time="{time:.3f}">
    <failure message="mypy produced messages">{text}</failure>
  </testcase>
</testsuite>
"""

ERROR_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<testsuite errors="1" failures="0" name="mypy" skips="0" tests="1" time="{time:.3f}">
  <testcase classname="mypy" file="mypy" line="1" name="mypy" time="{time:.3f}">
    <error message="mypy produced errors">{text}</error>
  </testcase>
</testsuite>
"""


def write_junit_xml(dt: float, serious: bool, messages: List[str], path: str) -> None:
    """XXX"""
    if not messages and not serious:
        xml = PASS_TEMPLATE.format(time=dt)
    elif not serious:
        xml = FAIL_TEMPLATE.format(text=escape('\n'.join(messages)), time=dt)
    else:
        xml = ERROR_TEMPLATE.format(text=escape('\n'.join(messages)), time=dt)
    with open(path, 'wb') as f:
        f.write(xml.encode('utf-8'))


class IdMapper:
    """Generate integer ids for objects.

    Unlike id(), these start from 0 and increment by 1, and ids won't
    get reused across the life-time of IdMapper.

    Assume objects don't redefine __eq__ or __hash__.
    """

    def __init__(self) -> None:
        self.id_map = {}  # type: Dict[object, int]
        self.next_id = 0

    def id(self, o: object) -> int:
        if o not in self.id_map:
            self.id_map[o] = self.next_id
            self.next_id += 1
        return self.id_map[o]


def get_prefix(fullname: str) -> str:
    """Drop the final component of a qualified name (e.g. ('x.y' -> 'x')."""
    return fullname.rsplit('.', 1)[0]


def correct_relative_import(cur_mod_id: str,
                            relative: int,
                            target: str,
                            is_cur_package_init_file: bool) -> Tuple[str, bool]:
    if relative == 0:
        return target, True
    parts = cur_mod_id.split(".")
    rel = relative
    if is_cur_package_init_file:
        rel -= 1
    ok = len(parts) >= rel
    if rel != 0:
        cur_mod_id = ".".join(parts[:-rel])
    return cur_mod_id + (("." + target) if target else ""), ok


def replace_object_state(new: object, old: object) -> None:
    """Copy state of old node to the new node.

    This handles cases where there is __slots__ and/or __dict__.

    Assume that both objects have the same __class__.
    """
    if hasattr(old, '__dict__'):
        new.__dict__ = old.__dict__
    if hasattr(old, '__slots__'):
        # Use __mro__ since some classes override 'mro' with something different.
        for base in type(old).__mro__:
            if '__slots__' in base.__dict__:
                for attr in getattr(base, '__slots__'):
                    if hasattr(old, attr):
                        setattr(new, attr, getattr(old, attr))
                    elif hasattr(new, attr):
                        delattr(new, attr)

# backport commonpath for 3.4
if os.name == 'nt':
    def commonpath(paths: Sequence[str]) -> str:
        """Given a sequence of path names, returns the longest common sub-path."""

        if not paths:
            raise ValueError('commonpath() arg is an empty sequence')

        paths = tuple(map(os.fspath, paths))
        if isinstance(paths[0], bytes):
            sep = b'\\'
            altsep = b'/'
            curdir = b'.'
        else:
            sep = '\\'
            altsep = '/'
            curdir = '.'

        try:
            drivesplits = [splitdrive(p.replace(altsep, sep).lower()) for p in paths]
            split_paths = [p.split(sep) for d, p in drivesplits]

            try:
                isabs, = set(p[:1] == sep for d, p in drivesplits)
            except ValueError:
                raise ValueError("Can't mix absolute and relative paths") from None

            # Check that all drive letters or UNC paths match. The check is made only
            # now otherwise type errors for mixing strings and bytes would not be
            # caught.
            if len(set(d for d, p in drivesplits)) != 1:
                raise ValueError("Paths don't have the same drive")

            drive, path = splitdrive(paths[0].replace(altsep, sep))
            common = path.split(sep)
            common = [c for c in common if c and c != curdir]

            split_paths = [[c for c in s if c and c != curdir] for s in split_paths]
            s1 = min(split_paths)
            s2 = max(split_paths)
            for i, c in enumerate(s1):
                if c != s2[i]:
                    common = common[:i]
                    break
            else:
                common = common[:len(s1)]

            prefix = drive + sep if isabs else drive
            return prefix + sep.join(common)
        except (TypeError, AttributeError):
            genericpath._check_arg_types('commonpath', *paths)
            raise
else:
    def commonpath(paths: Sequence[str]) -> str:
        """Given a sequence of path names, returns the longest common sub-path."""

        if not paths:
            raise ValueError('commonpath() arg is an empty sequence')

        paths = tuple(map(os.fspath, paths))
        if isinstance(paths[0], bytes):
            sep = b'/'
            curdir = b'.'
        else:
            sep = '/'
            curdir = '.'

        try:
            split_paths = [path.split(sep) for path in paths]

            try:
                isabs, = set(p[:1] == sep for p in paths)
            except ValueError:
                raise ValueError("Can't mix absolute and relative paths") from None

            split_paths = [[c for c in s if c and c != curdir] for s in split_paths]
            s1 = min(split_paths)
            s2 = max(split_paths)
            common = s1
            for i, c in enumerate(s1):
                if c != s2[i]:
                    common = s1[:i]
                    break

            prefix = sep if isabs else sep[:0]
            return prefix + sep.join(common)
        except (TypeError, AttributeError):
            genericpath._check_arg_types('commonpath', *paths)
            raise