# Stubs for glob

# Based on http://docs.python.org/3.2/library/glob.html

from typing import List, Iterator, AnyStr

def glob(pathname: AnyStr) -> List[AnyStr]: ...
def iglob(pathname: AnyStr) -> Iterator[AnyStr]: ...
