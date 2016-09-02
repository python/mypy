"""Expression type checker. This file is conceptually part of ExpressionChecker and TypeChecker."""

import re

from typing import cast, List, Tuple, Dict, Callable

from mypy.types import (
    Type, AnyType, TupleType, Instance, UnionType
)
from mypy.nodes import (
    Node, StrExpr, BytesExpr, TupleExpr, DictExpr, Context
)
if False:
    # break import cycle only needed for mypy
    import mypy.checker
    import mypy.checkexpr
from mypy import messages
from mypy.messages import MessageBuilder


class ConversionSpecifier:
    def __init__(self, key: str, flags: str, width: str, precision: str, type: str) -> None:
        self.key = key
        self.flags = flags
        self.width = width
        self.precision = precision
        self.type = type

    def has_key(self) -> bool:
        return self.key is not None

    def has_star(self) -> bool:
        return self.width == '*' or self.precision == '*'


class StringFormatterChecker:
    """String interpolation/formatter type checker.

    This class works closely together with checker.ExpressionChecker.
    """

    # Some services are provided by a TypeChecker instance.
    chk = None  # type: mypy.checker.TypeChecker
    # This is shared with TypeChecker, but stored also here for convenience.
    msg = None  # type: MessageBuilder
    # Some services are provided by a ExpressionChecker instance.
    exprchk = None  # type: mypy.checkexpr.ExpressionChecker

    def __init__(self,
                 exprchk: 'mypy.checkexpr.ExpressionChecker',
                 chk: 'mypy.checker.TypeChecker',
                 msg: MessageBuilder) -> None:
        """Construct an expression type checker."""
        self.chk = chk
        self.exprchk = exprchk
        self.msg = msg

    def check_str_interpolation(self, str: StrExpr, replacements: Node) -> Type:
        """Check the types of the 'replacements' in a string interpolation
        expression: str % replacements
        """
        specifiers = self.parse_conversion_specifiers(str.value)
        has_mapping_keys = self.analyze_conversion_specifiers(specifiers, str)
        if has_mapping_keys is None:
            pass  # Error was reported
        elif has_mapping_keys:
            self.check_mapping_str_interpolation(specifiers, replacements)
        else:
            self.check_simple_str_interpolation(specifiers, replacements)
        return self.named_type('builtins.str')

    def parse_conversion_specifiers(self, format: str) -> List[ConversionSpecifier]:
        key_regex = r'(\(([^()]*)\))?'  # (optional) parenthesised sequence of characters
        flags_regex = r'([#0\-+ ]*)'  # (optional) sequence of flags
        width_regex = r'(\*|[1-9][0-9]*)?'  # (optional) minimum field width (* or numbers)
        precision_regex = r'(?:\.(\*|[0-9]+)?)?'  # (optional) . followed by * of numbers
        length_mod_regex = r'[hlL]?'  # (optional) length modifier (unused)
        type_regex = r'(.)?'  # conversion type
        regex = ('%' + key_regex + flags_regex + width_regex +
                 precision_regex + length_mod_regex + type_regex)
        specifiers = []  # type: List[ConversionSpecifier]
        for parens_key, key, flags, width, precision, type in re.findall(regex, format):
            if parens_key == '':
                key = None
            specifiers.append(ConversionSpecifier(key, flags, width, precision, type))
        return specifiers

    def analyze_conversion_specifiers(self, specifiers: List[ConversionSpecifier],
                                      context: Context) -> bool:
        has_star = any(specifier.has_star() for specifier in specifiers)
        has_key = any(specifier.has_key() for specifier in specifiers)
        all_have_keys = all(
            specifier.has_key() or specifier.type == '%' for specifier in specifiers
        )

        if has_key and has_star:
            self.msg.string_interpolation_with_star_and_key(context)
            return None
        if has_key and not all_have_keys:
            self.msg.string_interpolation_mixing_key_and_non_keys(context)
            return None
        return has_key

    def check_simple_str_interpolation(self, specifiers: List[ConversionSpecifier],
                                       replacements: Node) -> None:
        checkers = self.build_replacement_checkers(specifiers, replacements)
        if checkers is None:
            return

        rhs_type = self.accept(replacements)
        rep_types = []  # type: List[Type]
        if isinstance(rhs_type, TupleType):
            rep_types = rhs_type.items
        elif isinstance(rhs_type, AnyType):
            return
        else:
            rep_types = [rhs_type]

        if len(checkers) > len(rep_types):
            self.msg.too_few_string_formatting_arguments(replacements)
        elif len(checkers) < len(rep_types):
            self.msg.too_many_string_formatting_arguments(replacements)
        else:
            if len(checkers) == 1:
                check_node, check_type = checkers[0]
                if isinstance(rhs_type, TupleType) and len(rhs_type.items) == 1:
                    check_type(rhs_type.items[0])
                else:
                    check_node(replacements)
            elif isinstance(replacements, TupleExpr):
                for checks, rep_node in zip(checkers, replacements.items):
                    check_node, check_type = checks
                    check_node(rep_node)
            else:
                for checks, rep_type in zip(checkers, rep_types):
                    check_node, check_type = checks
                    check_type(rep_type)

    def check_mapping_str_interpolation(self, specifiers: List[ConversionSpecifier],
                                       replacements: Node) -> None:
        dict_with_only_str_literal_keys = (isinstance(replacements, DictExpr) and
                                          all(isinstance(k, (StrExpr, BytesExpr))
                                              for k, v in replacements.items))
        if dict_with_only_str_literal_keys:
            mapping = {}  # type: Dict[str, Type]
            for k, v in cast(DictExpr, replacements).items:
                key_str = cast(StrExpr, k).value
                mapping[key_str] = self.accept(v)

            for specifier in specifiers:
                if specifier.type == '%':
                    # %% is allowed in mappings, no checking is required
                    continue
                if specifier.key not in mapping:
                    self.msg.key_not_in_mapping(specifier.key, replacements)
                    return
                rep_type = mapping[specifier.key]
                expected_type = self.conversion_type(specifier.type, replacements)
                if expected_type is None:
                    return
                self.chk.check_subtype(rep_type, expected_type, replacements,
                                       messages.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
                                       'expression has type',
                                       'placeholder with key \'%s\' has type' % specifier.key)
        else:
            rep_type = self.accept(replacements)
            dict_type = self.chk.named_generic_type('builtins.dict',
                                            [AnyType(), AnyType()])
            self.chk.check_subtype(rep_type, dict_type, replacements,
                                   messages.FORMAT_REQUIRES_MAPPING,
                                   'expression has type', 'expected type for mapping is')

    def build_replacement_checkers(self, specifiers: List[ConversionSpecifier],
                                   context: Context) -> List[Tuple[Callable[[Node], None],
                                                                   Callable[[Type], None]]]:
        checkers = []  # type: List[Tuple[Callable[[Node], None], Callable[[Type], None]]]
        for specifier in specifiers:
            checker = self.replacement_checkers(specifier, context)
            if checker is None:
                return None
            checkers.extend(checker)
        return checkers

    def replacement_checkers(self, specifier: ConversionSpecifier,
                             context: Context) -> List[Tuple[Callable[[Node], None],
                                                             Callable[[Type], None]]]:
        """Returns a list of tuples of two functions that check whether a replacement is
        of the right type for the specifier. The first functions take a node and checks
        its type in the right type context. The second function just checks a type.
        """
        checkers = []  # type: List[ Tuple[ Callable[[Node], None], Callable[[Type], None] ] ]

        if specifier.width == '*':
            checkers.append(self.checkers_for_star(context))
        if specifier.precision == '*':
            checkers.append(self.checkers_for_star(context))
        if specifier.type == 'c':
            c = self.checkers_for_c_type(specifier.type, context)
            if c is None:
                return None
            checkers.append(c)
        elif specifier.type != '%':
            c = self.checkers_for_regular_type(specifier.type, context)
            if c is None:
                return None
            checkers.append(c)
        return checkers

    def checkers_for_star(self, context: Context) -> Tuple[Callable[[Node], None],
                                                           Callable[[Type], None]]:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with a star in a conversion specifier
        """
        expected = self.named_type('builtins.int')

        def check_type(type: Type = None) -> None:
            expected = self.named_type('builtins.int')
            self.chk.check_subtype(type, expected, context, '* wants int')

        def check_node(node: Node) -> None:
            type = self.accept(node, expected)
            check_type(type)

        return check_node, check_type

    def checkers_for_regular_type(self, type: str,
                                  context: Context) -> Tuple[Callable[[Node], None],
                                                             Callable[[Type], None]]:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with 'type'. Return None in case of an
        """
        expected_type = self.conversion_type(type, context)
        if expected_type is None:
            return None

        def check_type(type: Type = None) -> None:
            self.chk.check_subtype(type, expected_type, context,
                              messages.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
                              'expression has type', 'placeholder has type')

        def check_node(node: Node) -> None:
            type = self.accept(node, expected_type)
            check_type(type)

        return check_node, check_type

    def checkers_for_c_type(self, type: str, context: Context) -> Tuple[Callable[[Node], None],
                                                                        Callable[[Type], None]]:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with 'type' that is a character type
        """
        expected_type = self.conversion_type(type, context)
        if expected_type is None:
            return None

        def check_type(type: Type = None) -> None:
            self.chk.check_subtype(type, expected_type, context,
                              messages.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
                              'expression has type', 'placeholder has type')

        def check_node(node: Node) -> None:
            """int, or str with length 1"""
            type = self.accept(node, expected_type)
            if isinstance(node, (StrExpr, BytesExpr)) and len(cast(StrExpr, node).value) != 1:
                self.msg.requires_int_or_char(context)
            check_type(type)

        return check_node, check_type

    def conversion_type(self, p: str, context: Context) -> Type:
        """Return the type that is accepted for a string interpolation
        conversion specifier type.

        Note that both Python's float (e.g. %f) and integer (e.g. %d)
        specifier types accept both float and integers.
        """
        if p in ['s', 'r']:
            return AnyType()
        elif p in ['d', 'i', 'o', 'u', 'x', 'X',
                   'e', 'E', 'f', 'F', 'g', 'G']:
            return UnionType([self.named_type('builtins.int'),
                              self.named_type('builtins.float')])
        elif p in ['c']:
            return UnionType([self.named_type('builtins.int'),
                              self.named_type('builtins.float'),
                              self.named_type('builtins.str')])
        else:
            self.msg.unsupported_placeholder(p, context)
            return None

    #
    # Helpers
    #

    def named_type(self, name: str) -> Instance:
        """Return an instance type with type given by the name and no type
        arguments. Alias for TypeChecker.named_type.
        """
        return self.chk.named_type(name)

    def accept(self, node: Node, context: Type = None) -> Type:
        """Type check a node. Alias for TypeChecker.accept."""
        return self.chk.accept(node, context)
