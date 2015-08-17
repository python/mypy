# Stubs for tempfile
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.3/library/tempfile.html

from typing import Tuple, BinaryIO

# global variables
tempdir = ''
template = ''

# TODO text files

# function stubs
def TemporaryFile(
            mode: str = 'w+b', buffering: int = None, encoding: str = None,
            newline: str = None, suffix: str = '', prefix: str = 'tmp',
            dir: str = None) -> BinaryIO:
    ...
def NamedTemporaryFile(
            mode: str = 'w+b', buffering: int = None, encoding: str = None,
            newline: str = None, suffix: str = '', prefix: str = 'tmp',
            dir: str = None, delete=True) -> BinaryIO:
    ...
def SpooledTemporaryFile(
            max_size: int = 0, mode: str = 'w+b', buffering: int = None,
            encoding: str = None, newline: str = None, suffix: str = '',
            prefix: str = 'tmp', dir: str = None) -> BinaryIO:
    ...

class TemporaryDirectory:
    name = ''
    def __init__(self, suffix: str = '', prefix: str = 'tmp',
                 dir: str = None) -> None: ...
    def cleanup(self) -> None: ...
    def __enter__(self) -> str: ...
    def __exit__(self, type, value, traceback) -> bool: ...

def mkstemp(suffix: str = '', prefix: str = 'tmp', dir: str = None,
            text: bool = False) -> Tuple[int, str]: ...
def mkdtemp(suffix: str = '', prefix: str = 'tmp',
            dir: str = None) -> str: ...
def mktemp(suffix: str = '', prefix: str = 'tmp', dir: str = None) -> str: ...
def gettempdir() -> str: ...
def gettempprefix() -> str: ...
