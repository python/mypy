# Stubs for shlex

# Based on http://docs.python.org/3.2/library/shlex.html

from typing import List, Tuple, Any, TextIO

def split(s: str, comments: bool = False,
          posix: bool = True) -> List[str]: ...

class shlex:
    commenters = ''
    wordchars = ''
    whitespace = ''
    escape = ''
    quotes = ''
    escapedquotes = ''
    whitespace_split = ''
    infile = ''
    instream = ...  # type: TextIO
    source = ''
    debug = 0
    lineno = 0
    token = ''
    eof = ''

    def __init__(self, instream=None, infile=None,
                 posix: bool = False) -> None: ...
    def get_token(self) -> str: ...
    def push_token(self, tok: str) -> None: ...
    def read_token(self) -> str: ...
    def sourcehook(self, filename: str) -> Tuple[str, TextIO]: ...
    # TODO argument types
    def push_source(self, newstream: Any, newfile: Any = None) -> None: ...
    def pop_source(self) -> None: ...
    def error_leader(self, infile: str = None,
                     lineno: int = None) -> None: ...
