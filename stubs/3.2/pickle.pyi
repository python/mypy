# Stubs for pickle

# NOTE: These are incomplete!

from typing import Any, IO

def dumps(obj: Any, protocol: int = None, *,
          fix_imports: bool = True) -> bytes: ...
def loads(p: bytes, *, fix_imports: bool = True,
          encoding: str = 'ASCII', errors: str = 'strict') -> Any: ...
def load(file: IO[bytes], *, fix_imports: bool = True, encoding: str = 'ASCII',
         errors: str = 'strict') -> Any: ...
