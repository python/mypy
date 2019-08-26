"""Expression type checker. This file is conceptually part of ExpressionChecker and TypeChecker."""

import re

from typing import cast, List, Tuple, Dict, Callable, Union, Optional, Pattern
from typing_extensions import Final, TYPE_CHECKING

from mypy.types import (
    Type, AnyType, TupleType, Instance, UnionType, TypeOfAny, get_proper_type, TypeVarType
)
from mypy.nodes import (
    StrExpr, BytesExpr, UnicodeExpr, TupleExpr, DictExpr, Context, Expression, StarExpr
)

if TYPE_CHECKING:
    # break import cycle only needed for mypy
    import mypy.checker
    import mypy.checkexpr
from mypy import message_registry
from mypy.messages import MessageBuilder

FormatStringExpr = Union[StrExpr, BytesExpr, UnicodeExpr]
Checkers = Tuple[Callable[[Expression], None], Callable[[Type], None]]


def compile_format_re() -> Pattern[str]:
    key_re = r'(\(([^()]*)\))?'  # (optional) parenthesised sequence of characters.
    flags_re = r'([#0\-+ ]*)'  # (optional) sequence of flags.
    width_re = r'(\*|[1-9][0-9]*)?'  # (optional) minimum field width (* or numbers).
    precision_re = r'(?:\.(\*|[0-9]+)?)?'  # (optional) . followed by * of numbers.
    length_mod_re = r'[hlL]?'  # (optional) length modifier (unused).
    type_re = r'(.)?'  # conversion type.
    format_re = '%' + key_re + flags_re + width_re + precision_re + length_mod_re + type_re
    return re.compile(format_re)


FORMAT_RE = compile_format_re()  # type: Final


def compile_new_format_re() -> Tuple[Pattern[str], Pattern[str]]:
    # After https://docs.python.org/3/library/string.html#formatspec
    # TODO: write a more precise regexp for identifiers (currently \w+).
    # TODO: support nested formatting like '{0:{fill}{align}16}'.format(x, fill=y, align=z).

    # Field (optional) is an integer/identifier possibly followed by several .attr and [index].
    field = r'(?P<field>(?P<arg_name>\w+)(\.\w+|\[[^]?$]+\])*)?'

    # Conversion (optional) is ! followed by one of letters for forced repr(), str(), or ascii().
    conversion = r'(?P<conversion>![rsa])?'

    # Format specification (optional) follows its own mini-language:
    # Fill and align is valid for all types.
    fill_align = r'(?P<fill_align>.?[<>=^])?'
    # Number formatting options are only valid for int, float, complex, and Decimal,
    # except if only width is given (it is valid for all types).
    # This contains sign, alternate markers (# and/or 0), width, grouping (_ or ,) and precision.
    num_spec = r'(?P<num_spec>[+\- ]?#?0?(?P<width>\d+)?[_,]?(\.\d+)?)?'
    # The last element is type.
    type = r'(?P<type>[bcdeEfFgGnosxX%])?'
    format_spec = r'(?P<format_spec>:' + fill_align + num_spec + type + r')?'

    # Custom types can define their own form_spec using __format__().
    format_spec_custom = r'(?P<format_spec>:.*)?'

    format_re = r'{' + field + conversion + format_spec + r'}'
    format_re_custom = r'{' + field + conversion + format_spec_custom + r'}'
    return re.compile(format_re), re.compile(format_re_custom)


_compiled_specs_new = compile_new_format_re()
FORMAT_RE_NEW = _compiled_specs_new[0]  # type: Final
FORMAT_RE_NEW_CUSTOM = _compiled_specs_new[1]  # type: Final
FORMAT_RE_NEW_EVERYTHING = re.compile(r'{.*}')  # type: Final


