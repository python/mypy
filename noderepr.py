from lex import Token


# Classes for storing the lexical token information of nodes. This is used
# for outputting the original source code represented by the nodes (including
# original formatting and comments).
#
# Each node representation usually only contains tokens directly associated
# with that node (terminals). All members are Tokens or lists of Tokens,
# unless explicitly mentioned otherwise.
#
# If a representation has a Break token, the member name is br.


class MypyFileRepr:
    def __init__(self, eof):
        self.eof = eof


class ImportRepr:
    void __init__(self, any import_tok, list<list<Token>> components,
                  list<tuple<Token, Token>> as_names, list<Token> commas,
                  any br):
        self.import_tok = import_tok
        self.components = components
        self.as_names = as_names
        self.commas = commas
        self.br = br


class ImportFromRepr:
    # Notes:
    #  - lparen and rparen may be empty
    #  - in each names tuple, the first item contains tokens for
    #    'name [as name]' and the second item is a comma or empty.
    void __init__(self,
                  any from_tok,
                  list<Token> components,
                  any import_tok,
                  any lparen,
                  list<tuple<list<Token>, Token>> names,
                  any rparen, any br):
        self.from_tok = from_tok
        self.components = components
        self.import_tok = import_tok
        self.lparen = lparen
        self.names = names
        self.rparen = rparen
        self.br = br


class FuncRepr:
    # Note: name may be empty.
    void __init__(self, any def_tok, any name, FuncArgsRepr args):
        self.def_tok = def_tok
        self.name = name
        self.args = args


# Representation of a set of function arguments.
class FuncArgsRepr:
    # Lseparator and rseparator are '(' and ')', respectively.
    void __init__(self, any lseparator, any rseparator, any arg_names,
                  any commas, any assigns, any asterisk):
        self.lseparator = lseparator
        self.rseparator = rseparator
        self.arg_names = arg_names
        self.commas = commas
        self.assigns = assigns
        self.asterisk = asterisk


class VarRepr:
    # Note_ comma may be empty.
    void __init__(self, any name, any comma):
        self.name = name
        self.comma = comma


class TypeDefRepr:
    void __init__(self, any class_tok, any name, any lparen, any commas,
                  any rparen):
        self.class_tok = class_tok
        self.name = name
        self.lparen = lparen
        self.commas = commas
        self.rparen = rparen


class VarDefRepr:
    # Note: assign may be empty.
    void __init__(self, any assign, any br):
        self.assign = assign
        self.br = br


class DecoratorRepr:
    void __init__(self, any at, any br):
        self.at = at
        self.br = br


class BlockRepr:
    void __init__(self, any colon, any br, any indent, any dedent):
        self.colon = colon
        self.br = br
        self.indent = indent
        self.dedent = dedent


class GlobalDeclRepr:
    any global_tok
    any names   # list<Token>
    any commas  # list<Token>
    any br
    
    void __init__(self, any global_tok, any names, any commas, any br):
        self.global_tok = global_tok
        self.names = names
        self.commas = commas
        self.br = br


class ExpressionStmtRepr:
    void __init__(self, any br):
        self.br = br


class AssignmentStmtRepr:
    any assigns       # list<Token>
    any br
    
    void __init__(self, any assigns, any br):
        self.assigns = assigns
        self.br = br


class OperatorAssignmentStmtRepr:
    void __init__(self, any assign, any br):
        self.assign = assign
        self.br = br


class WhileStmtRepr:
    void __init__(self, any while_tok, any else_tok):
        self.while_tok = while_tok
        self.else_tok = else_tok


class ForStmtRepr:
    void __init__(self, any for_tok, any in_tok, any else_tok):
        self.for_tok = for_tok
        self.in_tok = in_tok
        self.else_tok = else_tok


# break/continue/pass/return/assert
class SimpleStmtRepr:
    void __init__(self, any keyword, any br):
        self.keyword = keyword
        self.br = br


class IfStmtRepr:
    any if_tok
    any elif_toks   # list<Token>
    any else_tok    # May be empty
    
    void __init__(self, any if_tok, any elif_toks, any else_tok):
        self.if_tok = if_tok
        self.elif_toks = elif_toks
        self.else_tok = else_tok


class RaiseStmtRepr:
    void __init__(self, any raise_tok, any from_tok, any br):
        self.raise_tok = raise_tok
        self.from_tok = from_tok
        self.br = br


