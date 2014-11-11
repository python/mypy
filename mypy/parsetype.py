"""Type parser"""

from typing import List, Tuple, Union, cast

from mypy.types import (
    Type, UnboundType, TupleType, UnionType, TypeList, AnyType, Callable
)
from mypy.typerepr import CommonTypeRepr, ListTypeRepr
from mypy.lex import Token, Name, StrLit, Break, lex
from mypy import nodes


none = Token('')  # Empty token


class TypeParseError(Exception):
    def __init__(self, token: Token, index: int) -> None:
        super().__init__()
        self.token = token
        self.index = index


def parse_type(tok: List[Token], index: int) -> Tuple[Type, int]:
    """Parse a type.

    Return (type, index after type).
    """

    p = TypeParser(tok, index)
    return p.parse_type(), p.index()


def parse_types(tok: List[Token], index: int) -> Tuple[Type, int]:
    """Parse one or more types separated by commas (optional parentheses).

    Return (type, index after type).
    """

    p = TypeParser(tok, index)
    return p.parse_types(), p.index()


class TypeParser:
    def __init__(self, tok: List[Token], ind: int) -> None:
        self.tok = tok
        self.ind = ind

    def index(self) -> int:
        return self.ind

    def parse_type(self) -> Type:
        """Parse a type."""
        t = self.current_token()
        if t.string == '(':
            return self.parse_parens()
        if isinstance(t, Name):
            return self.parse_named_type()
        elif t.string == '[':
            return self.parse_type_list()
        elif isinstance(t, StrLit):
            # Type escaped as string literal.
            typestr = t.parsed()
            line = t.line
            self.skip()
            try:
                result = parse_str_as_type(typestr, line)
            except TypeParseError as e:
                raise TypeParseError(e.token, self.ind)
            return result
        else:
            self.parse_error()

    def parse_parens(self) -> Type:
        self.expect('(')
        types = self.parse_types()
        self.expect(')')
        return types

    def parse_types(self) -> Type:
        """ Parse either a single type or a comma separated
        list of types as a tuple type. In the latter case, a
        trailing comma is needed when the list contains only
        a single type (and optional otherwise).

        int   ->   int
        int,  ->   TupleType[int]
        int, int, int  ->  TupleType[int, int, int]
        """
        type = self.parse_type()
        if self.current_token_str() == ',':
            items = [type]
            while self.current_token_str() == ',':
                self.skip()
                if self.current_token_str() == ')':
                    break
                items.append(self.parse_type())
            type = TupleType(items, None)
        return type

    def parse_type_list(self) -> TypeList:
        """Parse type list [t, ...]."""
        lbracket = self.expect('[')
        commas = []  # type: List[Token]
        items = []  # type: List[Type]
        while self.current_token_str() != ']':
            t = self.parse_type()
            items.append(t)
            if self.current_token_str() != ',':
                break
            commas.append(self.skip())
        rbracket = self.expect(']')
        return TypeList(items, line=lbracket.line)

    def parse_named_type(self) -> Type:
        line = self.current_token().line
        name = ''
        components = []  # type: List[Token]

        components.append(self.expect_type(Name))
        name += components[-1].string

        while self.current_token_str() == '.':
            components.append(self.skip())
            t = self.expect_type(Name)
            components.append(t)
            name += '.' + t.string

        langle, rangle = none, none
        commas = []  # type: List[Token]
        args = []  # type: List[Type]
        if self.current_token_str() == '[':
            lbracket = self.skip()

            while True:
                typ = self.parse_type()
                args.append(typ)
                if self.current_token_str() != ',':
                    break
                commas.append(self.skip())

            rbracket = self.expect(']')

        typ = UnboundType(name, args, line, CommonTypeRepr(components,
                                                           langle,
                                                           commas, rangle))
        return typ

    # Helpers

    def skip(self) -> Token:
        self.ind += 1
        return self.tok[self.ind - 1]

    def expect(self, string: str) -> Token:
        if self.tok[self.ind].string == string:
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()

    def expect_type(self, typ: type) -> Token:
        if isinstance(self.current_token(), typ):
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()

    def current_token(self) -> Token:
        return self.tok[self.ind]

    def current_token_str(self) -> str:
        return self.current_token().string

    def parse_error(self) -> None:
        raise TypeParseError(self.tok[self.ind], self.ind)


def parse_str_as_type(typestr: str, line: int) -> Type:
    """Parse a type represented as a string.

    Raise TypeParseError on parse error.
    """

    typestr = typestr.strip()
    tokens = lex(typestr, line)
    result, i = parse_type(tokens, 0)
    if i < len(tokens) - 2:
        raise TypeParseError(tokens[i], i)
    return result


def parse_signature(tokens: List[Token]) -> Tuple[Callable, int]:
    """Parse signature of form (argtype, ...) -> ...

    Return tuple (signature type, token index).
    """
    i = 0
    if tokens[i].string != '(':
        raise TypeParseError(tokens[i], i)
    i += 1
    arg_types = List[Type]()
    arg_kinds = List[int]()
    while tokens[i].string != ')':
        if tokens[i].string == '*':
            arg_kinds.append(nodes.ARG_STAR)
            i += 1
        elif tokens[i].string == '**':
            arg_kinds.append(nodes.ARG_STAR2)
            i += 1
        else:
            arg_kinds.append(nodes.ARG_POS)
        arg, i = parse_type(tokens, i)
        arg_types.append(arg)
        next = tokens[i].string
        if next not in ',)':
            raise TypeParseError(tokens[i], i)
        if next == ',':
            i += 1
    i += 1
    if tokens[i].string != '->':
        raise TypeParseError(tokens[i], i)
    i += 1
    ret_type, i = parse_type(tokens, i)
    return Callable(arg_types,
                    arg_kinds,
                    [None] * len(arg_types),
                    ret_type, None), i