class ConversionSpecifier:
    def __init__(self, key: Optional[str],
                 flags: str, width: str, precision: str, type: str) -> None:
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
        # This flag is used to track Python 2 corner case where for example
        # '%s, %d' % (u'abc', 42) returns u'abc, 42' (i.e. unicode, not a string).
        self.unicode_upcast = False

    # TODO: In Python 3, the bytes formatting has a more restricted set of options
    # compared to string formatting.
    def check_str_interpolation(self,
                                expr: FormatStringExpr,
                                replacements: Expression) -> Type:
        """Check the types of the 'replacements' in a string interpolation
        expression: str % replacements
        """
        self.exprchk.accept(expr)
        specifiers = self.parse_conversion_specifiers(expr.value)
        has_mapping_keys = self.analyze_conversion_specifiers(specifiers, expr)
        if isinstance(expr, BytesExpr) and (3, 0) <= self.chk.options.python_version < (3, 5):
            self.msg.fail('Bytes formatting is only supported in Python 3.5 and later',
                          replacements)
            return AnyType(TypeOfAny.from_error)

        self.unicode_upcast = False
        if has_mapping_keys is None:
            pass  # Error was reported
        elif has_mapping_keys:
            self.check_mapping_str_interpolation(specifiers, replacements, expr)
        else:
            self.check_simple_str_interpolation(specifiers, replacements, expr)

        if isinstance(expr, BytesExpr):
            return self.named_type('builtins.bytes')
        elif isinstance(expr, UnicodeExpr):
            return self.named_type('builtins.unicode')
        elif isinstance(expr, StrExpr):
            if self.unicode_upcast:
                return self.named_type('builtins.unicode')
            return self.named_type('builtins.str')
        else:
            assert False

    def parse_conversion_specifiers(self, format: str) -> List[ConversionSpecifier]:
        specifiers = []  # type: List[ConversionSpecifier]
        for parens_key, key, flags, width, precision, type in FORMAT_RE.findall(format):
            if parens_key == '':
                key = None
            specifiers.append(ConversionSpecifier(key, flags, width, precision, type))
        return specifiers

    def analyze_conversion_specifiers(self, specifiers: List[ConversionSpecifier],
                                      context: Context) -> Optional[bool]:
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
                                       replacements: Expression, expr: FormatStringExpr) -> None:
        checkers = self.build_replacement_checkers(specifiers, replacements, expr)
        if checkers is None:
            return

        rhs_type = get_proper_type(self.accept(replacements))
        rep_types = []  # type: List[Type]
        if isinstance(rhs_type, TupleType):
            rep_types = rhs_type.items
        elif isinstance(rhs_type, AnyType):
            return
        elif isinstance(rhs_type, Instance) and rhs_type.type.fullname() == 'builtins.tuple':
            # Assume that an arbitrary-length tuple has the right number of items.
            rep_types = [rhs_type.args[0]] * len(checkers)
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
            elif (isinstance(replacements, TupleExpr)
                  and not any(isinstance(item, StarExpr) for item in replacements.items)):
                for checks, rep_node in zip(checkers, replacements.items):
                    check_node, check_type = checks
                    check_node(rep_node)
            else:
                for checks, rep_type in zip(checkers, rep_types):
                    check_node, check_type = checks
                    check_type(rep_type)

    def check_mapping_str_interpolation(self, specifiers: List[ConversionSpecifier],
                                        replacements: Expression,
                                        expr: FormatStringExpr) -> None:
        if (isinstance(replacements, DictExpr) and
                all(isinstance(k, (StrExpr, BytesExpr, UnicodeExpr))
                    for k, v in replacements.items)):
            mapping = {}  # type: Dict[str, Type]
            for k, v in replacements.items:
                if self.chk.options.python_version >= (3, 0) and isinstance(expr, BytesExpr):
                    # Special case: for bytes formatting keys must be bytes.
                    if not isinstance(k, BytesExpr):
                        self.msg.fail('Dictionary keys in bytes formatting must be bytes,'
                                      ' not strings', expr)
                key_str = cast(FormatStringExpr, k).value
                mapping[key_str] = self.accept(v)

            for specifier in specifiers:
                if specifier.type == '%':
                    # %% is allowed in mappings, no checking is required
                    continue
                assert specifier.key is not None
                if specifier.key not in mapping:
                    self.msg.key_not_in_mapping(specifier.key, replacements)
                    return
                rep_type = mapping[specifier.key]
                expected_type = self.conversion_type(specifier.type, replacements, expr)
                if expected_type is None:
                    return
                self.chk.check_subtype(rep_type, expected_type, replacements,
                                       message_registry.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
                                       'expression has type',
                                       'placeholder with key \'%s\' has type' % specifier.key)
                if specifier.type == 's':
                    self.check_s_special_cases(expr, rep_type, expr)
        else:
            rep_type = self.accept(replacements)
            dict_type = self.build_dict_type(expr)
            self.chk.check_subtype(rep_type, dict_type, replacements,
                                   message_registry.FORMAT_REQUIRES_MAPPING,
                                   'expression has type', 'expected type for mapping is')

    def build_dict_type(self, expr: FormatStringExpr) -> Type:
        """Build expected mapping type for right operand in % formatting."""
        any_type = AnyType(TypeOfAny.special_form)
        if self.chk.options.python_version >= (3, 0):
            if isinstance(expr, BytesExpr):
                bytes_type = self.chk.named_generic_type('builtins.bytes', [])
                return self.chk.named_generic_type('typing.Mapping',
                                                   [bytes_type, any_type])
            if isinstance(expr, StrExpr):
                str_type = self.chk.named_generic_type('builtins.str', [])
                return self.chk.named_generic_type('typing.Mapping',
                                                   [str_type, any_type])
        else:
            str_type = self.chk.named_generic_type('builtins.str', [])
            unicode_type = self.chk.named_generic_type('builtins.unicode', [])
            str_map = self.chk.named_generic_type('typing.Mapping',
                                                  [str_type, any_type])
            unicode_map = self.chk.named_generic_type('typing.Mapping',
                                                      [unicode_type, any_type])
            return UnionType.make_union([str_map, unicode_map])

    def build_replacement_checkers(self, specifiers: List[ConversionSpecifier],
                                   context: Context, expr: FormatStringExpr
                                   ) -> Optional[List[Checkers]]:
        checkers = []  # type: List[Checkers]
        for specifier in specifiers:
            checker = self.replacement_checkers(specifier, context, expr)
            if checker is None:
                return None
            checkers.extend(checker)
        return checkers

    def replacement_checkers(self, specifier: ConversionSpecifier, context: Context,
                             expr: FormatStringExpr) -> Optional[List[Checkers]]:
        """Returns a list of tuples of two functions that check whether a replacement is
        of the right type for the specifier. The first functions take a node and checks
        its type in the right type context. The second function just checks a type.
        """
        checkers = []  # type: List[Checkers]

        if specifier.width == '*':
            checkers.append(self.checkers_for_star(context))
        if specifier.precision == '*':
            checkers.append(self.checkers_for_star(context))
        if specifier.type == 'c':
            c = self.checkers_for_c_type(specifier.type, context, expr)
            if c is None:
                return None
            checkers.append(c)
        elif specifier.type != '%':
            c = self.checkers_for_regular_type(specifier.type, context, expr)
            if c is None:
                return None
            checkers.append(c)
        return checkers

    def checkers_for_star(self, context: Context) -> Checkers:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with a star in a conversion specifier.
        """
        expected = self.named_type('builtins.int')

        def check_type(type: Type) -> None:
            expected = self.named_type('builtins.int')
            self.chk.check_subtype(type, expected, context, '* wants int')

        def check_expr(expr: Expression) -> None:
            type = self.accept(expr, expected)
            check_type(type)

        return check_expr, check_type

    def checkers_for_regular_type(self, type: str,
                                  context: Context,
                                  expr: FormatStringExpr) -> Optional[Checkers]:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with 'type'. Return None in case of an error.
        """
        expected_type = self.conversion_type(type, context, expr)
        if expected_type is None:
            return None

        def check_type(typ: Type) -> None:
            assert expected_type is not None
            self.chk.check_subtype(typ, expected_type, context,
                                   message_registry.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
                                   'expression has type', 'placeholder has type')
            if type == 's':
                self.check_s_special_cases(expr, typ, context)

        def check_expr(expr: Expression) -> None:
            type = self.accept(expr, expected_type)
            check_type(type)

        return check_expr, check_type

    def check_s_special_cases(self, expr: FormatStringExpr, typ: Type, context: Context) -> None:
        """Additional special cases for %s in bytes vs string context."""
        if isinstance(expr, StrExpr):
            # Couple special cases for string formatting.
            if self.chk.options.python_version >= (3, 0):
                if has_type_component(typ, 'builtins.bytes'):
                    self.msg.fail("On Python 3 '%s' % b'abc' produces \"b'abc'\";"
                                  " use %r if this is a desired behavior", context)
            if self.chk.options.python_version < (3, 0):
                if has_type_component(typ, 'builtins.unicode'):
                    self.unicode_upcast = True
        if isinstance(expr, BytesExpr):
            # A special case for bytes formatting: b'%s' actually requires bytes on Python 3.
            if self.chk.options.python_version >= (3, 0):
                if has_type_component(typ, 'builtins.str'):
                    self.msg.fail("On Python 3 b'%s' requires bytes, not string", context)

    def checkers_for_c_type(self, type: str,
                            context: Context,
                            expr: FormatStringExpr) -> Optional[Checkers]:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with 'type' that is a character type.
        """
        expected_type = self.conversion_type(type, context, expr)
        if expected_type is None:
            return None

        def check_type(type: Type) -> None:
            assert expected_type is not None
            self.chk.check_subtype(type, expected_type, context,
                                   message_registry.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
                                   'expression has type', 'placeholder has type')

        def check_expr(expr: Expression) -> None:
            """int, or str with length 1"""
            type = self.accept(expr, expected_type)
            if isinstance(expr, (StrExpr, BytesExpr)) and len(cast(StrExpr, expr).value) != 1:
                self.msg.requires_int_or_char(context)
            check_type(type)

        return check_expr, check_type

    def conversion_type(self, p: str, context: Context, expr: FormatStringExpr) -> Optional[Type]:
        """Return the type that is accepted for a string interpolation conversion specifier type.

        Note that both Python's float (e.g. %f) and integer (e.g. %d)
        specifier types accept both float and integers.
        """
        if p == 'b':
            if self.chk.options.python_version < (3, 5):
                self.msg.fail("Format character 'b' is only supported in Python 3.5 and later",
                              context)
                return None
            if not isinstance(expr, BytesExpr):
                self.msg.fail("Format character 'b' is only supported on bytes patterns", context)
                return None
            return self.named_type('builtins.bytes')
        elif p == 'a':
            if self.chk.options.python_version < (3, 0):
                self.msg.fail("Format character 'a' is only supported in Python 3", context)
                return None
            # TODO: return type object?
            return AnyType(TypeOfAny.special_form)
        elif p in ['s', 'r']:
            return AnyType(TypeOfAny.special_form)
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

    def accept(self, expr: Expression, context: Optional[Type] = None) -> Type:
        """Type check a node. Alias for TypeChecker.accept."""
        return self.chk.expr_checker.accept(expr, context)


def has_type_component(typ: Type, fullname: str) -> bool:
    """Is this a specific instance type, or a union that contains it?"""
    typ = get_proper_type(typ)
    if isinstance(typ, Instance):
        return typ.type.has_base(fullname)
    elif isinstance(typ, TypeVarType):
        return (has_type_component(typ.upper_bound, fullname) or
                any(has_type_component(v, fullname) for v in typ.values))
    elif isinstance(typ, UnionType):
        return any(has_type_component(t, fullname) for t in typ.relevant_items())
    return False
