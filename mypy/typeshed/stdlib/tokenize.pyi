import sys
from _typeshed import StrOrBytesPath
from builtins import open as _builtin_open
from token import *
from typing import Any, Callable, Generator, Iterable, NamedTuple, Pattern, Sequence, TextIO

if sys.version_info >= (3, 10):
    __all__ = [
        "tok_name",
        "ISTERMINAL",
        "ISNONTERMINAL",
        "ISEOF",
        "ENDMARKER",
        "NAME",
        "NUMBER",
        "STRING",
        "NEWLINE",
        "INDENT",
        "DEDENT",
        "LPAR",
        "RPAR",
        "LSQB",
        "RSQB",
        "COLON",
        "COMMA",
        "SEMI",
        "PLUS",
        "MINUS",
        "STAR",
        "SLASH",
        "VBAR",
        "AMPER",
        "LESS",
        "GREATER",
        "EQUAL",
        "DOT",
        "PERCENT",
        "LBRACE",
        "RBRACE",
        "EQEQUAL",
        "NOTEQUAL",
        "LESSEQUAL",
        "GREATEREQUAL",
        "TILDE",
        "CIRCUMFLEX",
        "LEFTSHIFT",
        "RIGHTSHIFT",
        "DOUBLESTAR",
        "PLUSEQUAL",
        "MINEQUAL",
        "STAREQUAL",
        "SLASHEQUAL",
        "PERCENTEQUAL",
        "AMPEREQUAL",
        "VBAREQUAL",
        "CIRCUMFLEXEQUAL",
        "LEFTSHIFTEQUAL",
        "RIGHTSHIFTEQUAL",
        "DOUBLESTAREQUAL",
        "DOUBLESLASH",
        "DOUBLESLASHEQUAL",
        "AT",
        "ATEQUAL",
        "RARROW",
        "ELLIPSIS",
        "COLONEQUAL",
        "OP",
        "AWAIT",
        "ASYNC",
        "TYPE_IGNORE",
        "TYPE_COMMENT",
        "SOFT_KEYWORD",
        "ERRORTOKEN",
        "COMMENT",
        "NL",
        "ENCODING",
        "N_TOKENS",
        "NT_OFFSET",
        "tokenize",
        "generate_tokens",
        "detect_encoding",
        "untokenize",
        "TokenInfo",
    ]
elif sys.version_info >= (3, 8):
    __all__ = [
        "tok_name",
        "ISTERMINAL",
        "ISNONTERMINAL",
        "ISEOF",
        "ENDMARKER",
        "NAME",
        "NUMBER",
        "STRING",
        "NEWLINE",
        "INDENT",
        "DEDENT",
        "LPAR",
        "RPAR",
        "LSQB",
        "RSQB",
        "COLON",
        "COMMA",
        "SEMI",
        "PLUS",
        "MINUS",
        "STAR",
        "SLASH",
        "VBAR",
        "AMPER",
        "LESS",
        "GREATER",
        "EQUAL",
        "DOT",
        "PERCENT",
        "LBRACE",
        "RBRACE",
        "EQEQUAL",
        "NOTEQUAL",
        "LESSEQUAL",
        "GREATEREQUAL",
        "TILDE",
        "CIRCUMFLEX",
        "LEFTSHIFT",
        "RIGHTSHIFT",
        "DOUBLESTAR",
        "PLUSEQUAL",
        "MINEQUAL",
        "STAREQUAL",
        "SLASHEQUAL",
        "PERCENTEQUAL",
        "AMPEREQUAL",
        "VBAREQUAL",
        "CIRCUMFLEXEQUAL",
        "LEFTSHIFTEQUAL",
        "RIGHTSHIFTEQUAL",
        "DOUBLESTAREQUAL",
        "DOUBLESLASH",
        "DOUBLESLASHEQUAL",
        "AT",
        "ATEQUAL",
        "RARROW",
        "ELLIPSIS",
        "COLONEQUAL",
        "OP",
        "AWAIT",
        "ASYNC",
        "TYPE_IGNORE",
        "TYPE_COMMENT",
        "ERRORTOKEN",
        "COMMENT",
        "NL",
        "ENCODING",
        "N_TOKENS",
        "NT_OFFSET",
        "tokenize",
        "generate_tokens",
        "detect_encoding",
        "untokenize",
        "TokenInfo",
    ]
elif sys.version_info >= (3, 7):
    __all__ = [
        "tok_name",
        "ISTERMINAL",
        "ISNONTERMINAL",
        "ISEOF",
        "ENDMARKER",
        "NAME",
        "NUMBER",
        "STRING",
        "NEWLINE",
        "INDENT",
        "DEDENT",
        "LPAR",
        "RPAR",
        "LSQB",
        "RSQB",
        "COLON",
        "COMMA",
        "SEMI",
        "PLUS",
        "MINUS",
        "STAR",
        "SLASH",
        "VBAR",
        "AMPER",
        "LESS",
        "GREATER",
        "EQUAL",
        "DOT",
        "PERCENT",
        "LBRACE",
        "RBRACE",
        "EQEQUAL",
        "NOTEQUAL",
        "LESSEQUAL",
        "GREATEREQUAL",
        "TILDE",
        "CIRCUMFLEX",
        "LEFTSHIFT",
        "RIGHTSHIFT",
        "DOUBLESTAR",
        "PLUSEQUAL",
        "MINEQUAL",
        "STAREQUAL",
        "SLASHEQUAL",
        "PERCENTEQUAL",
        "AMPEREQUAL",
        "VBAREQUAL",
        "CIRCUMFLEXEQUAL",
        "LEFTSHIFTEQUAL",
        "RIGHTSHIFTEQUAL",
        "DOUBLESTAREQUAL",
        "DOUBLESLASH",
        "DOUBLESLASHEQUAL",
        "AT",
        "ATEQUAL",
        "RARROW",
        "ELLIPSIS",
        "OP",
        "ERRORTOKEN",
        "COMMENT",
        "NL",
        "ENCODING",
        "N_TOKENS",
        "NT_OFFSET",
        "tokenize",
        "detect_encoding",
        "untokenize",
        "TokenInfo",
    ]
