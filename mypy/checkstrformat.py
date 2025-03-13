"""
Format expression type checker.

This file is conceptually part of ExpressionChecker and TypeChecker. Main functionality
is located in StringFormatterChecker.check_str_format_call() for '{}'.format(), and in
StringFormatterChecker.check_str_interpolation() for printf-style % interpolation.

Note that although at runtime format strings are parsed using custom parsers,
here we use a regexp-based approach. This way we 99% match runtime behaviour while keeping
implementation simple.
"""

from __future__ import annotations

import re
from re import Match, Pattern
from typing import TYPE_CHECKING, Callable, Final, Union, cast
from typing_extensions import TypeAlias as _TypeAlias

import mypy.errorcodes as codes
from mypy.errors import Errors
from mypy.nodes import (
    ARG_NAMED,
    ARG_POS,
    ARG_STAR,
    ARG_STAR2,
    BytesExpr,
    CallExpr,
    Context,
    DictExpr,
    Expression,
    ExpressionStmt,
    IndexExpr,
    IntExpr,
    MemberExpr,
    MypyFile,
    NameExpr,
    Node,
    StarExpr,
    StrExpr,
    TempNode,
    TupleExpr,
)
from mypy.types import (
    AnyType,
    Instance,
    LiteralType,
    TupleType,
    Type,
    TypeOfAny,
    TypeVarTupleType,
    TypeVarType,
    UnionType,
    UnpackType,
    find_unpack_in_list,
    get_proper_type,
    get_proper_types,
)

if TYPE_CHECKING:
    # break import cycle only needed for mypy
    import mypy.checker
    import mypy.checkexpr

from mypy import message_registry
from mypy.maptype import map_instance_to_supertype
from mypy.messages import MessageBuilder
from mypy.parse import parse
from mypy.subtypes import is_subtype
from mypy.typeops import custom_special_method

FormatStringExpr: _TypeAlias = Union[StrExpr, BytesExpr]
Checkers: _TypeAlias = tuple[Callable[[Expression], None], Callable[[Type], bool]]
MatchMap: _TypeAlias = dict[tuple[int, int], Match[str]]  # span -> match


def compile_format_re() -> Pattern[str]:
    """Construct regexp to match format conversion specifiers in % interpolation.

    See https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting
    The regexp is intentionally a bit wider to report better errors.
    """
    key_re = r"(\((?P<key>[^)]*)\))?"  # (optional) parenthesised sequence of characters.
    flags_re = r"(?P<flags>[#0\-+ ]*)"  # (optional) sequence of flags.
    width_re = r"(?P<width>[1-9][0-9]*|\*)?"  # (optional) minimum field width (* or numbers).
    precision_re = r"(?:\.(?P<precision>\*|[0-9]+)?)?"  # (optional) . followed by * of numbers.
    length_mod_re = r"[hlL]?"  # (optional) length modifier (unused).
    type_re = r"(?P<type>.)?"  # conversion type.
    format_re = "%" + key_re + flags_re + width_re + precision_re + length_mod_re + type_re
    return re.compile(format_re)


def compile_new_format_re(custom_spec: bool) -> Pattern[str]:
    """Construct regexps to match format conversion specifiers in str.format() calls.

    See After https://docs.python.org/3/library/string.html#formatspec for
    specifications. The regexps are intentionally wider, to report better errors,
    instead of just not matching.
    """

    # Field (optional) is an integer/identifier possibly followed by several .attr and [index].
    field = r"(?P<field>(?P<key>[^.[!:]*)([^:!]+)?)"

    # Conversion (optional) is ! followed by one of letters for forced repr(), str(), or ascii().
    conversion = r"(?P<conversion>![^:])?"

    # Format specification (optional) follows its own mini-language:
    if not custom_spec:
        # Fill and align is valid for all builtin types.
        fill_align = r"(?P<fill_align>.?[<>=^])?"
        # Number formatting options are only valid for int, float, complex, and Decimal,
        # except if only width is given (it is valid for all types).
        # This contains sign, flags (sign, # and/or 0), width, grouping (_ or ,) and precision.
        num_spec = r"(?P<flags>[+\- ]?#?0?)(?P<width>\d+)?[_,]?(?P<precision>\.\d+)?"
        # The last element is type.
        conv_type = r"(?P<type>.)?"  # only some are supported, but we want to give a better error
        format_spec = r"(?P<format_spec>:" + fill_align + num_spec + conv_type + r")?"
    else:
        # Custom types can define their own form_spec using __format__().
        format_spec = r"(?P<format_spec>:.*)?"

    return re.compile(field + conversion + format_spec)


FORMAT_RE: Final = compile_format_re()
FORMAT_RE_NEW: Final = compile_new_format_re(False)
FORMAT_RE_NEW_CUSTOM: Final = compile_new_format_re(True)
DUMMY_FIELD_NAME: Final = "__dummy_name__"

