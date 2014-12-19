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


class ExpressionStmtRepr:
    def __init__(self, br: Any) -> None:
        self.br = br


class AssignmentStmtRepr:
    def __init__(self, assigns: List[Token], br: Any) -> None:
        self.assigns = assigns
        self.br = br


class OperatorAssignmentStmtRepr:
    def __init__(self, assign: Any, br: Any) -> None:
        self.assign = assign
        self.br = br


class WhileStmtRepr:
    def __init__(self, while_tok: Any, else_tok: Any) -> None:
        self.while_tok = while_tok
        self.else_tok = else_tok


class ForStmtRepr:
    def __init__(self, for_tok: Any, in_tok: Any,
                 else_tok: Any) -> None:
        self.for_tok = for_tok
        self.in_tok = in_tok
        self.else_tok = else_tok


class SimpleStmtRepr:
    """Representation for break, continue, pass, return and assert."""
    def __init__(self, keyword: Any, br: Any) -> None:
        self.keyword = keyword
        self.br = br


class IfStmtRepr:
    def __init__(self, if_tok: Any, elif_toks: Any, else_tok: Any) -> None:
        # Note: else_tok may be empty.
        self.if_tok = if_tok
        self.elif_toks = elif_toks
        self.else_tok = else_tok


class RaiseStmtRepr:
    def __init__(self, raise_tok: Any, from_tok: Any, br: Any) -> None:
        self.raise_tok = raise_tok
        self.from_tok = from_tok
        self.br = br


class TryStmtRepr:
    def __init__(self, try_tok: Any, except_toks: Any, name_toks: Any,
                 as_toks: Any, else_tok: Any, finally_tok: Any) -> None:
        self.try_tok = try_tok
        self.except_toks = except_toks
        self.name_toks = name_toks
        self.as_toks = as_toks
        self.else_tok = else_tok
        self.finally_tok = finally_tok


class WithStmtRepr:
    def __init__(self, with_tok: Any, as_toks: Any, commas: Any) -> None:
        self.with_tok = with_tok
        self.as_toks = as_toks
        self.commas = commas


class IntExprRepr:
    def __init__(self, int: Any) -> None:
        self.int = int


class StrExprRepr:
    def __init__(self, string: List[Token]) -> None:
        self.string = string


class FloatExprRepr:
    def __init__(self, float: Any) -> None:
        self.float = float


class ComplexExprRepr:
    def __init__(self, complex: Any) -> None:
        self.complex = complex


class EllipsisNodeRepr:
    def __init__(self, ellipsis_tok) -> None:
        self.ellipsis = ellipsis_tok


class ParenExprRepr:
    def __init__(self, lparen: Any, rparen: Any) -> None:
        self.lparen = lparen
        self.rparen = rparen


class StarExprRepr:
    def __init__(self, star: Any) -> None:
        self.star = star


class NameExprRepr:
    def __init__(self, id: Any) -> None:
        self.id = id


class MemberExprRepr:
    def __init__(self, dot: Any, name: Any) -> None:
        self.dot = dot
        self.name = name

class ComparisonExprRepr:
    def __init__(self, operators: List[Any]) -> None:
        # List of tupples of (op, op2).
        # Note: op2 may be empty; it is used for "is not" and "not in".
        self.operators = operators

class CallExprRepr:
    def __init__(self, lparen: Any, commas: List[Token], star: Any, star2: Any,
                 keywords: List[List[Token]], rparen: Any) -> None:
        # Asterisk may be empty.
        self.lparen = lparen
        self.commas = commas
        self.star = star
        self.star2 = star2
        self.keywords = keywords
        self.rparen = rparen


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


class SuperExprRepr:
    def __init__(self, super_tok: Any, lparen: Any, rparen: Any, dot: Any,
                 name: Any) -> None:
        self.super_tok = super_tok
        self.lparen = lparen
        self.rparen = rparen
        self.dot = dot
        self.name = name


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
