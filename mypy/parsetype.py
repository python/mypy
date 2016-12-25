"""Type parser"""

from typing import List, Tuple, Union, Optional, TypeVar, cast

import typing

from mypy.types import (
    Type, UnboundType, TupleType, ArgumentList, CallableType, StarType,
    EllipsisType, AnyType, ArgNameException, ArgKindException
)

from mypy.sharedparse import ARG_KINDS_BY_CONSTRUCTOR, STAR_ARG_CONSTRUCTORS

from mypy.lex import Token, Name, StrLit, lex
from mypy import nodes

T = TypeVar('T', bound=Token)

none = Token('')  # Empty token


class TypeParseError(Exception):
    def __init__(self, token: Token, index: int, message: Optional[str] = None) -> None:
        super().__init__()
        self.token = token
        self.index = index
        self.message = message


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
            return self.parse_argument_list()
        elif t.string == '*':
            return self.parse_star_type()
        elif t.string == '...':
            return self.parse_ellipsis_type()
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
            raise self.parse_error()

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
            type = TupleType(items, None, type.line, implicit=True)
        return type

    def parse_argument_spec(self) -> Tuple[Type, Optional[str], int]:
        current = self.current_token()
        nxt = self.next_token()
        # This is a small recreation of a subset of parsing a CallExpr; just
        # enough to parse what happens in an arugment list.
        # TODO: Doesn't handle an explicit name of None yet.
        if isinstance(current, Name) and nxt is not None and nxt.string == '(':
            arg_const = self.expect_type(Name).string
            name = None  # type: Optional[str]
            typ = AnyType(implicit=True)  # type: Type
            try:
                kind = ARG_KINDS_BY_CONSTRUCTOR[arg_const]
            except KeyError:
                raise self.parse_error("Unknown argument constructor {}".format(arg_const))
            name, typ = self.parse_arg_args(read_name = arg_const not in STAR_ARG_CONSTRUCTORS)
            return typ, name, kind
        else:
            return self.parse_type(), None, nodes.ARG_POS

    def parse_arg_args(self, *, read_name: bool) -> Tuple[Optional[str], Optional[Type]]:
        self.expect('(')
        name = None  # type: Optional[str]
        typ = AnyType(implicit=True)  # type: Type
        i = 0
        while self.current_token_str() != ')':
            if i > 0:
                self.expect(',')
            if self.next_token() and self.next_token().string == '=':
                arg_arg_name = self.current_token_str()
                if arg_arg_name == 'name' and read_name:
                    self.expect('name')
                    self.expect('=')
                    if self.current_token_str() == 'None':
                        self.expect('None')
                    else:
                        name = self.expect_type(StrLit).parsed()
                elif arg_arg_name == 'typ':
                    self.expect('typ')
                    self.expect('=')
                    typ = self.parse_type()
                else:
                    raise self.parse_error(
                        'Unexpected argument "{}" for argument constructor'.format(arg_arg_name))
            elif i == 0 and read_name:
                if self.current_token_str() == 'None':
                    self.expect('None')
                else:
                    name = self.expect_type(StrLit).parsed()
            elif i == 0 and not read_name or i == 1 and read_name:
                typ = self.parse_type()
            else:
                raise self.parse_error("Unexpected argument for argument constructor")
            i += 1
        self.expect(')')
        return name, typ

    def parse_argument_list(self) -> ArgumentList:
        """Parse type list [t, ...]."""
        lbracket = self.expect('[')
        commas = []  # type: List[Token]
        items = []  # type: List[Type]
        names = []  # type: List[Optional[str]]
        kinds = []  # type: List[int]
        while self.current_token_str() != ']':
            t, name, kind = self.parse_argument_spec()
            items.append(t)
            names.append(name)
            kinds.append(kind)

            if self.current_token_str() != ',':
                break
            commas.append(self.skip())
        self.expect(']')
        return ArgumentList(items, names, kinds, line=lbracket.line)

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

        commas = []  # type: List[Token]
        args = []  # type: List[Type]
        if self.current_token_str() == '[':
            self.skip()
            while True:
                typ = self.parse_type()
                args.append(typ)
                if self.current_token_str() != ',':
                    break
                commas.append(self.skip())

            self.expect(']')

        typ = UnboundType(name, args, line)
        return typ

    def parse_star_type(self) -> Type:
        star = self.expect('*')
        type = self.parse_type()
        return StarType(type, star.line)

    def parse_ellipsis_type(self) -> Type:
        ellipsis = self.expect('...')
        return EllipsisType(ellipsis.line)

    # Helpers

    def skip(self) -> Token:
        self.ind += 1
        return self.tok[self.ind - 1]

    def expect(self, string: str) -> Token:
        if self.tok[self.ind].string == string:
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            raise self.parse_error()

    def expect_type(self, typ: typing.Type[T]) -> T:
        if isinstance(self.current_token(), typ):
            self.ind += 1
            return cast(T, self.tok[self.ind - 1])
        else:
            raise self.parse_error()

    def current_token(self) -> Token:
        return self.tok[self.ind]

    def next_token(self) -> Optional[Token]:
        if self.ind + 1 >= len(self.tok):
            return None
        return self.tok[self.ind + 1]

    def current_token_str(self) -> str:
        return self.current_token().string

    def parse_error(self, message: Optional[str] = None) -> TypeParseError:
        return TypeParseError(self.tok[self.ind], self.ind, message=message)


def parse_str_as_type(typestr: str, line: int) -> Type:
    """Parse a type represented as a string.

    Raise TypeParseError on parse error.
    """

    typestr = typestr.strip()
    tokens = lex(typestr, line)[0]
    result, i = parse_type(tokens, 0)
    if i < len(tokens) - 2:
        raise TypeParseError(tokens[i], i)
    return result


def parse_signature(tokens: List[Token]) -> Tuple[CallableType, int]:
    """Parse signature of form (argtype, ...) -> ...

    Return tuple (signature type, token index).
    """
    i = 0
    if tokens[i].string != '(':
        raise TypeParseError(tokens[i], i)
    begin = tokens[i]
    begin_idx = i
    i += 1
    arg_types = []  # type: List[Type]
    arg_kinds = []  # type: List[int]
    encountered_ellipsis = False
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

        # Check for ellipsis. If it exists, assert it's the only arg_type.
        # Disallow '(..., int) -> None' for example.
        if isinstance(arg, EllipsisType):
            encountered_ellipsis = True
        if encountered_ellipsis and len(arg_types) != 1:
            raise TypeParseError(tokens[i], i,
                                 "Ellipses cannot accompany other argument types"
                                 " in function type signature.")

        if next not in ',)':
            raise TypeParseError(tokens[i], i)
        if next == ',':
            i += 1
    i += 1
    if tokens[i].string != '->':
        raise TypeParseError(tokens[i], i)
    i += 1
    ret_type, i = parse_type(tokens, i)
    try:
        return CallableType(arg_types,
                            arg_kinds,
                            [None] * len(arg_types),
                            ret_type, None,
                            is_ellipsis_args=encountered_ellipsis), i
    except (ArgKindException, ArgNameException) as e:
        raise TypeParseError(begin, begin_idx, e.message)
