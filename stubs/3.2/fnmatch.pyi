# Stubs for fnmatch

# Based on http://docs.python.org/3.2/library/fnmatch.html and
# python-lib/fnmatch.py

from typing import Iterable, List, AnyStr

def fnmatch(name: AnyStr, pat: AnyStr) -> bool: pass
def fnmatchcase(name: AnyStr, pat: AnyStr) -> bool: pass
def filter(names: Iterable[AnyStr], pat: AnyStr) -> List[AnyStr]: pass
def translate(pat: str) -> str: pass