# Types that require either int or float.
NUMERIC_TYPES_OLD: Final = {"d", "i", "o", "u", "x", "X", "e", "E", "f", "F", "g", "G"}
NUMERIC_TYPES_NEW: Final = {"b", "d", "o", "e", "E", "f", "F", "g", "G", "n", "x", "X", "%"}

# These types accept _only_ int.
REQUIRE_INT_OLD: Final = {"o", "x", "X"}
REQUIRE_INT_NEW: Final = {"b", "d", "o", "x", "X"}

# These types fall back to SupportsFloat with % (other fall back to SupportsInt)
FLOAT_TYPES: Final = {"e", "E", "f", "F", "g", "G"}


class ConversionSpecifier:
    def __init__(
        self, match: Match[str], start_pos: int = -1, non_standard_format_spec: bool = False
    ) -> None:
        self.whole_seq = match.group()
        self.start_pos = start_pos

        m_dict = match.groupdict()
        self.key = m_dict.get("key")

        # Replace unmatched optional groups with empty matches (for convenience).
        self.conv_type = m_dict.get("type", "")
        self.flags = m_dict.get("flags", "")
        self.width = m_dict.get("width", "")
        self.precision = m_dict.get("precision", "")

        # Used only for str.format() calls (it may be custom for types with __format__()).
        self.format_spec = m_dict.get("format_spec")
        self.non_standard_format_spec = non_standard_format_spec
        # Used only for str.format() calls.
        self.conversion = m_dict.get("conversion")
        # Full formatted expression (i.e. key plus following attributes and/or indexes).
        # Used only for str.format() calls.
        self.field = m_dict.get("field")

    def has_key(self) -> bool:
        return self.key is not None

    def has_star(self) -> bool:
        return self.width == "*" or self.precision == "*"


def parse_conversion_specifiers(format_str: str) -> list[ConversionSpecifier]:
    """Parse c-printf-style format string into list of conversion specifiers."""
    specifiers: list[ConversionSpecifier] = []
    for m in re.finditer(FORMAT_RE, format_str):
        specifiers.append(ConversionSpecifier(m, start_pos=m.start()))
    return specifiers


def parse_format_value(
    format_value: str, ctx: Context, msg: MessageBuilder, nested: bool = False
) -> list[ConversionSpecifier] | None:
    """Parse format string into list of conversion specifiers.

    The specifiers may be nested (two levels maximum), in this case they are ordered as
    '{0:{1}}, {2:{3}{4}}'. Return None in case of an error.
    """
    top_targets = find_non_escaped_targets(format_value, ctx, msg)
    if top_targets is None:
        return None

    result: list[ConversionSpecifier] = []
    for target, start_pos in top_targets:
        match = FORMAT_RE_NEW.fullmatch(target)
        if match:
            conv_spec = ConversionSpecifier(match, start_pos=start_pos)
        else:
            custom_match = FORMAT_RE_NEW_CUSTOM.fullmatch(target)
            if custom_match:
                conv_spec = ConversionSpecifier(
                    custom_match, start_pos=start_pos, non_standard_format_spec=True
                )
            else:
                msg.fail(
                    "Invalid conversion specifier in format string",
                    ctx,
                    code=codes.STRING_FORMATTING,
                )
                return None

        if conv_spec.key and ("{" in conv_spec.key or "}" in conv_spec.key):
            msg.fail("Conversion value must not contain { or }", ctx, code=codes.STRING_FORMATTING)
            return None
        result.append(conv_spec)

        # Parse nested conversions that are allowed in format specifier.
        if (
            conv_spec.format_spec
            and conv_spec.non_standard_format_spec
            and ("{" in conv_spec.format_spec or "}" in conv_spec.format_spec)
        ):
            if nested:
                msg.fail(
                    "Formatting nesting must be at most two levels deep",
                    ctx,
                    code=codes.STRING_FORMATTING,
                )
                return None
            sub_conv_specs = parse_format_value(conv_spec.format_spec, ctx, msg, nested=True)
            if sub_conv_specs is None:
                return None
            result.extend(sub_conv_specs)
    return result


def find_non_escaped_targets(
    format_value: str, ctx: Context, msg: MessageBuilder
) -> list[tuple[str, int]] | None:
    """Return list of raw (un-parsed) format specifiers in format string.

    Format specifiers don't include enclosing braces. We don't use regexp for
    this because they don't work well with nested/repeated patterns
    (both greedy and non-greedy), and these are heavily used internally for
    representation of f-strings.

    Return None in case of an error.
    """
    result = []
    next_spec = ""
    pos = 0
    nesting = 0
    while pos < len(format_value):
        c = format_value[pos]
        if not nesting:
            # Skip any paired '{{' and '}}', enter nesting on '{', report error on '}'.
            if c == "{":
                if pos < len(format_value) - 1 and format_value[pos + 1] == "{":
                    pos += 1
                else:
                    nesting = 1
            if c == "}":
                if pos < len(format_value) - 1 and format_value[pos + 1] == "}":
                    pos += 1
                else:
                    msg.fail(
                        "Invalid conversion specifier in format string: unexpected }",
                        ctx,
                        code=codes.STRING_FORMATTING,
                    )
                    return None
        else:
            # Adjust nesting level, then either continue adding chars or move on.
            if c == "{":
                nesting += 1
            if c == "}":
                nesting -= 1
            if nesting:
                next_spec += c
            else:
                result.append((next_spec, pos - len(next_spec)))
                next_spec = ""
        pos += 1
    if nesting:
        msg.fail(
            "Invalid conversion specifier in format string: unmatched {",
            ctx,
            code=codes.STRING_FORMATTING,
        )
        return None
    return result


