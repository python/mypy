# Stubs for fnmatch

# Based on http://docs.python.org/3.2/library/fnmatch.html and
# python-lib/fnmatch.py

from typing import overload, Iterable, List

@overload
def fnmatch(name: str, pat: str) -> bool: pass
@overload
def fnmatch(name: bytes, pat: bytes) -> bool: pass

@overload
def fnmatchcase(name: str, pat: str) -> bool: pass
@overload
def fnmatchcase(name: bytes, pat: bytes) -> bool: pass

@overload
def filter(names: Iterable[str], pat: str) -> List[str]: pass
@overload
def filter(names: Iterable[bytes], pat: bytes) -> List[bytes]: pass
def translate(pat: str) -> str: pass
