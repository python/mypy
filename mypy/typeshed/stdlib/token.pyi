import sys

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
    ]

ENDMARKER: int
NAME: int
NUMBER: int
STRING: int
NEWLINE: int
INDENT: int
DEDENT: int
LPAR: int
RPAR: int
LSQB: int
RSQB: int
COLON: int
COMMA: int
SEMI: int
PLUS: int
MINUS: int
STAR: int
SLASH: int
VBAR: int
AMPER: int
LESS: int
GREATER: int
EQUAL: int
DOT: int
PERCENT: int
LBRACE: int
RBRACE: int
EQEQUAL: int
NOTEQUAL: int
LESSEQUAL: int
GREATEREQUAL: int
TILDE: int
CIRCUMFLEX: int
LEFTSHIFT: int
RIGHTSHIFT: int
DOUBLESTAR: int
PLUSEQUAL: int
MINEQUAL: int
STAREQUAL: int
SLASHEQUAL: int
PERCENTEQUAL: int
AMPEREQUAL: int
VBAREQUAL: int
CIRCUMFLEXEQUAL: int
LEFTSHIFTEQUAL: int
RIGHTSHIFTEQUAL: int
DOUBLESTAREQUAL: int
DOUBLESLASH: int
DOUBLESLASHEQUAL: int
AT: int
RARROW: int
ELLIPSIS: int
ATEQUAL: int
if sys.version_info < (3, 7) or sys.version_info >= (3, 8):
    # These were removed in Python 3.7 but added back in Python 3.8
    AWAIT: int
    ASYNC: int
OP: int
ERRORTOKEN: int
N_TOKENS: int
NT_OFFSET: int
tok_name: dict[int, str]
if sys.version_info >= (3, 7):
    COMMENT: int
    NL: int
    ENCODING: int
if sys.version_info >= (3, 8):
    TYPE_COMMENT: int
    TYPE_IGNORE: int
    COLONEQUAL: int
    EXACT_TOKEN_TYPES: dict[str, int]
if sys.version_info >= (3, 10):
    SOFT_KEYWORD: int

def ISTERMINAL(x: int) -> bool: ...
def ISNONTERMINAL(x: int) -> bool: ...
def ISEOF(x: int) -> bool: ...