else:
    __all__ = [
        "tok_name",
        "ISTERMINAL",
        "ISNONTERMINAL",
        "ISEOF",
        "ENDMARKER",
        "NAME",
        "NUMBER",
        "STRING",
        "NEWLINE",
        "INDENT",
        "DEDENT",
        "LPAR",
        "RPAR",
        "LSQB",
        "RSQB",
        "COLON",
        "COMMA",
        "SEMI",
        "PLUS",
        "MINUS",
        "STAR",
        "SLASH",
        "VBAR",
        "AMPER",
        "LESS",
        "GREATER",
        "EQUAL",
        "DOT",
        "PERCENT",
        "LBRACE",
        "RBRACE",
        "EQEQUAL",
        "NOTEQUAL",
        "LESSEQUAL",
        "GREATEREQUAL",
        "TILDE",
        "CIRCUMFLEX",
        "LEFTSHIFT",
        "RIGHTSHIFT",
        "DOUBLESTAR",
        "PLUSEQUAL",
        "MINEQUAL",
        "STAREQUAL",
        "SLASHEQUAL",
        "PERCENTEQUAL",
        "AMPEREQUAL",
        "VBAREQUAL",
        "CIRCUMFLEXEQUAL",
        "LEFTSHIFTEQUAL",
        "RIGHTSHIFTEQUAL",
        "DOUBLESTAREQUAL",
        "DOUBLESLASH",
        "DOUBLESLASHEQUAL",
        "AT",
        "ATEQUAL",
        "RARROW",
        "ELLIPSIS",
        "OP",
        "AWAIT",
        "ASYNC",
        "ERRORTOKEN",
        "N_TOKENS",
        "NT_OFFSET",
        "COMMENT",
        "tokenize",
        "detect_encoding",
        "NL",
        "untokenize",
        "ENCODING",
        "TokenInfo",
    ]

if sys.version_info >= (3, 8):
    from token import EXACT_TOKEN_TYPES as EXACT_TOKEN_TYPES
else:
    EXACT_TOKEN_TYPES: dict[str, int]

if sys.version_info < (3, 7):
    COMMENT: int
    NL: int
    ENCODING: int

cookie_re: Pattern[str]
blank_re: Pattern[bytes]

_Position = tuple[int, int]

class _TokenInfo(NamedTuple):
    type: int
    string: str
    start: _Position
    end: _Position
    line: str

class TokenInfo(_TokenInfo):
    @property
    def exact_type(self) -> int: ...

# Backwards compatible tokens can be sequences of a shorter length too
_Token = TokenInfo | Sequence[int | str | _Position]

class TokenError(Exception): ...
class StopTokenizing(Exception): ...  # undocumented

class Untokenizer:
    tokens: list[str]
    prev_row: int
    prev_col: int
    encoding: str | None
    def __init__(self) -> None: ...
    def add_whitespace(self, start: _Position) -> None: ...
    def untokenize(self, iterable: Iterable[_Token]) -> str: ...
    def compat(self, token: Sequence[int | str], iterable: Iterable[_Token]) -> None: ...

# the docstring says "returns bytes" but is incorrect --
# if the ENCODING token is missing, it skips the encode
def untokenize(iterable: Iterable[_Token]) -> Any: ...
def detect_encoding(readline: Callable[[], bytes]) -> tuple[str, Sequence[bytes]]: ...
def tokenize(readline: Callable[[], bytes]) -> Generator[TokenInfo, None, None]: ...
def generate_tokens(readline: Callable[[], str]) -> Generator[TokenInfo, None, None]: ...  # undocumented
def open(filename: StrOrBytesPath | int) -> TextIO: ...
def group(*choices: str) -> str: ...  # undocumented
def any(*choices: str) -> str: ...  # undocumented
def maybe(*choices: str) -> str: ...  # undocumented

Whitespace: str  # undocumented
Comment: str  # undocumented
Ignore: str  # undocumented
Name: str  # undocumented

Hexnumber: str  # undocumented
Binnumber: str  # undocumented
Octnumber: str  # undocumented
Decnumber: str  # undocumented
Intnumber: str  # undocumented
Exponent: str  # undocumented
Pointfloat: str  # undocumented
Expfloat: str  # undocumented
Floatnumber: str  # undocumented
Imagnumber: str  # undocumented
Number: str  # undocumented

def _all_string_prefixes() -> set[str]: ...  # undocumented

StringPrefix: str  # undocumented

Single: str  # undocumented
Double: str  # undocumented
Single3: str  # undocumented
Double3: str  # undocumented
Triple: str  # undocumented
String: str  # undocumented

if sys.version_info < (3, 7):
    Operator: str  # undocumented
    Bracket: str  # undocumented

Special: str  # undocumented
Funny: str  # undocumented

PlainToken: str  # undocumented
Token: str  # undocumented

ContStr: str  # undocumented
PseudoExtras: str  # undocumented
PseudoToken: str  # undocumented

endpats: dict[str, str]  # undocumented
single_quoted: set[str]  # undocumented
triple_quoted: set[str]  # undocumented

tabsize: int  # undocumented