class TryStmtRepr:
    any try_tok
    any except_toks  # list<Token>
    any name_toks    # list<Token>, may be empty
    any as_toks      # list<Token>, may be empty
    any else_tok
    any finally_tok
    
    void __init__(self, any try_tok, any except_toks, any name_toks,
                  any as_toks, any else_tok, any finally_tok):
        self.try_tok = try_tok
        self.except_toks = except_toks
        self.name_toks = name_toks
        self.as_toks = as_toks
        self.else_tok = else_tok
        self.finally_tok = finally_tok


class WithStmtRepr:
    void __init__(self, any with_tok, any as_toks, any commas):
        self.with_tok = with_tok
        self.as_toks = as_toks
        self.commas = commas


class IntExprRepr:
    void __init__(self, any int):
        self.int = int


class StrExprRepr:
    any string  # list<Token>
    
    void __init__(self, any string):
        self.string = string


class FloatExprRepr:
    void __init__(self, any float):
        self.float = float


class ParenExprRepr:
    void __init__(self, any lparen, any rparen):
        self.lparen = lparen
        self.rparen = rparen


class LvalueRepr:
    any lparens  # list<Token>
    any rparens  # list<Token>
    any base
    
    void __init__(self, any lparens, any rparens, any base):
        self.lparens = lparens
        self.rparens = rparens
        self.base = base


class NameExprRepr:
    void __init__(self, any id):
        self.id = id


class MemberExprRepr:
    void __init__(self, any dot, any name):
        self.dot = dot
        self.name = name


class CallExprRepr:
    any lparen
    list<Token> commas
    any asterisk # May be empty
    list<Token> assigns
    any rparen
    
    void __init__(self, any lparen, list<Token> commas, any asterisk,
                  list<Token> assigns, any rparen):
        self.lparen = lparen
        self.commas = commas
        self.asterisk = asterisk
        self.assigns = assigns
        self.rparen = rparen


class IndexExprRepr:
    void __init__(self, any lbracket, any rbracket):
        self.lbracket = lbracket
        self.rbracket = rbracket


class SliceExprRepr:
    void __init__(self, any colon, any colon2):
        self.colon = colon
        self.colon2 = colon2


class UnaryExprRepr:
    void __init__(self, any op):
        self.op = op


class OpExprRepr:
    any op
    any op2    # May be empty; for "is not" and "not in"
    
    void __init__(self, any op, any op2):
        self.op = op
        self.op2 = op2


class CastExprRepr:
    void __init__(self, any lparen, any rparen):
        self.lparen = lparen
        self.rparen = rparen


class FuncExprRepr:
    void __init__(self, any lambda_tok, any colon, any args):
        self.lambda_tok = lambda_tok
        self.colon = colon
        self.args = args


class SuperExprRepr:
    void __init__(self, any super_tok, any lparen, any rparen, any dot,
                  any name):
        self.super_tok = super_tok
        self.lparen = lparen
        self.rparen = rparen
        self.dot = dot
        self.name = name


class ListExprRepr:
    any lbracket
    any commas    # list<Token>
    any rbracket
    any langle
    any rangle
    
    void __init__(self, any lbracket, any commas, any rbracket, any langle,
                  any rangle):
        self.lbracket = lbracket
        self.commas = commas
        self.rbracket = rbracket
        self.langle = langle
        self.rangle = rangle


class TupleExprRepr:
    any lparen  # May be empty
    any commas  # list<Token>
    any rparen  # May be empty
    
    void __init__(self, any lparen, any commas, any rparen):
        self.lparen = lparen
        self.commas = commas
        self.rparen = rparen


class DictExprRepr:
    any lbrace
    any colons  # list<Token>
    any commas  # list<Token>
    any rbrace
    any langle
    any type_comma
    any rangle
    
    void __init__(self, any lbrace, any colons, any commas, any rbrace,
                  any langle, any type_comma, any rangle):
        self.lbrace = lbrace
        self.colons = colons
        self.commas = commas
        self.rbrace = rbrace
        self.langle = langle
        self.type_comma = type_comma
        self.rangle = rangle


class AnnotationRepr: pass


class TypeApplicationRepr:
    void __init__(self, any langle, any commas, any rangle):
        self.langle = langle
        self.commas = commas
        self.rangle = rangle
