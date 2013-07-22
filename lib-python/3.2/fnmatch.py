"""Filename matching with shell patterns.

fnmatch(FILENAME, PATTERN) matches according to the local convention.
fnmatchcase(FILENAME, PATTERN) always takes case in account.

The functions operate by translating the pattern into a regular
expression.  They cache the compiled regular expressions for speed.

The function translate(PATTERN) returns a regular expression
corresponding to PATTERN.  (It does not compile it.)
"""
import os
import posixpath
import re
import functools

from typing import overload, Iterable, List, AnyStr

__all__ = ["filter", "fnmatch", "fnmatchcase", "translate"]

def fnmatch(name: AnyStr, pat: AnyStr) -> bool:
    """Test whether FILENAME matches PATTERN.

    Patterns are Unix shell style:

    *       matches everything
    ?       matches any single character
    [seq]   matches any character in seq
    [!seq]  matches any char not in seq

    An initial period in FILENAME is not special.
    Both FILENAME and PATTERN are first case-normalized
    if the operating system requires it.
    If you don't want this, use fnmatchcase(FILENAME, PATTERN).
    """
    name = os.path.normcase(name)
    pat = os.path.normcase(pat)
    return fnmatchcase(name, pat)

@functools.lru_cache(maxsize=250)
def _compile_pattern(pat, is_bytes=False):
    if is_bytes:
        pat_str = str(pat, 'ISO-8859-1')
        res_str = translate(pat_str)
        res = bytes(res_str, 'ISO-8859-1')
    else:
        res = translate(pat)
    return re.compile(res).match

def _filter(names, pat):
    result = []
    pat = os.path.normcase(pat)
    match = _compile_pattern(pat, isinstance(pat, bytes))
    if os.path is posixpath:
        # normcase on posix is NOP. Optimize it away from the loop.
        for name in names:
            if match(name):
                result.append(name)
    else:
        for name in names:
            if match(os.path.normcase(name)):
                result.append(name)
    return result

@overload
def filter(names: Iterable[str], pat: str) -> List[str]:
    """Return the subset of the list NAMES that match PAT."""
    return _filter(names, pat)

@overload
def filter(names: Iterable[bytes], pat: bytes) -> List[bytes]:
    return _filter(names, pat)

def _fnmatchcase(name, pat):
    match = _compile_pattern(pat, isinstance(pat, bytes))
    return match(name) is not None

@overload
def fnmatchcase(name: str, pat: str) -> bool:
    """Test whether FILENAME matches PATTERN, including case.

    This is a version of fnmatch() which doesn't case-normalize
    its arguments.
    """
    return _fnmatchcase(name, pat)

@overload
def fnmatchcase(name: bytes, pat: bytes) -> bool:
    return _fnmatchcase(name, pat)

def translate(pat: str) -> str:
    """Translate a shell PATTERN to a regular expression.

    There is no way to quote meta-characters.
    """

    i, n = 0, len(pat)
    res = ''
    while i < n:
        c = pat[i]
        i = i+1
        if c == '*':
            res = res + '.*'
        elif c == '?':
            res = res + '.'
        elif c == '[':
            j = i
            if j < n and pat[j] == '!':
                j = j+1
            if j < n and pat[j] == ']':
                j = j+1
            while j < n and pat[j] != ']':
                j = j+1
            if j >= n:
                res = res + '\\['
            else:
                stuff = pat[i:j].replace('\\','\\\\')
                i = j+1
                if stuff[0] == '!':
                    stuff = '^' + stuff[1:]
                elif stuff[0] == '^':
                    stuff = '\\' + stuff
                res = '%s[%s]' % (res, stuff)
        else:
            res = res + re.escape(c)
    return res + '\Z(?ms)'
