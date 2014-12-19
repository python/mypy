"""Classes for storing the lexical token information of nodes.

This is used for outputting the original source code represented by the nodes
(including original formatting and comments).

Each node representation usually only contains tokens directly associated
with that node (terminals). All members are Tokens or lists of Tokens,
unless explicitly mentioned otherwise.

If a representation has a Break token, the member name is br.
"""

from typing import Any, List, Tuple, Undefined

from mypy.lex import Token


class IndexExprRepr:
    def __init__(self, lbracket: Any, rbracket: Any) -> None:
        self.lbracket = lbracket
        self.rbracket = rbracket


class SliceExprRepr:
    def __init__(self, colon: Any, colon2: Any) -> None:
        self.colon = colon
        self.colon2 = colon2


class UnaryExprRepr:
    def __init__(self, op: Any) -> None:
        self.op = op


class OpExprRepr:
    def __init__(self, op: Any) -> None:
        self.op = op


class CastExprRepr:
    def __init__(self, lparen: Any, rparen: Any) -> None:
        self.lparen = lparen
        self.rparen = rparen


class FuncExprRepr:
    def __init__(self, lambda_tok: Any, colon: Any, args: Any) -> None:
        self.lambda_tok = lambda_tok
        self.colon = colon
        self.args = args


class TupleExprRepr:
    def __init__(self, lparen: Any, commas: List[Token], rparen: Any) -> None:
        # Note: lparen and rparen may be empty.
        self.lparen = lparen
        self.commas = commas
        self.rparen = rparen


class TypeApplicationRepr:
    def __init__(self, langle: Any, commas: Any, rangle: Any) -> None:
        self.langle = langle
        self.commas = commas
        self.rangle = rangle