class StringFormatterChecker:
    """String interpolation/formatter type checker.

    This class works closely together with checker.ExpressionChecker.
    """

    # Some services are provided by a TypeChecker instance.
    chk: mypy.checker.TypeChecker
    # This is shared with TypeChecker, but stored also here for convenience.
    msg: MessageBuilder
    # Some services are provided by a ExpressionChecker instance.
    exprchk: mypy.checkexpr.ExpressionChecker

    def __init__(
        self,
        exprchk: mypy.checkexpr.ExpressionChecker,
        chk: mypy.checker.TypeChecker,
        msg: MessageBuilder,
    ) -> None:
        """Construct an expression type checker."""
        self.chk = chk
        self.exprchk = exprchk
        self.msg = msg

    def check_str_format_call(self, call: CallExpr, format_value: str) -> None:
        """Perform more precise checks for str.format() calls when possible.

        Currently the checks are performed for:
          * Actual string literals
          * Literal types with string values
          * Final names with string values

        The checks that we currently perform:
          * Check generic validity (e.g. unmatched { or }, and {} in invalid positions)
          * Check consistency of specifiers' auto-numbering
          * Verify that replacements can be found for all conversion specifiers,
            and all arguments were used
          * Non-standard format specs are only allowed for types with custom __format__
          * Type check replacements with accessors applied (if any).
          * Verify that specifier type is known and matches replacement type
          * Perform special checks for some specifier types:
            - 'c' requires a single character string
            - 's' must not accept bytes
            - non-empty flags are only allowed for numeric types
        """
        conv_specs = parse_format_value(format_value, call, self.msg)
        if conv_specs is None:
            return
        if not self.auto_generate_keys(conv_specs, call):
            return
        self.check_specs_in_format_call(call, conv_specs, format_value)

    def check_specs_in_format_call(
        self, call: CallExpr, specs: list[ConversionSpecifier], format_value: str
    ) -> None:
        """Perform pairwise checks for conversion specifiers vs their replacements.

        The core logic for format checking is implemented in this method.
        """
        assert all(s.key for s in specs), "Keys must be auto-generated first!"
        replacements = self.find_replacements_in_call(call, [cast(str, s.key) for s in specs])
        assert len(replacements) == len(specs)
        for spec, repl in zip(specs, replacements):
            repl = self.apply_field_accessors(spec, repl, ctx=call)
            actual_type = repl.type if isinstance(repl, TempNode) else self.chk.lookup_type(repl)
            assert actual_type is not None

            # Special case custom formatting.
            if (
                spec.format_spec
                and spec.non_standard_format_spec
                and
                # Exclude "dynamic" specifiers (i.e. containing nested formatting).
                not ("{" in spec.format_spec or "}" in spec.format_spec)
            ):
                if (
                    not custom_special_method(actual_type, "__format__", check_all=True)
                    or spec.conversion
                ):
                    # TODO: add support for some custom specs like datetime?
                    self.msg.fail(
                        f'Unrecognized format specification "{spec.format_spec[1:]}"',
                        call,
                        code=codes.STRING_FORMATTING,
                    )
                    continue
            # Adjust expected and actual types.
            if not spec.conv_type:
                expected_type: Type | None = AnyType(TypeOfAny.special_form)
            else:
                assert isinstance(call.callee, MemberExpr)
                if isinstance(call.callee.expr, StrExpr):
                    format_str = call.callee.expr
                else:
                    format_str = StrExpr(format_value)
                expected_type = self.conversion_type(
                    spec.conv_type, call, format_str, format_call=True
                )
            if spec.conversion is not None:
                # If the explicit conversion is given, then explicit conversion is called _first_.
                if spec.conversion[1] not in "rsa":
                    self.msg.fail(
                        (
                            f'Invalid conversion type "{spec.conversion[1]}", '
                            f'must be one of "r", "s" or "a"'
                        ),
                        call,
                        code=codes.STRING_FORMATTING,
                    )
                actual_type = self.named_type("builtins.str")

            # Perform the checks for given types.
            if expected_type is None:
                continue

            a_type = get_proper_type(actual_type)
            actual_items = (
                get_proper_types(a_type.items) if isinstance(a_type, UnionType) else [a_type]
            )
            for a_type in actual_items:
                if custom_special_method(a_type, "__format__"):
                    continue
                self.check_placeholder_type(a_type, expected_type, call)
                self.perform_special_format_checks(spec, call, repl, a_type, expected_type)

    def perform_special_format_checks(
        self,
        spec: ConversionSpecifier,
        call: CallExpr,
        repl: Expression,
        actual_type: Type,
        expected_type: Type,
    ) -> None:
        # TODO: try refactoring to combine this logic with % formatting.
        if spec.conv_type == "c":
            if isinstance(repl, (StrExpr, BytesExpr)) and len(repl.value) != 1:
                self.msg.requires_int_or_char(call, format_call=True)
            c_typ = get_proper_type(self.chk.lookup_type(repl))
            if isinstance(c_typ, Instance) and c_typ.last_known_value:
                c_typ = c_typ.last_known_value
            if isinstance(c_typ, LiteralType) and isinstance(c_typ.value, str):
                if len(c_typ.value) != 1:
                    self.msg.requires_int_or_char(call, format_call=True)
        if (not spec.conv_type or spec.conv_type == "s") and not spec.conversion:
            if has_type_component(actual_type, "builtins.bytes") and not custom_special_method(
                actual_type, "__str__"
            ):
                self.msg.fail(
                    'If x = b\'abc\' then f"{x}" or "{}".format(x) produces "b\'abc\'", '
                    'not "abc". If this is desired behavior, use f"{x!r}" or "{!r}".format(x). '
                    "Otherwise, decode the bytes",
                    call,
                    code=codes.STR_BYTES_PY3,
                )
        if spec.flags:
            numeric_types = UnionType(
                [self.named_type("builtins.int"), self.named_type("builtins.float")]
            )
            if (
                spec.conv_type
                and spec.conv_type not in NUMERIC_TYPES_NEW
                or not spec.conv_type
                and not is_subtype(actual_type, numeric_types)
                and not custom_special_method(actual_type, "__format__")
            ):
                self.msg.fail(
                    "Numeric flags are only allowed for numeric types",
                    call,
                    code=codes.STRING_FORMATTING,
                )

    def find_replacements_in_call(self, call: CallExpr, keys: list[str]) -> list[Expression]:
        """Find replacement expression for every specifier in str.format() call.

        In case of an error use TempNode(AnyType).
        """
        result: list[Expression] = []
        used: set[Expression] = set()
        for key in keys:
            if key.isdecimal():
                expr = self.get_expr_by_position(int(key), call)
                if not expr:
                    self.msg.fail(
                        f"Cannot find replacement for positional format specifier {key}",
                        call,
                        code=codes.STRING_FORMATTING,
                    )
                    expr = TempNode(AnyType(TypeOfAny.from_error))
            else:
                expr = self.get_expr_by_name(key, call)
                if not expr:
                    self.msg.fail(
                        f'Cannot find replacement for named format specifier "{key}"',
                        call,
                        code=codes.STRING_FORMATTING,
                    )
                    expr = TempNode(AnyType(TypeOfAny.from_error))
            result.append(expr)
            if not isinstance(expr, TempNode):
                used.add(expr)
        # Strictly speaking not using all replacements is not a type error, but most likely
        # a typo in user code, so we show an error like we do for % formatting.
        total_explicit = len([kind for kind in call.arg_kinds if kind in (ARG_POS, ARG_NAMED)])
        if len(used) < total_explicit:
            self.msg.too_many_string_formatting_arguments(call)
        return result

    def get_expr_by_position(self, pos: int, call: CallExpr) -> Expression | None:
        """Get positional replacement expression from '{0}, {1}'.format(x, y, ...) call.

        If the type is from *args, return TempNode(<item type>). Return None in case of
        an error.
        """
        pos_args = [arg for arg, kind in zip(call.args, call.arg_kinds) if kind == ARG_POS]
        if pos < len(pos_args):
            return pos_args[pos]
        star_args = [arg for arg, kind in zip(call.args, call.arg_kinds) if kind == ARG_STAR]
        if not star_args:
            return None

        # Fall back to *args when present in call.
        star_arg = star_args[0]
        varargs_type = get_proper_type(self.chk.lookup_type(star_arg))
        if not isinstance(varargs_type, Instance) or not varargs_type.type.has_base(
            "typing.Sequence"
        ):
            # Error should be already reported.
            return TempNode(AnyType(TypeOfAny.special_form))
        iter_info = self.chk.named_generic_type(
            "typing.Sequence", [AnyType(TypeOfAny.special_form)]
        ).type
        return TempNode(map_instance_to_supertype(varargs_type, iter_info).args[0])

    def get_expr_by_name(self, key: str, call: CallExpr) -> Expression | None:
        """Get named replacement expression from '{name}'.format(name=...) call.

        If the type is from **kwargs, return TempNode(<item type>). Return None in case of
        an error.
        """
        named_args = [
            arg
            for arg, kind, name in zip(call.args, call.arg_kinds, call.arg_names)
            if kind == ARG_NAMED and name == key
        ]
        if named_args:
            return named_args[0]
        star_args_2 = [arg for arg, kind in zip(call.args, call.arg_kinds) if kind == ARG_STAR2]
        if not star_args_2:
            return None
        star_arg_2 = star_args_2[0]
        kwargs_type = get_proper_type(self.chk.lookup_type(star_arg_2))
        if not isinstance(kwargs_type, Instance) or not kwargs_type.type.has_base(
            "typing.Mapping"
        ):
            # Error should be already reported.
            return TempNode(AnyType(TypeOfAny.special_form))
        any_type = AnyType(TypeOfAny.special_form)
        mapping_info = self.chk.named_generic_type("typing.Mapping", [any_type, any_type]).type
        return TempNode(map_instance_to_supertype(kwargs_type, mapping_info).args[1])

    def auto_generate_keys(self, all_specs: list[ConversionSpecifier], ctx: Context) -> bool:
        """Translate '{} {name} {}' to '{0} {name} {1}'.

        Return True if generation was successful, otherwise report an error and return false.
        """
        some_defined = any(s.key and s.key.isdecimal() for s in all_specs)
        all_defined = all(bool(s.key) for s in all_specs)
        if some_defined and not all_defined:
            self.msg.fail(
                "Cannot combine automatic field numbering and manual field specification",
                ctx,
                code=codes.STRING_FORMATTING,
            )
            return False
        if all_defined:
            return True
        next_index = 0
        for spec in all_specs:
            if not spec.key:
                str_index = str(next_index)
                spec.key = str_index
                # Update also the full field (i.e. turn {.x} into {0.x}).
                if not spec.field:
                    spec.field = str_index
                else:
                    spec.field = str_index + spec.field
                next_index += 1
        return True

    def apply_field_accessors(
        self, spec: ConversionSpecifier, repl: Expression, ctx: Context
    ) -> Expression:
        """Transform and validate expr in '{.attr[item]}'.format(expr) into expr.attr['item'].

        If validation fails, return TempNode(AnyType).
        """
        assert spec.key, "Keys must be auto-generated first!"
        if spec.field == spec.key:
            return repl
        assert spec.field

        temp_errors = Errors(self.chk.options)
        dummy = DUMMY_FIELD_NAME + spec.field[len(spec.key) :]
        temp_ast: Node = parse(
            dummy, fnam="<format>", module=None, options=self.chk.options, errors=temp_errors
        )
        if temp_errors.is_errors():
            self.msg.fail(
                f'Syntax error in format specifier "{spec.field}"',
                ctx,
                code=codes.STRING_FORMATTING,
            )
            return TempNode(AnyType(TypeOfAny.from_error))

        # These asserts are guaranteed by the original regexp.
        assert isinstance(temp_ast, MypyFile)
        temp_ast = temp_ast.defs[0]
        assert isinstance(temp_ast, ExpressionStmt)
        temp_ast = temp_ast.expr
        if not self.validate_and_transform_accessors(temp_ast, repl, spec, ctx=ctx):
            return TempNode(AnyType(TypeOfAny.from_error))

        # Check if there are any other errors (like missing members).
        # TODO: fix column to point to actual start of the format specifier _within_ string.
        temp_ast.line = ctx.line
        temp_ast.column = ctx.column
        self.exprchk.accept(temp_ast)
        return temp_ast

    def validate_and_transform_accessors(
        self,
        temp_ast: Expression,
        original_repl: Expression,
        spec: ConversionSpecifier,
        ctx: Context,
    ) -> bool:
        """Validate and transform (in-place) format field accessors.

        On error, report it and return False. The transformations include replacing the dummy
        variable with actual replacement expression and translating any name expressions in an
        index into strings, so that this will work:

            class User(TypedDict):
                name: str
                id: int
            u: User
            '{[id]:d} -> {[name]}'.format(u)
        """
        if not isinstance(temp_ast, (MemberExpr, IndexExpr)):
            self.msg.fail(
                "Only index and member expressions are allowed in"
                ' format field accessors; got "{}"'.format(spec.field),
                ctx,
                code=codes.STRING_FORMATTING,
            )
            return False
        if isinstance(temp_ast, MemberExpr):
            node = temp_ast.expr
        else:
            node = temp_ast.base
            if not isinstance(temp_ast.index, (NameExpr, IntExpr)):
                assert spec.key, "Call this method only after auto-generating keys!"
                assert spec.field
                self.msg.fail(
                    'Invalid index expression in format field accessor "{}"'.format(
                        spec.field[len(spec.key) :]
                    ),
                    ctx,
                    code=codes.STRING_FORMATTING,
                )
                return False
            if isinstance(temp_ast.index, NameExpr):
                temp_ast.index = StrExpr(temp_ast.index.name)
        if isinstance(node, NameExpr) and node.name == DUMMY_FIELD_NAME:
            # Replace it with the actual replacement expression.
            assert isinstance(temp_ast, (IndexExpr, MemberExpr))  # XXX: this is redundant
            if isinstance(temp_ast, IndexExpr):
                temp_ast.base = original_repl
            else:
                temp_ast.expr = original_repl
            return True
        node.line = ctx.line
        node.column = ctx.column
        return self.validate_and_transform_accessors(
            node, original_repl=original_repl, spec=spec, ctx=ctx
        )

    # TODO: In Python 3, the bytes formatting has a more restricted set of options
    #       compared to string formatting.
    def check_str_interpolation(self, expr: FormatStringExpr, replacements: Expression) -> Type:
        """Check the types of the 'replacements' in a string interpolation
        expression: str % replacements.
        """
        self.exprchk.accept(expr)
        specifiers = parse_conversion_specifiers(expr.value)
        has_mapping_keys = self.analyze_conversion_specifiers(specifiers, expr)
        if has_mapping_keys is None:
            pass  # Error was reported
        elif has_mapping_keys:
            self.check_mapping_str_interpolation(specifiers, replacements, expr)
        else:
            self.check_simple_str_interpolation(specifiers, replacements, expr)

        if isinstance(expr, BytesExpr):
            return self.named_type("builtins.bytes")
        elif isinstance(expr, StrExpr):
            return self.named_type("builtins.str")
        else:
            assert False

    def analyze_conversion_specifiers(
        self, specifiers: list[ConversionSpecifier], context: Context
    ) -> bool | None:
        has_star = any(specifier.has_star() for specifier in specifiers)
        has_key = any(specifier.has_key() for specifier in specifiers)
        all_have_keys = all(
            specifier.has_key() or specifier.conv_type == "%" for specifier in specifiers
        )

        if has_key and has_star:
            self.msg.string_interpolation_with_star_and_key(context)
            return None
        if has_key and not all_have_keys:
            self.msg.string_interpolation_mixing_key_and_non_keys(context)
            return None
        return has_key

    def check_simple_str_interpolation(
        self,
        specifiers: list[ConversionSpecifier],
        replacements: Expression,
        expr: FormatStringExpr,
    ) -> None:
        """Check % string interpolation with positional specifiers '%s, %d' % ('yes, 42')."""
        checkers = self.build_replacement_checkers(specifiers, replacements, expr)
        if checkers is None:
            return

        rhs_type = get_proper_type(self.accept(replacements))
        rep_types: list[Type] = []
        if isinstance(rhs_type, TupleType):
            rep_types = rhs_type.items
            unpack_index = find_unpack_in_list(rep_types)
            if unpack_index is not None:
                # TODO: we should probably warn about potentially short tuple.
                # However, without special-casing for tuple(f(i) for in other_tuple)
                # this causes false positive on mypy self-check in report.py.
                extras = max(0, len(checkers) - len(rep_types) + 1)
                unpacked = rep_types[unpack_index]
                assert isinstance(unpacked, UnpackType)
                unpacked = get_proper_type(unpacked.type)
                if isinstance(unpacked, TypeVarTupleType):
                    unpacked = get_proper_type(unpacked.upper_bound)
                assert (
                    isinstance(unpacked, Instance) and unpacked.type.fullname == "builtins.tuple"
                )
                unpack_items = [unpacked.args[0]] * extras
                rep_types = rep_types[:unpack_index] + unpack_items + rep_types[unpack_index + 1 :]
        elif isinstance(rhs_type, AnyType):
            return
        elif isinstance(rhs_type, Instance) and rhs_type.type.fullname == "builtins.tuple":
            # Assume that an arbitrary-length tuple has the right number of items.
            rep_types = [rhs_type.args[0]] * len(checkers)
        elif isinstance(rhs_type, UnionType):
            for typ in rhs_type.relevant_items():
                temp_node = TempNode(typ)
                temp_node.line = replacements.line
                self.check_simple_str_interpolation(specifiers, temp_node, expr)
            return
        else:
            rep_types = [rhs_type]

        if len(checkers) > len(rep_types):
            # Only check the fix-length Tuple type. Other Iterable types would skip.
            if is_subtype(rhs_type, self.chk.named_type("typing.Iterable")) and not isinstance(
                rhs_type, TupleType
            ):
                return
            else:
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
            elif isinstance(replacements, TupleExpr) and not any(
                isinstance(item, StarExpr) for item in replacements.items
            ):
                for checks, rep_node in zip(checkers, replacements.items):
                    check_node, check_type = checks
                    check_node(rep_node)
            else:
                for checks, rep_type in zip(checkers, rep_types):
                    check_node, check_type = checks
                    check_type(rep_type)

    def check_mapping_str_interpolation(
        self,
        specifiers: list[ConversionSpecifier],
        replacements: Expression,
        expr: FormatStringExpr,
    ) -> None:
        """Check % string interpolation with names specifiers '%(name)s' % {'name': 'John'}."""
        if isinstance(replacements, DictExpr) and all(
            isinstance(k, (StrExpr, BytesExpr)) for k, v in replacements.items
        ):
            mapping: dict[str, Type] = {}
            for k, v in replacements.items:
                if isinstance(expr, BytesExpr):
                    # Special case: for bytes formatting keys must be bytes.
                    if not isinstance(k, BytesExpr):
                        self.msg.fail(
                            "Dictionary keys in bytes formatting must be bytes, not strings",
                            expr,
                            code=codes.STRING_FORMATTING,
                        )
                key_str = cast(FormatStringExpr, k).value
                mapping[key_str] = self.accept(v)

            for specifier in specifiers:
                if specifier.conv_type == "%":
                    # %% is allowed in mappings, no checking is required
                    continue
                assert specifier.key is not None
                if specifier.key not in mapping:
                    self.msg.key_not_in_mapping(specifier.key, replacements)
                    return
                rep_type = mapping[specifier.key]
                assert specifier.conv_type is not None
                expected_type = self.conversion_type(specifier.conv_type, replacements, expr)
                if expected_type is None:
                    return
                self.chk.check_subtype(
                    rep_type,
                    expected_type,
                    replacements,
                    message_registry.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
                    "expression has type",
                    f"placeholder with key '{specifier.key}' has type",
                    code=codes.STRING_FORMATTING,
                )
                if specifier.conv_type == "s":
                    self.check_s_special_cases(expr, rep_type, expr)
        else:
            rep_type = self.accept(replacements)
            dict_type = self.build_dict_type(expr)
            self.chk.check_subtype(
                rep_type,
                dict_type,
                replacements,
                message_registry.FORMAT_REQUIRES_MAPPING,
                "expression has type",
                "expected type for mapping is",
                code=codes.STRING_FORMATTING,
            )

    def build_dict_type(self, expr: FormatStringExpr) -> Type:
        """Build expected mapping type for right operand in % formatting."""
        any_type = AnyType(TypeOfAny.special_form)
        if isinstance(expr, BytesExpr):
            bytes_type = self.chk.named_generic_type("builtins.bytes", [])
            return self.chk.named_generic_type(
                "_typeshed.SupportsKeysAndGetItem", [bytes_type, any_type]
            )
        elif isinstance(expr, StrExpr):
            str_type = self.chk.named_generic_type("builtins.str", [])
            return self.chk.named_generic_type(
                "_typeshed.SupportsKeysAndGetItem", [str_type, any_type]
            )
        else:
            assert False, "Unreachable"

    def build_replacement_checkers(
        self, specifiers: list[ConversionSpecifier], context: Context, expr: FormatStringExpr
    ) -> list[Checkers] | None:
        checkers: list[Checkers] = []
        for specifier in specifiers:
            checker = self.replacement_checkers(specifier, context, expr)
            if checker is None:
                return None
            checkers.extend(checker)
        return checkers

    def replacement_checkers(
        self, specifier: ConversionSpecifier, context: Context, expr: FormatStringExpr
    ) -> list[Checkers] | None:
        """Returns a list of tuples of two functions that check whether a replacement is
        of the right type for the specifier. The first function takes a node and checks
        its type in the right type context. The second function just checks a type.
        """
        checkers: list[Checkers] = []

        if specifier.width == "*":
            checkers.append(self.checkers_for_star(context))
        if specifier.precision == "*":
            checkers.append(self.checkers_for_star(context))

        if specifier.conv_type == "c":
            c = self.checkers_for_c_type(specifier.conv_type, context, expr)
            if c is None:
                return None
            checkers.append(c)
        elif specifier.conv_type is not None and specifier.conv_type != "%":
            c = self.checkers_for_regular_type(specifier.conv_type, context, expr)
            if c is None:
                return None
            checkers.append(c)
        return checkers

    def checkers_for_star(self, context: Context) -> Checkers:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with a star in a conversion specifier.
        """
        expected = self.named_type("builtins.int")

        def check_type(type: Type) -> bool:
            expected = self.named_type("builtins.int")
            return self.chk.check_subtype(
                type, expected, context, "* wants int", code=codes.STRING_FORMATTING
            )

        def check_expr(expr: Expression) -> None:
            type = self.accept(expr, expected)
            check_type(type)

        return check_expr, check_type

    def check_placeholder_type(self, typ: Type, expected_type: Type, context: Context) -> bool:
        return self.chk.check_subtype(
            typ,
            expected_type,
            context,
            message_registry.INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION,
            "expression has type",
            "placeholder has type",
            code=codes.STRING_FORMATTING,
        )

    def checkers_for_regular_type(
        self, conv_type: str, context: Context, expr: FormatStringExpr
    ) -> Checkers | None:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with 'type'. Return None in case of an error.
        """
        expected_type = self.conversion_type(conv_type, context, expr)
        if expected_type is None:
            return None

        def check_type(typ: Type) -> bool:
            assert expected_type is not None
            ret = self.check_placeholder_type(typ, expected_type, context)
            if ret and conv_type == "s":
                ret = self.check_s_special_cases(expr, typ, context)
            return ret

        def check_expr(expr: Expression) -> None:
            type = self.accept(expr, expected_type)
            check_type(type)

        return check_expr, check_type

    def check_s_special_cases(self, expr: FormatStringExpr, typ: Type, context: Context) -> bool:
        """Additional special cases for %s in bytes vs string context."""
        if isinstance(expr, StrExpr):
            # Couple special cases for string formatting.
            if has_type_component(typ, "builtins.bytes"):
                self.msg.fail(
                    'If x = b\'abc\' then "%s" % x produces "b\'abc\'", not "abc". '
                    'If this is desired behavior use "%r" % x. Otherwise, decode the bytes',
                    context,
                    code=codes.STR_BYTES_PY3,
                )
                return False
        if isinstance(expr, BytesExpr):
            # A special case for bytes formatting: b'%s' actually requires bytes on Python 3.
            if has_type_component(typ, "builtins.str"):
                self.msg.fail(
                    "On Python 3 b'%s' requires bytes, not string",
                    context,
                    code=codes.STRING_FORMATTING,
                )
                return False
        return True

    def checkers_for_c_type(
        self, type: str, context: Context, format_expr: FormatStringExpr
    ) -> Checkers | None:
        """Returns a tuple of check functions that check whether, respectively,
        a node or a type is compatible with 'type' that is a character type.
        """
        expected_type = self.conversion_type(type, context, format_expr)
        if expected_type is None:
            return None

        def check_type(type: Type) -> bool:
            assert expected_type is not None
            if isinstance(format_expr, BytesExpr):
                err_msg = '"%c" requires an integer in range(256) or a single byte'
            else:
                err_msg = '"%c" requires int or char'
            return self.chk.check_subtype(
                type,
                expected_type,
                context,
                err_msg,
                "expression has type",
                code=codes.STRING_FORMATTING,
            )

        def check_expr(expr: Expression) -> None:
            """int, or str with length 1"""
            type = self.accept(expr, expected_type)
            # We need further check with expr to make sure that
            # it has exact one char or one single byte.
            if check_type(type):
                # Python 3 doesn't support b'%c' % str
                if (
                    isinstance(format_expr, BytesExpr)
                    and isinstance(expr, BytesExpr)
                    and len(expr.value) != 1
                ):
                    self.msg.requires_int_or_single_byte(context)
                elif isinstance(expr, (StrExpr, BytesExpr)) and len(expr.value) != 1:
                    self.msg.requires_int_or_char(context)

        return check_expr, check_type

    def conversion_type(
        self, p: str, context: Context, expr: FormatStringExpr, format_call: bool = False
    ) -> Type | None:
        """Return the type that is accepted for a string interpolation conversion specifier type.

        Note that both Python's float (e.g. %f) and integer (e.g. %d)
        specifier types accept both float and integers.

        The 'format_call' argument indicates whether this type came from % interpolation or from
        a str.format() call, the meaning of few formatting types are different.
        """
        NUMERIC_TYPES = NUMERIC_TYPES_NEW if format_call else NUMERIC_TYPES_OLD
        INT_TYPES = REQUIRE_INT_NEW if format_call else REQUIRE_INT_OLD
        if p == "b" and not format_call:
            if not isinstance(expr, BytesExpr):
                self.msg.fail(
                    'Format character "b" is only supported on bytes patterns',
                    context,
                    code=codes.STRING_FORMATTING,
                )
                return None
            return self.named_type("builtins.bytes")
        elif p == "a":
            # TODO: return type object?
            return AnyType(TypeOfAny.special_form)
        elif p in ["s", "r"]:
            return AnyType(TypeOfAny.special_form)
        elif p in NUMERIC_TYPES:
            if p in INT_TYPES:
                numeric_types = [self.named_type("builtins.int")]
            else:
                numeric_types = [
                    self.named_type("builtins.int"),
                    self.named_type("builtins.float"),
                ]
                if not format_call:
                    if p in FLOAT_TYPES:
                        numeric_types.append(self.named_type("typing.SupportsFloat"))
                    else:
                        numeric_types.append(self.named_type("typing.SupportsInt"))
            return UnionType.make_union(numeric_types)
        elif p in ["c"]:
            if isinstance(expr, BytesExpr):
                return UnionType(
                    [self.named_type("builtins.int"), self.named_type("builtins.bytes")]
                )
            else:
                return UnionType(
                    [self.named_type("builtins.int"), self.named_type("builtins.str")]
                )
        elif p.startswith(("<", ">", "=", "^")):
            return UnionType(
                [
                    self.named_type("builtins.int"), 
                    self.named_type("builtins.float"), 
                    self.named_type("builtins.str")
                ]
            )
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

    def accept(self, expr: Expression, context: Type | None = None) -> Type:
        """Type check a node. Alias for TypeChecker.accept."""
        return self.chk.expr_checker.accept(expr, context)


def has_type_component(typ: Type, fullname: str) -> bool:
    """Is this a specific instance type, or a union that contains it?

    We use this ad-hoc function instead of a proper visitor or subtype check
    because some str vs bytes errors are strictly speaking not runtime errors,
    but rather highly counter-intuitive behavior. This is similar to what is used for
    --strict-equality.
    """
    typ = get_proper_type(typ)
    if isinstance(typ, Instance):
        return typ.type.has_base(fullname)
    elif isinstance(typ, TypeVarType):
        return has_type_component(typ.upper_bound, fullname) or any(
            has_type_component(v, fullname) for v in typ.values
        )
    elif isinstance(typ, UnionType):
        return any(has_type_component(t, fullname) for t in typ.relevant_items())
    return False
