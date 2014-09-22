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


class MypyFileRepr:
    def __init__(self, eof):
        self.eof = eof


class ImportRepr:
    def __init__(self, import_tok: Any, components: List[List[Token]],
                 as_names: List[Tuple[Token, Token]], commas: List[Token],
                 br: Any) -> None:
        self.import_tok = import_tok
        self.components = components
        self.as_names = as_names
        self.commas = commas
        self.br = br


class ImportFromRepr:
    def __init__(self,
                 from_tok: Any,
                 components: List[Token],
                 import_tok: Any,
                 lparen: Any,
                 names: List[Tuple[List[Token], Token]],
                 rparen: Any, br: Any) -> None:
        # Notes:
        # - lparen and rparen may be empty
        # - in each names tuple, the first item contains tokens for
        #   'name [as name]' and the second item is a comma or empty.
        self.from_tok = from_tok
        self.components = components
        self.import_tok = import_tok
        self.lparen = lparen
        self.names = names
        self.rparen = rparen
        self.br = br


class FuncRepr:
    def __init__(self, def_tok: Any, name: Any, args: 'FuncArgsRepr') -> None:
        # Note: name may be empty.
        self.def_tok = def_tok
        self.name = name
        self.args = args


class FuncArgsRepr:
    """Representation of a set of function arguments."""
    def __init__(self, lseparator: Any, rseparator: Any, arg_names: Any,
                 commas: Any, assigns: Any, asterisk: Any) -> None:
        # Lseparator and rseparator are '(' and ')', respectively.
        self.lseparator = lseparator
        self.rseparator = rseparator
        self.arg_names = arg_names
        self.commas = commas
        self.assigns = assigns
        self.asterisk = asterisk


class VarRepr:
    def __init__(self, name: Any, comma: Any) -> None:
        # Note_ comma may be empty.
        self.name = name
        self.comma = comma


class TypeDefRepr:
    def __init__(self, class_tok: Any, name: Any, lparen: Any, commas: Any,
                 rparen: Any) -> None:
        self.class_tok = class_tok
        self.name = name
        self.lparen = lparen
        self.commas = commas
        self.rparen = rparen


class VarDefRepr:
    def __init__(self, assign: Any, br: Any) -> None:
        # Note: assign may be empty.
        self.assign = assign
        self.br = br


class DecoratorRepr:
    def __init__(self, ats: Any, brs: Any) -> None:
        self.ats = ats
        self.brs = brs


class BlockRepr:
    def __init__(self, colon: Any, br: Any, indent: Any, dedent: Any) -> None:
        self.colon = colon
        self.br = br
        self.indent = indent
        self.dedent = dedent


class GlobalDeclRepr:
    def __init__(self, global_tok: Any, names: List[Token],
                 commas: List[Token], br: Any) -> None:
        self.global_tok = global_tok
        self.names = names
        self.commas = commas
        self.br = br


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
    def __init__(self, for_tok: Any, commas: Any, in_tok: Any,
                 else_tok: Any) -> None:
        self.for_tok = for_tok
        self.commas = commas
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


class ParenExprRepr:
    def __init__(self, lparen: Any, rparen: Any) -> None:
        self.lparen = lparen
        self.rparen = rparen


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


class ListSetExprRepr:
    # [...] or {...}
    def __init__(self, lbracket: Any, commas: List[Token], rbracket: Any,
                 langle: Any, rangle: Any) -> None:
        self.lbracket = lbracket
        self.commas = commas
        self.rbracket = rbracket
        self.langle = langle
        self.rangle = rangle


class TupleExprRepr:
    def __init__(self, lparen: Any, commas: List[Token], rparen: Any) -> None:
        # Note: lparen and rparen may be empty.
        self.lparen = lparen
        self.commas = commas
        self.rparen = rparen


class DictExprRepr:
    def __init__(self, lbrace: Any, colons: List[Token], commas: List[Token],
                 rbrace: Any, langle: Any, type_comma: Any,
                 rangle: Any) -> None:
        self.lbrace = lbrace
        self.colons = colons
        self.commas = commas
        self.rbrace = rbrace
        self.langle = langle
        self.type_comma = type_comma
        self.rangle = rangle


class TypeApplicationRepr:
    def __init__(self, langle: Any, commas: Any, rangle: Any) -> None:
        self.langle = langle
        self.commas = commas
        self.rangle = rangle


class GeneratorExprRepr:
    def __init__(self, for_toks: List[Token], commas: List[Token], in_toks: List[Token],
                 if_toklists: List[List[Token]]) -> None:
        self.for_toks = for_toks
        self.commas = commas
        self.in_toks = in_toks
        self.if_toklists = if_toklists


class ListComprehensionRepr:
    def __init__(self, lbracket: Any, rbracket: Any) -> None:
        self.lbracket = lbracket
        self.rbracket = rbracket
