"""Utility functions with no non-trivial dependencies."""
import contextlib
import os
import pathlib
import re
import subprocess
import sys
from types import TracebackType
from typing import TypeVar, List, Tuple, Optional, Dict, Sequence, TextIO

MYPY = False
if MYPY:
    from typing import Type, ClassVar
    from typing_extensions import Final

T = TypeVar('T')

ENCODING_RE = \
    re.compile(br'([ \t\v]*#.*(\r\n?|\n))??[ \t\v]*#.*coding[:=][ \t]*([-\w.]+)')  # type: Final

default_python2_interpreter = \
    ['python2', 'python', '/usr/bin/python', 'C:\\Python27\\python.exe']  # type: Final


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
  <testcase classname="mypy" file="mypy" line="1" name="mypy-py{ver}-{platform}" time="{time:.3f}">
  </testcase>
</testsuite>
"""  # type: Final

FAIL_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<testsuite errors="0" failures="1" name="mypy" skips="0" tests="1" time="{time:.3f}">
  <testcase classname="mypy" file="mypy" line="1" name="mypy-py{ver}-{platform}" time="{time:.3f}">
    <failure message="mypy produced messages">{text}</failure>
  </testcase>
</testsuite>
"""  # type: Final

ERROR_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<testsuite errors="1" failures="0" name="mypy" skips="0" tests="1" time="{time:.3f}">
  <testcase classname="mypy" file="mypy" line="1" name="mypy-py{ver}-{platform}" time="{time:.3f}">
    <error message="mypy produced errors">{text}</error>
  </testcase>
</testsuite>
"""  # type: Final


def write_junit_xml(dt: float, serious: bool, messages: List[str], path: str,
                    version: str, platform: str) -> None:
    from xml.sax.saxutils import escape
    if not messages and not serious:
        xml = PASS_TEMPLATE.format(time=dt, ver=version, platform=platform)
    elif not serious:
        xml = FAIL_TEMPLATE.format(text=escape('\n'.join(messages)), time=dt,
                                   ver=version, platform=platform)
    else:
        xml = ERROR_TEMPLATE.format(text=escape('\n'.join(messages)), time=dt,
                                    ver=version, platform=platform)

    # checks for a directory structure in path and creates folders if needed
    xml_dirs = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(xml_dirs):
        os.makedirs(xml_dirs)

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


fields_cache = {}  # type: Final[Dict[Type[object], List[str]]]


def get_class_descriptors(cls: 'Type[object]') -> Sequence[str]:
    import inspect  # Lazy import for minor startup speed win
    # Maintain a cache of type -> attributes defined by descriptors in the class
    # (that is, attributes from __slots__ and C extension classes)
    if cls not in fields_cache:
        members = inspect.getmembers(
            cls,
            lambda o: inspect.isgetsetdescriptor(o) or inspect.ismemberdescriptor(o))
        fields_cache[cls] = [x for x, y in members if x != '__weakref__']
    return fields_cache[cls]


def replace_object_state(new: object, old: object, copy_dict: bool = False) -> None:
    """Copy state of old node to the new node.

    This handles cases where there is __dict__ and/or attribute descriptors
    (either from slots or because the type is defined in a C extension module).

    Assume that both objects have the same __class__.
    """
    if hasattr(old, '__dict__'):
        if copy_dict:
            new.__dict__ = dict(old.__dict__)
        else:
            new.__dict__ = old.__dict__

    for attr in get_class_descriptors(old.__class__):
        try:
            if hasattr(old, attr):
                setattr(new, attr, getattr(old, attr))
            elif hasattr(new, attr):
                delattr(new, attr)
        # There is no way to distinguish getsetdescriptors that allow
        # writes from ones that don't (I think?), so we just ignore
        # AttributeErrors if we need to.
        # TODO: What about getsetdescriptors that act like properties???
        except AttributeError:
            pass


def is_sub_path(path1: str, path2: str) -> bool:
    """Given two paths, return if path1 is a sub-path of path2."""
    return pathlib.Path(path2) in pathlib.Path(path1).parents


def hard_exit(status: int = 0) -> None:
    """Kill the current process without fully cleaning up.

    This can be quite a bit faster than a normal exit() since objects are not freed.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)


def unmangle(name: str) -> str:
    """Remove internal suffixes from a short name."""
    return name.rstrip("'")


# The following is a backport of stream redirect utilities from Lib/contextlib.py
# We need this for 3.4 support. They can be removed in March 2019!


class _RedirectStream:

    _stream = None  # type: ClassVar[str]

    def __init__(self, new_target: TextIO) -> None:
        self._new_target = new_target
        # We use a list of old targets to make this CM re-entrant
        self._old_targets = []  # type: List[TextIO]

    def __enter__(self) -> TextIO:
        self._old_targets.append(getattr(sys, self._stream))
        setattr(sys, self._stream, self._new_target)
        return self._new_target

    def __exit__(self,
                 exc_ty: 'Optional[Type[BaseException]]' = None,
                 exc_val: Optional[BaseException] = None,
                 exc_tb: Optional[TracebackType] = None,
                 ) -> bool:
        setattr(sys, self._stream, self._old_targets.pop())
        return False


class redirect_stdout(_RedirectStream):
    """Context manager for temporarily redirecting stdout to another file.
        # How to send help() to stderr
        with redirect_stdout(sys.stderr):
            help(dir)
        # How to write help() to a file
        with open('help.txt', 'w') as f:
            with redirect_stdout(f):
                help(pow)
    """

    _stream = "stdout"


class redirect_stderr(_RedirectStream):
    """Context manager for temporarily redirecting stderr to another file."""

    _stream = "stderr"
