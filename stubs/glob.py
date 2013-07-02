# Stubs for glob

# Based on http://docs.python.org/3.2/library/glob.html

from typing import overload, List, Iterator

@overload
def glob(pathname: str) -> List[str]: pass
@overload
def glob(pathname: bytes) -> List[bytes]: pass
@overload
def iglob(pathname: str) -> Iterator[str]: pass
@overload
def iglob(pathname: bytes) -> Iterator[bytes]: pass
