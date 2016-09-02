"""Utility functions with no non-trivial dependencies."""

import re
import subprocess
from typing import TypeVar, List, Any, Tuple, Optional


T = TypeVar('T')

ENCODING_RE = re.compile(br'([ \t\v]*#.*(\r\n?|\n))??[ \t\v]*#.*coding[:=][ \t]*([-\w.]+)')

default_python2_interpreter = ['python2', 'python', '/usr/bin/python']


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


def indent(s: str, n: int) -> str:
    """Indent all the lines in s (separated by Newlines) by n spaces."""
    s = ' ' * n + s
    s = s.replace('\n', '\n' + ' ' * n)
    return s


def array_repr(a: List[T]) -> List[str]:
    """Return the items of an array converted to strings using Repr."""
    aa = []  # type: List[str]
    for x in a:
        aa.append(repr(x))
    return aa


def dump_tagged(nodes: List[Any], tag: str) -> str:
    """Convert an array into a pretty-printed multiline string representation.

    The format is
      tag(
        item1..
        itemN)
    Individual items are formatted like this:
     - arrays are flattened
     - pairs (str : array) are converted recursively, so that str is the tag
     - other items are converted to strings and indented
    """
    a = []  # type: List[str]
    if tag:
        a.append(tag + '(')
    for n in nodes:
        if isinstance(n, list):
            if n:
                a.append(dump_tagged(n, None))
        elif isinstance(n, tuple):
            s = dump_tagged(n[1], n[0])
            a.append(indent(s, 2))
        elif n:
            a.append(indent(str(n), 2))
    if tag:
        a[-1] += ')'
    return '\n'.join(a)


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


_python2_interpreter = None  # type: Optional[str]


def try_find_python2_interpreter() -> Optional[str]:
    global _python2_interpreter
    if _python2_interpreter:
        return _python2_interpreter
    for interpreter in default_python2_interpreter:
        try:
            process = subprocess.Popen([interpreter, '-V'], stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            stdout, stderr = process.communicate()
            if b'Python 2.7' in stdout:
                _python2_interpreter = interpreter
                return interpreter
        except OSError:
            pass
    return None
