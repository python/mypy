"""Facilities and constants for generating error messages during type checking.

Don't add any non-trivial message construction logic to the type
checker, as it can compromise clarity and make messages less
consistent. Add such logic to this module instead. Literal messages used
in multiple places should also be defined as constants in this module so
they won't get out of sync.

Historically we tried to avoid all message string literals in the type
checker but we are moving away from this convention.
"""

import re
import difflib

from typing import cast, List, Dict, Any, Sequence, Iterable, Tuple, Set, Optional, Union

from mypy.erasetype import erase_type
from mypy.errors import Errors
from mypy.types import (
    Type, CallableType, Instance, TypeVarType, TupleType, TypedDictType,
    UnionType, NoneTyp, AnyType, Overloaded, FunctionLike, DeletedType, TypeType,
    UninhabitedType, TypeOfAny, ForwardRef, UnboundType
)
from mypy.nodes import (
    TypeInfo, Context, MypyFile, op_methods, FuncDef, reverse_type_aliases,
    ARG_POS, ARG_OPT, ARG_NAMED, ARG_NAMED_OPT, ARG_STAR, ARG_STAR2,
    ReturnStmt, NameExpr, Var, CONTRAVARIANT, COVARIANT
)


# Constants that represent simple type checker error message, i.e. messages
# that do not have any parameters.

NO_RETURN_VALUE_EXPECTED = 'No return value expected'
MISSING_RETURN_STATEMENT = 'Missing return statement'
INVALID_IMPLICIT_RETURN = 'Implicit return in function which does not return'
INCOMPATIBLE_RETURN_VALUE_TYPE = 'Incompatible return value type'
RETURN_VALUE_EXPECTED = 'Return value expected'
NO_RETURN_EXPECTED = 'Return statement in function which does not return'
INVALID_EXCEPTION = 'Exception must be derived from BaseException'
INVALID_EXCEPTION_TYPE = 'Exception type must be derived from BaseException'
INVALID_RETURN_TYPE_FOR_GENERATOR = \
    'The return type of a generator function should be "Generator" or one of its supertypes'
INVALID_RETURN_TYPE_FOR_ASYNC_GENERATOR = \
    'The return type of an async generator function should be "AsyncGenerator" or one of its ' \
    'supertypes'
INVALID_GENERATOR_RETURN_ITEM_TYPE = \
    'The return type of a generator function must be None in its third type parameter in Python 2'
YIELD_VALUE_EXPECTED = 'Yield value expected'
INCOMPATIBLE_TYPES = 'Incompatible types'
INCOMPATIBLE_TYPES_IN_ASSIGNMENT = 'Incompatible types in assignment'
INCOMPATIBLE_REDEFINITION = 'Incompatible redefinition'
INCOMPATIBLE_TYPES_IN_AWAIT = 'Incompatible types in "await"'
INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AENTER = 'Incompatible types in "async with" for "__aenter__"'
INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AEXIT = 'Incompatible types in "async with" for "__aexit__"'
INCOMPATIBLE_TYPES_IN_ASYNC_FOR = 'Incompatible types in "async for"'

INCOMPATIBLE_TYPES_IN_YIELD = 'Incompatible types in "yield"'
INCOMPATIBLE_TYPES_IN_YIELD_FROM = 'Incompatible types in "yield from"'
INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION = 'Incompatible types in string interpolation'
MUST_HAVE_NONE_RETURN_TYPE = 'The return type of "{}" must be None'
INVALID_TUPLE_INDEX_TYPE = 'Invalid tuple index type'
TUPLE_INDEX_OUT_OF_RANGE = 'Tuple index out of range'
NEED_ANNOTATION_FOR_VAR = 'Need type annotation for variable'
ITERABLE_EXPECTED = 'Iterable expected'
ASYNC_ITERABLE_EXPECTED = 'AsyncIterable expected'
INVALID_SLICE_INDEX = 'Slice index must be an integer or None'
CANNOT_INFER_LAMBDA_TYPE = 'Cannot infer type of lambda'
CANNOT_INFER_ITEM_TYPE = 'Cannot infer iterable item type'
CANNOT_ACCESS_INIT = 'Cannot access "__init__" directly'
CANNOT_ASSIGN_TO_METHOD = 'Cannot assign to a method'
CANNOT_ASSIGN_TO_TYPE = 'Cannot assign to a type'
INCONSISTENT_ABSTRACT_OVERLOAD = \
    'Overloaded method has both abstract and non-abstract variants'
READ_ONLY_PROPERTY_OVERRIDES_READ_WRITE = \
    'Read-only property cannot override read-write property'
FORMAT_REQUIRES_MAPPING = 'Format requires a mapping'
RETURN_TYPE_CANNOT_BE_CONTRAVARIANT = "Cannot use a contravariant type variable as return type"
FUNCTION_PARAMETER_CANNOT_BE_COVARIANT = "Cannot use a covariant type variable as a parameter"
INCOMPATIBLE_IMPORT_OF = "Incompatible import of"
FUNCTION_TYPE_EXPECTED = "Function is missing a type annotation"
ONLY_CLASS_APPLICATION = "Type application is only supported for generic classes"
RETURN_TYPE_EXPECTED = "Function is missing a return type annotation"
ARGUMENT_TYPE_EXPECTED = "Function is missing a type annotation for one or more arguments"
KEYWORD_ARGUMENT_REQUIRES_STR_KEY_TYPE = \
    'Keyword argument only valid with "str" key type in call to "dict"'
ALL_MUST_BE_SEQ_STR = 'Type of __all__ must be {}, not {}'
INVALID_TYPEDDICT_ARGS = \
    'Expected keyword arguments, {...}, or dict(...) in TypedDict constructor'
TYPEDDICT_KEY_MUST_BE_STRING_LITERAL = \
    'Expected TypedDict key to be string literal'
MALFORMED_ASSERT = 'Assertion is always true, perhaps remove parentheses?'
NON_BOOLEAN_IN_CONDITIONAL = 'Condition must be a boolean'
DUPLICATE_TYPE_SIGNATURES = 'Function has duplicate type signatures'
GENERIC_INSTANCE_VAR_CLASS_ACCESS = 'Access to generic instance variables via class is ambiguous'
CANNOT_ISINSTANCE_TYPEDDICT = 'Cannot use isinstance() with a TypedDict type'
CANNOT_ISINSTANCE_NEWTYPE = 'Cannot use isinstance() with a NewType type'
BARE_GENERIC = 'Missing type parameters for generic type'
IMPLICIT_GENERIC_ANY_BUILTIN = 'Implicit generic "Any". Use \'{}\' and specify generic parameters'
INCOMPATIBLE_TYPEVAR_VALUE = 'Value of type variable "{}" of {} cannot be {}'
UNSUPPORTED_ARGUMENT_2_FOR_SUPER = 'Unsupported argument 2 for "super"'

ARG_CONSTRUCTOR_NAMES = {
    ARG_POS: "Arg",
    ARG_OPT: "DefaultArg",
    ARG_NAMED: "NamedArg",
    ARG_NAMED_OPT: "DefaultNamedArg",
    ARG_STAR: "VarArg",
    ARG_STAR2: "KwArg",
}


class MessageBuilder:
    """Helper class for reporting type checker error messages with parameters.

    The methods of this class need to be provided with the context within a
    file; the errors member manages the wider context.

    IDEA: Support a 'verbose mode' that includes full information about types
          in error messages and that may otherwise produce more detailed error
          messages.
    """

    # Report errors using this instance. It knows about the current file and
    # import context.
    errors = None  # type: Errors

    modules = None  # type: Dict[str, MypyFile]

    # Number of times errors have been disabled.
    disable_count = 0

    # Hack to deduplicate error messages from union types
    disable_type_names = 0

    def __init__(self, errors: Errors, modules: Dict[str, MypyFile]) -> None:
        self.errors = errors
        self.modules = modules
        self.disable_count = 0
        self.disable_type_names = 0

    #
    # Helpers
    #

    def copy(self) -> 'MessageBuilder':
        new = MessageBuilder(self.errors.copy(), self.modules)
        new.disable_count = self.disable_count
        new.disable_type_names = self.disable_type_names
        return new

    def add_errors(self, messages: 'MessageBuilder') -> None:
        """Add errors in messages to this builder."""
        if self.disable_count <= 0:
            for info in messages.errors.error_info:
                self.errors.add_error_info(info)

    def disable_errors(self) -> None:
        self.disable_count += 1

    def enable_errors(self) -> None:
        self.disable_count -= 1

    def is_errors(self) -> bool:
        return self.errors.is_errors()

    def report(self, msg: str, context: Optional[Context], severity: str,
               file: Optional[str] = None, origin: Optional[Context] = None,
               offset: int = 0) -> None:
        """Report an error or note (unless disabled)."""
        if self.disable_count <= 0:
            self.errors.report(context.get_line() if context else -1,
                               context.get_column() if context else -1,
                               msg.strip(), severity=severity, file=file, offset=offset,
                               origin_line=origin.get_line() if origin else None)

    def fail(self, msg: str, context: Optional[Context], file: Optional[str] = None,
             origin: Optional[Context] = None) -> None:
        """Report an error message (unless disabled)."""
        self.report(msg, context, 'error', file=file, origin=origin)

    def note(self, msg: str, context: Context, file: Optional[str] = None,
             origin: Optional[Context] = None, offset: int = 0) -> None:
        """Report a note (unless disabled)."""
        self.report(msg, context, 'note', file=file, origin=origin, offset=offset)

    def warn(self, msg: str, context: Context, file: Optional[str] = None,
             origin: Optional[Context] = None) -> None:
        """Report a warning message (unless disabled)."""
        self.report(msg, context, 'warning', file=file, origin=origin)

    def quote_type_string(self, type_string: str) -> str:
        """Quotes a type representation for use in messages."""
        no_quote_regex = r'^<(tuple|union): \d+ items>$'
        if (type_string in ['Module', 'overloaded function', '<nothing>', '<deleted>']
                or re.match(no_quote_regex, type_string) is not None or type_string.endswith('?')):
            # Messages are easier to read if these aren't quoted.  We use a
            # regex to match strings with variable contents.
            return type_string
        return '"{}"'.format(type_string)

    def format(self, typ: Type, verbosity: int = 0) -> str:
        """
        Convert a type to a relatively short string suitable for error messages.

        This method returns a string appropriate for unmodified use in error
        messages; this means that it will be quoted in most cases.  If
        modification of the formatted string is required, callers should use
        .format_bare.
        """
        return self.quote_type_string(self.format_bare(typ, verbosity))

    def format_bare(self, typ: Type, verbosity: int = 0) -> str:
        """
        Convert a type to a relatively short string suitable for error messages.

        This method will return an unquoted string.  If a caller doesn't need to
        perform post-processing on the string output, .format should be used
        instead.  (The caller may want to use .quote_type_string after
        processing has happened, to maintain consistent quoting in messages.)
        """
        if isinstance(typ, Instance):
            itype = typ
            # Get the short name of the type.
            if itype.type.fullname() in ('types.ModuleType',
                                         '_importlib_modulespec.ModuleType'):
                # Make some common error messages simpler and tidier.
                return 'Module'
            if verbosity >= 2:
                base_str = itype.type.fullname()
            else:
                base_str = itype.type.name()
            if itype.args == []:
                # No type arguments, just return the type name
                return base_str
            elif itype.type.fullname() == 'builtins.tuple':
                item_type_str = self.format_bare(itype.args[0])
                return 'Tuple[{}, ...]'.format(item_type_str)
            elif itype.type.fullname() in reverse_type_aliases:
                alias = reverse_type_aliases[itype.type.fullname()]
                alias = alias.split('.')[-1]
                items = [self.format_bare(arg) for arg in itype.args]
                return '{}[{}]'.format(alias, ', '.join(items))
            else:
                # There are type arguments. Convert the arguments to strings.
                # If the result is too long, replace arguments with [...].
                a = []  # type: List[str]
                for arg in itype.args:
                    a.append(self.format_bare(arg))
                s = ', '.join(a)
                if len((base_str + s)) < 150:
                    return '{}[{}]'.format(base_str, s)
                else:
                    return '{}[...]'.format(base_str)
        elif isinstance(typ, TypeVarType):
            # This is similar to non-generic instance types.
            return typ.name
        elif isinstance(typ, TupleType):
            # Prefer the name of the fallback class (if not tuple), as it's more informative.
            if typ.fallback.type.fullname() != 'builtins.tuple':
                return self.format_bare(typ.fallback)
            items = []
            for t in typ.items:
                items.append(self.format_bare(t))
            s = 'Tuple[{}]'.format(', '.join(items))
            if len(s) < 400:
                return s
            else:
                return '<tuple: {} items>'.format(len(items))
        elif isinstance(typ, TypedDictType):
            # If the TypedDictType is named, return the name
            if not typ.is_anonymous():
                return self.format_bare(typ.fallback)
            items = []
            for (item_name, item_type) in typ.items.items():
                modifier = '' if item_name in typ.required_keys else '?'
                items.append('{!r}{}: {}'.format(item_name,
                                                 modifier,
                                                 self.format_bare(item_type)))
            s = 'TypedDict({{{}}})'.format(', '.join(items))
            return s
        elif isinstance(typ, UnionType):
            # Only print Unions as Optionals if the Optional wouldn't have to contain another Union
            print_as_optional = (len(typ.items) -
                                 sum(isinstance(t, NoneTyp) for t in typ.items) == 1)
            if print_as_optional:
                rest = [t for t in typ.items if not isinstance(t, NoneTyp)]
                return 'Optional[{}]'.format(self.format_bare(rest[0]))
            else:
                items = []
                for t in typ.items:
                    items.append(self.format_bare(t))
                s = 'Union[{}]'.format(', '.join(items))
                if len(s) < 400:
                    return s
                else:
                    return '<union: {} items>'.format(len(items))
        elif isinstance(typ, NoneTyp):
            return 'None'
        elif isinstance(typ, AnyType):
            return 'Any'
        elif isinstance(typ, DeletedType):
            return '<deleted>'
        elif isinstance(typ, UninhabitedType):
            if typ.is_noreturn:
                return 'NoReturn'
            else:
                return '<nothing>'
        elif isinstance(typ, TypeType):
            return 'Type[{}]'.format(self.format_bare(typ.item, verbosity))
        elif isinstance(typ, ForwardRef):  # may appear in semanal.py
            if typ.resolved:
                return self.format_bare(typ.resolved, verbosity)
            else:
                return self.format_bare(typ.unbound, verbosity)
        elif isinstance(typ, FunctionLike):
            func = typ
            if func.is_type_obj():
                # The type of a type object type can be derived from the
                # return type (this always works).
                return self.format_bare(
                    TypeType.make_normalized(
                        erase_type(func.items()[0].ret_type)),
                    verbosity)
            elif isinstance(func, CallableType):
                return_type = self.format_bare(func.ret_type)
                if func.is_ellipsis_args:
                    return 'Callable[..., {}]'.format(return_type)
                arg_strings = []
                for arg_name, arg_type, arg_kind in zip(
                        func.arg_names, func.arg_types, func.arg_kinds):
                    if (arg_kind == ARG_POS and arg_name is None
                            or verbosity == 0 and arg_kind in (ARG_POS, ARG_OPT)):

                        arg_strings.append(
                            self.format_bare(
                                arg_type,
                                verbosity = max(verbosity - 1, 0)))
                    else:
                        constructor = ARG_CONSTRUCTOR_NAMES[arg_kind]
                        if arg_kind in (ARG_STAR, ARG_STAR2) or arg_name is None:
                            arg_strings.append("{}({})".format(
                                constructor,
                                self.format_bare(arg_type)))
                        else:
                            arg_strings.append("{}({}, {})".format(
                                constructor,
                                self.format_bare(arg_type),
                                repr(arg_name)))

                return 'Callable[[{}], {}]'.format(", ".join(arg_strings), return_type)
            else:
                # Use a simple representation for function types; proper
                # function types may result in long and difficult-to-read
                # error messages.
                return 'overloaded function'
        elif isinstance(typ, UnboundType):
            return str(typ)
        elif typ is None:
            raise RuntimeError('Type is None')
        else:
            # Default case; we simply have to return something meaningful here.
            return 'object'

    def format_distinctly(self, type1: Type, type2: Type, bare: bool = False) -> Tuple[str, str]:
        """Jointly format a pair of types to distinct strings.

        Increase the verbosity of the type strings until they become distinct.

        By default, the returned strings are created using .format() and will be
        quoted accordingly. If ``bare`` is True, the returned strings will not
        be quoted; callers who need to do post-processing of the strings before
        quoting them (such as prepending * or **) should use this.
        """
        if bare:
            format_method = self.format_bare
        else:
            format_method = self.format
        verbosity = 0
        for verbosity in range(3):
            str1 = format_method(type1, verbosity=verbosity)
            str2 = format_method(type2, verbosity=verbosity)
            if str1 != str2:
                return (str1, str2)
        return (str1, str2)

    #
    # Specific operations
    #

    # The following operations are for generating specific error messages. They
    # get some information as arguments, and they build an error message based
    # on them.

    def has_no_attr(self, original_type: Type, typ: Type, member: str, context: Context) -> Type:
        """Report a missing or non-accessible member.

        original_type is the top-level type on which the error occurred.
        typ is the actual type that is missing the member. These can be
        different, e.g., in a union, original_type will be the union and typ
        will be the specific item in the union that does not have the member
        attribute.

        If member corresponds to an operator, use the corresponding operator
        name in the messages. Return type Any.
        """
        if (isinstance(original_type, Instance) and
                original_type.type.has_readable_member(member)):
            self.fail('Member "{}" is not assignable'.format(member), context)
        elif member == '__contains__':
            self.fail('Unsupported right operand type for in ({})'.format(
                self.format(original_type)), context)
        elif member in op_methods.values():
            # Access to a binary operator member (e.g. _add). This case does
            # not handle indexing operations.
            for op, method in op_methods.items():
                if method == member:
                    self.unsupported_left_operand(op, original_type, context)
                    break
        elif member == '__neg__':
            self.fail('Unsupported operand type for unary - ({})'.format(
                self.format(original_type)), context)
        elif member == '__pos__':
            self.fail('Unsupported operand type for unary + ({})'.format(
                self.format(original_type)), context)
        elif member == '__invert__':
            self.fail('Unsupported operand type for ~ ({})'.format(
                self.format(original_type)), context)
        elif member == '__getitem__':
            # Indexed get.
            # TODO: Fix this consistently in self.format
            if isinstance(original_type, CallableType) and original_type.is_type_obj():
                self.fail('The type {} is not generic and not indexable'.format(
                    self.format(original_type)), context)
            else:
                self.fail('Value of type {} is not indexable'.format(
                    self.format(original_type)), context)
        elif member == '__setitem__':
            # Indexed set.
            self.fail('Unsupported target for indexed assignment', context)
        elif member == '__call__':
            if isinstance(original_type, Instance) and \
                    (original_type.type.fullname() == 'builtins.function'):
                # "'function' not callable" is a confusing error message.
                # Explain that the problem is that the type of the function is not known.
                self.fail('Cannot call function of unknown type', context)
            else:
                self.fail('{} not callable'.format(self.format(original_type)), context)
        else:
            # The non-special case: a missing ordinary attribute.
            if not self.disable_type_names:
                failed = False
                if isinstance(original_type, Instance) and original_type.type.names:
                    alternatives = set(original_type.type.names.keys())
                    matches = [m for m in COMMON_MISTAKES.get(member, []) if m in alternatives]
                    matches.extend(best_matches(member, alternatives)[:3])
                    if matches:
                        self.fail('{} has no attribute "{}"; maybe {}?'.format(
                            self.format(original_type), member, pretty_or(matches)), context)
                        failed = True
                if not failed:
                    self.fail('{} has no attribute "{}"'.format(self.format(original_type),
                                                                member), context)
            elif isinstance(original_type, UnionType):
                # The checker passes "object" in lieu of "None" for attribute
                # checks, so we manually convert it back.
                typ_format = self.format(typ)
                if typ_format == '"object"' and \
                        any(type(item) == NoneTyp for item in original_type.items):
                    typ_format = '"None"'
                self.fail('Item {} of {} has no attribute "{}"'.format(
                    typ_format, self.format(original_type), member), context)
        return AnyType(TypeOfAny.from_error)

    def unsupported_operand_types(self, op: str, left_type: Any,
                                  right_type: Any, context: Context) -> None:
        """Report unsupported operand types for a binary operation.

        Types can be Type objects or strings.
        """
        left_str = ''
        if isinstance(left_type, str):
            left_str = left_type
        else:
            left_str = self.format(left_type)

        right_str = ''
        if isinstance(right_type, str):
            right_str = right_type
        else:
            right_str = self.format(right_type)

        if self.disable_type_names:
            msg = 'Unsupported operand types for {} (likely involving Union)'.format(op)
        else:
            msg = 'Unsupported operand types for {} ({} and {})'.format(
                op, left_str, right_str)
        self.fail(msg, context)

    def unsupported_left_operand(self, op: str, typ: Type,
                                 context: Context) -> None:
        if self.disable_type_names:
            msg = 'Unsupported left operand type for {} (some union)'.format(op)
        else:
            msg = 'Unsupported left operand type for {} ({})'.format(
                op, self.format(typ))
        self.fail(msg, context)

    def not_callable(self, typ: Type, context: Context) -> Type:
        self.fail('{} not callable'.format(self.format(typ)), context)
        return AnyType(TypeOfAny.from_error)

    def untyped_function_call(self, callee: CallableType, context: Context) -> Type:
        name = callee.name if callee.name is not None else '(unknown)'
        self.fail('Call to untyped function {} in typed context'.format(name), context)
        return AnyType(TypeOfAny.from_error)

    def incompatible_argument(self, n: int, m: int, callee: CallableType, arg_type: Type,
                              arg_kind: int, context: Context) -> None:
        """Report an error about an incompatible argument type.

        The argument type is arg_type, argument number is n and the
        callee type is 'callee'. If the callee represents a method
        that corresponds to an operator, use the corresponding
        operator name in the messages.
        """
        target = ''
        if callee.name:
            name = callee.name
            if callee.bound_args and callee.bound_args[0] is not None:
                base = self.format(callee.bound_args[0])
            else:
                base = extract_type(name)

            for op, method in op_methods.items():
                for variant in method, '__r' + method[2:]:
                    if name.startswith('"{}" of'.format(variant)):
                        if op == 'in' or variant != method:
                            # Reversed order of base/argument.
                            self.unsupported_operand_types(op, arg_type, base,
                                                           context)
                        else:
                            self.unsupported_operand_types(op, base, arg_type,
                                                           context)
                        return

            if name.startswith('"__getitem__" of'):
                self.invalid_index_type(arg_type, callee.arg_types[n - 1], base, context)
                return

            if name.startswith('"__setitem__" of'):
                if n == 1:
                    self.invalid_index_type(arg_type, callee.arg_types[n - 1], base, context)
                else:
                    msg = '{} (expression has type {}, target has type {})'
                    arg_type_str, callee_type_str = self.format_distinctly(arg_type,
                                                                           callee.arg_types[n - 1])
                    self.fail(msg.format(INCOMPATIBLE_TYPES_IN_ASSIGNMENT,
                                         arg_type_str, callee_type_str),
                              context)
                return

            target = 'to {} '.format(name)

        msg = ''
        notes = []  # type: List[str]
        if callee.name == '<list>':
            name = callee.name[1:-1]
            n -= 1
            actual_type_str, expected_type_str = self.format_distinctly(arg_type,
                                                                        callee.arg_types[0])
            msg = '{} item {} has incompatible type {}; expected {}'.format(
                name.title(), n, actual_type_str, expected_type_str)
        elif callee.name == '<dict>':
            name = callee.name[1:-1]
            n -= 1
            key_type, value_type = cast(TupleType, arg_type).items
            expected_key_type, expected_value_type = cast(TupleType, callee.arg_types[0]).items

            # don't increase verbosity unless there is need to do so
            from mypy.subtypes import is_subtype
            if is_subtype(key_type, expected_key_type):
                key_type_str = self.format(key_type)
                expected_key_type_str = self.format(expected_key_type)
            else:
                key_type_str, expected_key_type_str = self.format_distinctly(
                    key_type, expected_key_type)
            if is_subtype(value_type, expected_value_type):
                value_type_str = self.format(value_type)
                expected_value_type_str = self.format(expected_value_type)
            else:
                value_type_str, expected_value_type_str = self.format_distinctly(
                    value_type, expected_value_type)

            msg = '{} entry {} has incompatible type {}: {}; expected {}: {}'.format(
                name.title(), n, key_type_str, value_type_str,
                expected_key_type_str, expected_value_type_str)
        elif callee.name == '<list-comprehension>':
            actual_type_str, expected_type_str = map(strip_quotes,
                                                     self.format_distinctly(arg_type,
                                                                            callee.arg_types[0]))
            msg = 'List comprehension has incompatible type List[{}]; expected List[{}]'.format(
                actual_type_str, expected_type_str)
        elif callee.name == '<set-comprehension>':
            actual_type_str, expected_type_str = map(strip_quotes,
                                                     self.format_distinctly(arg_type,
                                                                            callee.arg_types[0]))
            msg = 'Set comprehension has incompatible type Set[{}]; expected Set[{}]'.format(
                actual_type_str, expected_type_str)
        elif callee.name == '<dictionary-comprehension>':
            actual_type_str, expected_type_str = self.format_distinctly(arg_type,
                                                                        callee.arg_types[n - 1])
            msg = ('{} expression in dictionary comprehension has incompatible type {}; '
                   'expected type {}').format(
                'Key' if n == 1 else 'Value',
                actual_type_str,
                expected_type_str)
        elif callee.name == '<generator>':
            actual_type_str, expected_type_str = self.format_distinctly(arg_type,
                                                                        callee.arg_types[0])
            msg = 'Generator has incompatible item type {}; expected {}'.format(
                actual_type_str, expected_type_str)
        else:
            try:
                expected_type = callee.arg_types[m - 1]
            except IndexError:  # Varargs callees
                expected_type = callee.arg_types[-1]
            arg_type_str, expected_type_str = self.format_distinctly(
                arg_type, expected_type, bare=True)
            if arg_kind == ARG_STAR:
                arg_type_str = '*' + arg_type_str
            elif arg_kind == ARG_STAR2:
                arg_type_str = '**' + arg_type_str
            msg = 'Argument {} {}has incompatible type {}; expected {}'.format(
                n, target, self.quote_type_string(arg_type_str),
                self.quote_type_string(expected_type_str))
            if isinstance(arg_type, Instance) and isinstance(expected_type, Instance):
                notes = append_invariance_notes(notes, arg_type, expected_type)
        self.fail(msg, context)
        if notes:
            for note_msg in notes:
                self.note(note_msg, context)

    def invalid_index_type(self, index_type: Type, expected_type: Type, base_str: str,
                           context: Context) -> None:
        self.fail('Invalid index type {} for {}; expected type {}'.format(
            self.format(index_type), base_str, self.format(expected_type)), context)

    def too_few_arguments(self, callee: CallableType, context: Context,
                          argument_names: Optional[Sequence[Optional[str]]]) -> None:
        if (argument_names is not None and not all(k is None for k in argument_names)
                and len(argument_names) >= 1):
            diff = [k for k in callee.arg_names if k not in argument_names]
            if len(diff) == 1:
                msg = 'Missing positional argument'
            else:
                msg = 'Missing positional arguments'
            if callee.name and diff and all(d is not None for d in diff):
                msg += ' "{}" in call to {}'.format('", "'.join(cast(List[str], diff)),
                                                    callee.name)
        else:
            msg = 'Too few arguments'
            if callee.name:
                msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    def missing_named_argument(self, callee: CallableType, context: Context, name: str) -> None:
        msg = 'Missing named argument "{}"'.format(name)
        if callee.name:
            msg += ' for function {}'.format(callee.name)
        self.fail(msg, context)

    def too_many_arguments(self, callee: CallableType, context: Context) -> None:
        msg = 'Too many arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    def too_many_positional_arguments(self, callee: CallableType,
                                      context: Context) -> None:
        msg = 'Too many positional arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    def unexpected_keyword_argument(self, callee: CallableType, name: str,
                                    context: Context) -> None:
        msg = 'Unexpected keyword argument "{}"'.format(name)
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)
        module = find_defining_module(self.modules, callee)
        if module:
            assert callee.definition is not None
            self.note('{} defined here'.format(callee.name), callee.definition,
                      file=module.path, origin=context)

    def duplicate_argument_value(self, callee: CallableType, index: int,
                                 context: Context) -> None:
        self.fail('{} gets multiple values for keyword argument "{}"'.
                  format(capitalize(callable_name(callee)),
                         callee.arg_names[index]), context)

    def does_not_return_value(self, callee_type: Optional[Type], context: Context) -> None:
        """Report an error about use of an unusable type."""
        name = None  # type: Optional[str]
        if isinstance(callee_type, FunctionLike):
            name = callee_type.get_name()
        if name is not None:
            self.fail('{} does not return a value'.format(capitalize(name)), context)
        else:
            self.fail('Function does not return a value', context)

    def deleted_as_rvalue(self, typ: DeletedType, context: Context) -> None:
        """Report an error about using an deleted type as an rvalue."""
        if typ.source is None:
            s = ""
        else:
            s = " '{}'".format(typ.source)
        self.fail('Trying to read deleted variable{}'.format(s), context)

    def deleted_as_lvalue(self, typ: DeletedType, context: Context) -> None:
        """Report an error about using an deleted type as an lvalue.

        Currently, this only occurs when trying to assign to an
        exception variable outside the local except: blocks.
        """
        if typ.source is None:
            s = ""
        else:
            s = " '{}'".format(typ.source)
        self.fail('Assignment to variable{} outside except: block'.format(s), context)

    def no_variant_matches_arguments(self, overload: Overloaded, arg_types: List[Type],
                                     context: Context) -> None:
        if overload.name():
            self.fail('No overload variant of {} matches argument types {}'
                      .format(overload.name(), arg_types), context)
        else:
            self.fail('No overload variant matches argument types {}'.format(arg_types), context)

    def wrong_number_values_to_unpack(self, provided: int, expected: int,
                                      context: Context) -> None:
        if provided < expected:
            if provided == 1:
                self.fail('Need more than 1 value to unpack ({} expected)'.format(expected),
                          context)
            else:
                self.fail('Need more than {} values to unpack ({} expected)'.format(
                    provided, expected), context)
        elif provided > expected:
            self.fail('Too many values to unpack ({} expected, {} provided)'.format(
                expected, provided), context)

    def type_not_iterable(self, type: Type, context: Context) -> None:
        self.fail('\'{}\' object is not iterable'.format(type), context)

    def incompatible_operator_assignment(self, op: str,
                                         context: Context) -> None:
        self.fail('Result type of {} incompatible in assignment'.format(op),
                  context)

    def signature_incompatible_with_supertype(
            self, name: str, name_in_super: str, supertype: str,
            context: Context) -> None:
        target = self.override_target(name, name_in_super, supertype)
        self.fail('Signature of "{}" incompatible with {}'.format(
            name, target), context)

    def argument_incompatible_with_supertype(
            self, arg_num: int, name: str, name_in_supertype: str,
            supertype: str, context: Context) -> None:
        target = self.override_target(name, name_in_supertype, supertype)
        self.fail('Argument {} of "{}" incompatible with {}'
                  .format(arg_num, name, target), context)

    def return_type_incompatible_with_supertype(
            self, name: str, name_in_supertype: str, supertype: str,
            context: Context) -> None:
        target = self.override_target(name, name_in_supertype, supertype)
        self.fail('Return type of "{}" incompatible with {}'
                  .format(name, target), context)

    def override_target(self, name: str, name_in_super: str,
                        supertype: str) -> str:
        target = 'supertype "{}"'.format(supertype)
        if name_in_super != name:
            target = '"{}" of {}'.format(name_in_super, target)
        return target

    def incompatible_type_application(self, expected_arg_count: int,
                                      actual_arg_count: int,
                                      context: Context) -> None:
        if expected_arg_count == 0:
            self.fail('Type application targets a non-generic function or class',
                      context)
        elif actual_arg_count > expected_arg_count:
            self.fail('Type application has too many types ({} expected)'
                      .format(expected_arg_count), context)
        else:
            self.fail('Type application has too few types ({} expected)'
                      .format(expected_arg_count), context)

    def could_not_infer_type_arguments(self, callee_type: CallableType, n: int,
                                       context: Context) -> None:
        if callee_type.name and n > 0:
            self.fail('Cannot infer type argument {} of {}'.format(
                n, callee_type.name), context)
        else:
            self.fail('Cannot infer function type argument', context)

    def invalid_var_arg(self, typ: Type, context: Context) -> None:
        self.fail('List or tuple expected as variable arguments', context)

    def invalid_keyword_var_arg(self, typ: Type, is_mapping: bool, context: Context) -> None:
        if isinstance(typ, Instance) and is_mapping:
            self.fail('Keywords must be strings', context)
        else:
            suffix = ''
            if isinstance(typ, Instance):
                suffix = ', not {}'.format(self.format(typ))
            self.fail(
                'Argument after ** must be a mapping{}'.format(suffix),
                context)

    def undefined_in_superclass(self, member: str, context: Context) -> None:
        self.fail('"{}" undefined in superclass'.format(member), context)

    def first_argument_for_super_must_be_type(self, actual: Type, context: Context) -> None:
        if isinstance(actual, Instance):
            # Don't include type of instance, because it can look confusingly like a type
            # object.
            type_str = 'a non-type instance'
        else:
            type_str = self.format(actual)
        self.fail('Argument 1 for "super" must be a type object; got {}'.format(type_str), context)

    def too_few_string_formatting_arguments(self, context: Context) -> None:
        self.fail('Not enough arguments for format string', context)

    def too_many_string_formatting_arguments(self, context: Context) -> None:
        self.fail('Not all arguments converted during string formatting', context)

    def unsupported_placeholder(self, placeholder: str, context: Context) -> None:
        self.fail('Unsupported format character \'%s\'' % placeholder, context)

    def string_interpolation_with_star_and_key(self, context: Context) -> None:
        self.fail('String interpolation contains both stars and mapping keys', context)

    def requires_int_or_char(self, context: Context) -> None:
        self.fail('%c requires int or char', context)

    def key_not_in_mapping(self, key: str, context: Context) -> None:
        self.fail('Key \'%s\' not found in mapping' % key, context)

    def string_interpolation_mixing_key_and_non_keys(self, context: Context) -> None:
        self.fail('String interpolation mixes specifier with and without mapping keys', context)

    def cannot_determine_type(self, name: str, context: Context) -> None:
        self.fail("Cannot determine type of '%s'" % name, context)

    def cannot_determine_type_in_base(self, name: str, base: str, context: Context) -> None:
        self.fail("Cannot determine type of '%s' in base class '%s'" % (name, base), context)

    def no_formal_self(self, name: str, item: CallableType, context: Context) -> None:
        self.fail('Attribute function "%s" with type %s does not accept self argument'
                  % (name, self.format(item)), context)

    def incompatible_self_argument(self, name: str, arg: Type, sig: CallableType,
                                   is_classmethod: bool, context: Context) -> None:
        kind = 'class attribute function' if is_classmethod else 'attribute function'
        self.fail('Invalid self argument %s to %s "%s" with type %s'
                  % (self.format(arg), kind, name, self.format(sig)), context)

    def incompatible_conditional_function_def(self, defn: FuncDef) -> None:
        self.fail('All conditional function variants must have identical '
                  'signatures', defn)

    def cannot_instantiate_abstract_class(self, class_name: str,
                                          abstract_attributes: List[str],
                                          context: Context) -> None:
        attrs = format_string_list("'%s'" % a for a in abstract_attributes)
        self.fail("Cannot instantiate abstract class '%s' with abstract "
                  "attribute%s %s" % (class_name, plural_s(abstract_attributes),
                                   attrs),
                  context)

    def base_class_definitions_incompatible(self, name: str, base1: TypeInfo,
                                            base2: TypeInfo,
                                            context: Context) -> None:
        self.fail('Definition of "{}" in base class "{}" is incompatible '
                  'with definition in base class "{}"'.format(
                      name, base1.name(), base2.name()), context)

    def cant_assign_to_method(self, context: Context) -> None:
        self.fail(CANNOT_ASSIGN_TO_METHOD, context)

    def cant_assign_to_classvar(self, name: str, context: Context) -> None:
        self.fail('Cannot assign to class variable "%s" via instance' % name, context)

    def read_only_property(self, name: str, type: TypeInfo,
                           context: Context) -> None:
        self.fail('Property "{}" defined in "{}" is read-only'.format(
            name, type.name()), context)

    def incompatible_typevar_value(self,
                                   callee: CallableType,
                                   typ: Type,
                                   typevar_name: str,
                                   context: Context) -> None:
        self.fail(INCOMPATIBLE_TYPEVAR_VALUE.format(typevar_name, callable_name(callee),
                                                    self.format(typ)), context)

    def overloaded_signatures_overlap(self, index1: int, index2: int,
                                      context: Context) -> None:
        self.fail('Overloaded function signatures {} and {} overlap with '
                  'incompatible return types'.format(index1, index2), context)

    def overloaded_signatures_arg_specific(self, index1: int, context: Context) -> None:
        self.fail('Overloaded function implementation does not accept all possible arguments '
                  'of signature {}'.format(index1), context)

    def overloaded_signatures_ret_specific(self, index1: int, context: Context) -> None:
        self.fail('Overloaded function implementation cannot produce return type '
                  'of signature {}'.format(index1), context)

    def operator_method_signatures_overlap(
            self, reverse_class: str, reverse_method: str, forward_class: str,
            forward_method: str, context: Context) -> None:
        self.fail('Signatures of "{}" of "{}" and "{}" of "{}" '
                  'are unsafely overlapping'.format(
                      reverse_method, reverse_class,
                      forward_method, forward_class),
                  context)

    def forward_operator_not_callable(
            self, forward_method: str, context: Context) -> None:
        self.fail('Forward operator "{}" is not callable'.format(
            forward_method), context)

    def signatures_incompatible(self, method: str, other_method: str,
                                context: Context) -> None:
        self.fail('Signatures of "{}" and "{}" are incompatible'.format(
            method, other_method), context)

    def yield_from_invalid_operand_type(self, expr: Type, context: Context) -> Type:
        text = self.format(expr) if self.format(expr) != 'object' else expr
        self.fail('"yield from" can\'t be applied to {}'.format(text), context)
        return AnyType(TypeOfAny.from_error)

    def invalid_signature(self, func_type: Type, context: Context) -> None:
        self.fail('Invalid signature "{}"'.format(func_type), context)

    def reveal_type(self, typ: Type, context: Context) -> None:
        self.fail('Revealed type is \'{}\''.format(typ), context)

    def unsupported_type_type(self, item: Type, context: Context) -> None:
        self.fail('Unsupported type Type[{}]'.format(self.format(item)), context)

    def redundant_cast(self, typ: Type, context: Context) -> None:
        self.note('Redundant cast to {}'.format(self.format(typ)), context)

    def unimported_type_becomes_any(self, prefix: str, typ: Type, ctx: Context) -> None:
        self.fail("{} becomes {} due to an unfollowed import".format(prefix, self.format(typ)),
                  ctx)

    def explicit_any(self, ctx: Context) -> None:
        self.fail('Explicit "Any" is not allowed', ctx)

    def unexpected_typeddict_keys(
            self,
            typ: TypedDictType,
            expected_keys: List[str],
            actual_keys: List[str],
            context: Context) -> None:
        actual_set = set(actual_keys)
        expected_set = set(expected_keys)
        if not typ.is_anonymous():
            # Generate simpler messages for some common special cases.
            if actual_set < expected_set:
                # Use list comprehension instead of set operations to preserve order.
                missing = [key for key in expected_keys if key not in actual_set]
                self.fail('{} missing for TypedDict {}'.format(
                    format_key_list(missing, short=True).capitalize(), self.format(typ)),
                    context)
                return
            else:
                extra = [key for key in actual_keys if key not in expected_set]
                if extra:
                    # If there are both extra and missing keys, only report extra ones for
                    # simplicity.
                    self.fail('Extra {} for TypedDict {}'.format(
                        format_key_list(extra, short=True), self.format(typ)),
                        context)
                    return
        if not expected_keys:
            expected = '(no keys)'
        else:
            expected = format_key_list(expected_keys)
        found = format_key_list(actual_keys, short=True)
        if actual_keys and actual_set < expected_set:
            found = 'only {}'.format(found)
        self.fail('Expected {} but found {}'.format(expected, found), context)

    def typeddict_key_must_be_string_literal(
            self,
            typ: TypedDictType,
            context: Context) -> None:
        self.fail(
            'TypedDict key must be a string literal; expected one of {}'.format(
                format_item_name_list(typ.items.keys())), context)

    def typeddict_key_not_found(
            self,
            typ: TypedDictType,
            item_name: str,
            context: Context) -> None:
        if typ.is_anonymous():
            self.fail('\'{}\' is not a valid TypedDict key; expected one of {}'.format(
                item_name, format_item_name_list(typ.items.keys())), context)
        else:
            self.fail("TypedDict {} has no key '{}'".format(self.format(typ), item_name), context)

    def type_arguments_not_allowed(self, context: Context) -> None:
        self.fail('Parameterized generics cannot be used with class or instance checks', context)

    def disallowed_any_type(self, typ: Type, context: Context) -> None:
        if isinstance(typ, AnyType):
            message = 'Expression has type "Any"'
        else:
            message = 'Expression type contains "Any" (has type {})'.format(self.format(typ))
        self.fail(message, context)

    def incorrectly_returning_any(self, typ: Type, context: Context) -> None:
        message = 'Returning Any from function declared to return {}'.format(
            self.format(typ))
        self.warn(message, context)

    def untyped_decorated_function(self, typ: Type, context: Context) -> None:
        if isinstance(typ, AnyType):
            self.fail("Function is untyped after decorator transformation", context)
        else:
            self.fail('Type of decorated function contains type "Any" ({})'.format(
                self.format(typ)), context)

    def typed_function_untyped_decorator(self, func_name: str, context: Context) -> None:
        self.fail('Untyped decorator makes function "{}" untyped'.format(func_name), context)

    def bad_proto_variance(self, actual: int, tvar_name: str, expected: int,
                           context: Context) -> None:
        msg = capitalize("{} type variable '{}' used in protocol where"
                         " {} one is expected".format(variance_string(actual),
                                                      tvar_name,
                                                      variance_string(expected)))
        self.fail(msg, context)

    def concrete_only_assign(self, typ: Type, context: Context) -> None:
        self.fail("Can only assign concrete classes to a variable of type {}"
                  .format(self.format(typ)), context)

    def concrete_only_call(self, typ: Type, context: Context) -> None:
        self.fail("Only concrete class can be given where {} is expected"
                  .format(self.format(typ)), context)

    def report_non_method_protocol(self, tp: TypeInfo, members: List[str],
                                   context: Context) -> None:
        self.fail("Only protocols that don't have non-method members can be"
                  " used with issubclass()", context)
        if len(members) < 3:
            attrs = ', '.join(members)
            self.note('Protocol "{}" has non-method member(s): {}'
                      .format(tp.name(), attrs), context)

    def note_call(self, subtype: Type, call: Type, context: Context) -> None:
        self.note('"{}.__call__" has type {}'.format(self.format_bare(subtype),
                                                     self.format(call, verbosity=1)), context)

    def report_protocol_problems(self, subtype: Union[Instance, TupleType, TypedDictType],
                                 supertype: Instance, context: Context) -> None:
        """Report possible protocol conflicts between 'subtype' and 'supertype'.

        This includes missing members, incompatible types, and incompatible
        attribute flags, such as settable vs read-only or class variable vs
        instance variable.
        """
        from mypy.subtypes import is_subtype, IS_SETTABLE, IS_CLASSVAR, IS_CLASS_OR_STATIC
        OFFSET = 4  # Four spaces, so that notes will look like this:
        # note: 'Cls' is missing following 'Proto' members:
        # note:     method, attr
        MAX_ITEMS = 2  # Maximum number of conflicts, missing members, and overloads shown
        # List of special situations where we don't want to report additional problems
        exclusions = {TypedDictType: ['typing.Mapping'],
                      TupleType: ['typing.Iterable', 'typing.Sequence'],
                      Instance: []}  # type: Dict[type, List[str]]
        if supertype.type.fullname() in exclusions[type(subtype)]:
            return
        if any(isinstance(tp, UninhabitedType) for tp in supertype.args):
            # We don't want to add notes for failed inference (e.g. Iterable[<nothing>]).
            # This will be only confusing a user even more.
            return

        if isinstance(subtype, (TupleType, TypedDictType)):
            if not isinstance(subtype.fallback, Instance):
                return
            subtype = subtype.fallback

        # Report missing members
        missing = get_missing_protocol_members(subtype, supertype)
        if (missing and len(missing) < len(supertype.type.protocol_members) and
                len(missing) <= MAX_ITEMS):
            self.note("'{}' is missing following '{}' protocol member{}:"
                      .format(subtype.type.name(), supertype.type.name(), plural_s(missing)),
                      context)
            self.note(', '.join(missing), context, offset=OFFSET)
        elif len(missing) > MAX_ITEMS or len(missing) == len(supertype.type.protocol_members):
            # This is an obviously wrong type: too many missing members
            return

        # Report member type conflicts
        conflict_types = get_conflict_protocol_types(subtype, supertype)
        if conflict_types and (not is_subtype(subtype, erase_type(supertype)) or
                               not subtype.type.defn.type_vars or
                               not supertype.type.defn.type_vars):
            self.note('Following member(s) of {} have '
                      'conflicts:'.format(self.format(subtype)), context)
            for name, got, exp in conflict_types[:MAX_ITEMS]:
                if (not isinstance(exp, (CallableType, Overloaded)) or
                        not isinstance(got, (CallableType, Overloaded))):
                    self.note('{}: expected {}, got {}'.format(name,
                                                               *self.format_distinctly(exp, got)),
                              context, offset=OFFSET)
                else:
                    self.note('Expected:', context, offset=OFFSET)
                    if isinstance(exp, CallableType):
                        self.note(self.pretty_callable(exp), context, offset=2 * OFFSET)
                    else:
                        assert isinstance(exp, Overloaded)
                        self.pretty_overload(exp, context, OFFSET, MAX_ITEMS)
                    self.note('Got:', context, offset=OFFSET)
                    if isinstance(got, CallableType):
                        self.note(self.pretty_callable(got), context, offset=2 * OFFSET)
                    else:
                        assert isinstance(got, Overloaded)
                        self.pretty_overload(got, context, OFFSET, MAX_ITEMS)
            self.print_more(conflict_types, context, OFFSET, MAX_ITEMS)

        # Report flag conflicts (i.e. settable vs read-only etc.)
        conflict_flags = get_bad_protocol_flags(subtype, supertype)
        for name, subflags, superflags in conflict_flags[:MAX_ITEMS]:
            if IS_CLASSVAR in subflags and IS_CLASSVAR not in superflags:
                self.note('Protocol member {}.{} expected instance variable,'
                          ' got class variable'.format(supertype.type.name(), name), context)
            if IS_CLASSVAR in superflags and IS_CLASSVAR not in subflags:
                self.note('Protocol member {}.{} expected class variable,'
                          ' got instance variable'.format(supertype.type.name(), name), context)
            if IS_SETTABLE in superflags and IS_SETTABLE not in subflags:
                self.note('Protocol member {}.{} expected settable variable,'
                          ' got read-only attribute'.format(supertype.type.name(), name), context)
            if IS_CLASS_OR_STATIC in superflags and IS_CLASS_OR_STATIC not in subflags:
                self.note('Protocol member {}.{} expected class or static method'
                          .format(supertype.type.name(), name), context)
        self.print_more(conflict_flags, context, OFFSET, MAX_ITEMS)

    def pretty_overload(self, tp: Overloaded, context: Context,
                        offset: int, max_items: int) -> None:
        for item in tp.items()[:max_items]:
            self.note('@overload', context, offset=2 * offset)
            self.note(self.pretty_callable(item), context, offset=2 * offset)
        if len(tp.items()) > max_items:
            self.note('<{} more overload(s) not shown>'.format(len(tp.items()) - max_items),
                      context, offset=2 * offset)

    def print_more(self, conflicts: Sequence[Any], context: Context,
                   offset: int, max_items: int) -> None:
        if len(conflicts) > max_items:
            self.note('<{} more conflict(s) not shown>'
                      .format(len(conflicts) - max_items),
                      context, offset=offset)

    def pretty_callable(self, tp: CallableType) -> str:
        """Return a nice easily-readable representation of a callable type.
        For example:
            def [T <: int] f(self, x: int, y: T) -> None
        """
        s = ''
        asterisk = False
        for i in range(len(tp.arg_types)):
            if s:
                s += ', '
            if tp.arg_kinds[i] in (ARG_NAMED, ARG_NAMED_OPT) and not asterisk:
                s += '*, '
                asterisk = True
            if tp.arg_kinds[i] == ARG_STAR:
                s += '*'
                asterisk = True
            if tp.arg_kinds[i] == ARG_STAR2:
                s += '**'
            name = tp.arg_names[i]
            if name:
                s += name + ': '
            s += self.format_bare(tp.arg_types[i])
            if tp.arg_kinds[i] in (ARG_OPT, ARG_NAMED_OPT):
                s += ' = ...'

        # If we got a "special arg" (i.e: self, cls, etc...), prepend it to the arg list
        if tp.definition is not None and tp.definition.name() is not None:
            definition_args = getattr(tp.definition, 'arg_names')
            if definition_args and tp.arg_names != definition_args \
                    and len(definition_args) > 0:
                if s:
                    s = ', ' + s
                s = definition_args[0] + s
            s = '{}({})'.format(tp.definition.name(), s)
        else:
            s = '({})'.format(s)

        s += ' -> ' + self.format_bare(tp.ret_type)
        if tp.variables:
            tvars = []
            for tvar in tp.variables:
                if (tvar.upper_bound and isinstance(tvar.upper_bound, Instance) and
                        tvar.upper_bound.type.fullname() != 'builtins.object'):
                    tvars.append('{} <: {}'.format(tvar.name,
                                                   self.format_bare(tvar.upper_bound)))
                elif tvar.values:
                    tvars.append('{} in ({})'
                                 .format(tvar.name, ', '.join([self.format_bare(tp)
                                                               for tp in tvar.values])))
                else:
                    tvars.append(tvar.name)
            s = '[{}] {}'.format(', '.join(tvars), s)
        return 'def {}'.format(s)


def variance_string(variance: int) -> str:
    if variance == COVARIANT:
        return 'covariant'
    elif variance == CONTRAVARIANT:
        return 'contravariant'
    else:
        return 'invariant'


def get_missing_protocol_members(left: Instance, right: Instance) -> List[str]:
    """Find all protocol members of 'right' that are not implemented
    (i.e. completely missing) in 'left'.
    """
    from mypy.subtypes import find_member
    assert right.type.is_protocol
    missing = []  # type: List[str]
    for member in right.type.protocol_members:
        if not find_member(member, left, left):
            missing.append(member)
    return missing


def get_conflict_protocol_types(left: Instance, right: Instance) -> List[Tuple[str, Type, Type]]:
    """Find members that are defined in 'left' but have incompatible types.
    Return them as a list of ('member', 'got', 'expected').
    """
    from mypy.subtypes import find_member, is_subtype, get_member_flags, IS_SETTABLE
    assert right.type.is_protocol
    conflicts = []  # type: List[Tuple[str, Type, Type]]
    for member in right.type.protocol_members:
        if member in ('__init__', '__new__'):
            continue
        supertype = find_member(member, right, left)
        assert supertype is not None
        subtype = find_member(member, left, left)
        if not subtype:
            continue
        is_compat = is_subtype(subtype, supertype, ignore_pos_arg_names=True)
        if IS_SETTABLE in get_member_flags(member, right.type):
            is_compat = is_compat and is_subtype(supertype, subtype)
        if not is_compat:
            conflicts.append((member, subtype, supertype))
    return conflicts


def get_bad_protocol_flags(left: Instance, right: Instance
                           ) -> List[Tuple[str, Set[int], Set[int]]]:
    """Return all incompatible attribute flags for members that are present in both
    'left' and 'right'.
    """
    from mypy.subtypes import (find_member, get_member_flags,
                               IS_SETTABLE, IS_CLASSVAR, IS_CLASS_OR_STATIC)
    assert right.type.is_protocol
    all_flags = []  # type: List[Tuple[str, Set[int], Set[int]]]
    for member in right.type.protocol_members:
        if find_member(member, left, left):
            item = (member,
                    get_member_flags(member, left.type),
                    get_member_flags(member, right.type))
            all_flags.append(item)
    bad_flags = []
    for name, subflags, superflags in all_flags:
        if (IS_CLASSVAR in subflags and IS_CLASSVAR not in superflags or
                IS_CLASSVAR in superflags and IS_CLASSVAR not in subflags or
                IS_SETTABLE in superflags and IS_SETTABLE not in subflags or
                IS_CLASS_OR_STATIC in superflags and IS_CLASS_OR_STATIC not in subflags):
            bad_flags.append((name, subflags, superflags))
    return bad_flags


def capitalize(s: str) -> str:
    """Capitalize the first character of a string."""
    if s == '':
        return ''
    else:
        return s[0].upper() + s[1:]


def extract_type(name: str) -> str:
    """If the argument is the name of a method (of form C.m), return
    the type portion in quotes (e.g. "y"). Otherwise, return the string
    unmodified.
    """
    name = re.sub('^"[a-zA-Z0-9_]+" of ', '', name)
    return name


def strip_quotes(s: str) -> str:
    """Strip a double quote at the beginning and end of the string, if any."""
    s = re.sub('^"', '', s)
    s = re.sub('"$', '', s)
    return s


def plural_s(s: Sequence[Any]) -> str:
    if len(s) > 1:
        return 's'
    else:
        return ''


def format_string_list(s: Iterable[str]) -> str:
    lst = list(s)
    assert len(lst) > 0
    if len(lst) == 1:
        return lst[0]
    elif len(lst) <= 5:
        return '%s and %s' % (', '.join(lst[:-1]), lst[-1])
    else:
        return '%s, ... and %s (%i methods suppressed)' % (
            ', '.join(lst[:2]), lst[-1], len(lst) - 3)


def format_item_name_list(s: Iterable[str]) -> str:
    lst = list(s)
    if len(lst) <= 5:
        return '(' + ', '.join(["'%s'" % name for name in lst]) + ')'
    else:
        return '(' + ', '.join(["'%s'" % name for name in lst[:5]]) + ', ...)'


def callable_name(type: CallableType) -> str:
    if type.name:
        return type.name
    else:
        return 'function'


def find_defining_module(modules: Dict[str, MypyFile], typ: CallableType) -> Optional[MypyFile]:
    if not typ.definition:
        return None
    fullname = typ.definition.fullname()
    if fullname is not None and '.' in fullname:
        for i in range(fullname.count('.')):
            module_name = fullname.rsplit('.', i + 1)[0]
            try:
                return modules[module_name]
            except KeyError:
                pass
        assert False, "Couldn't determine module from CallableType"
    return None


def temp_message_builder() -> MessageBuilder:
    """Return a message builder usable for throwaway errors (which may not format properly)."""
    return MessageBuilder(Errors(), {})


# For hard-coding suggested missing member alternatives.
COMMON_MISTAKES = {
    'add': ('append', 'extend'),
}  # type: Dict[str, Sequence[str]]


def best_matches(current: str, options: Iterable[str]) -> List[str]:
    ratios = {v: difflib.SequenceMatcher(a=current, b=v).ratio() for v in options}
    return sorted((o for o in options if ratios[o] > 0.75),
                  reverse=True, key=lambda v: (ratios[v], v))


def pretty_or(args: List[str]) -> str:
    quoted = ['"' + a + '"' for a in args]
    if len(quoted) == 1:
        return quoted[0]
    if len(quoted) == 2:
        return "{} or {}".format(quoted[0], quoted[1])
    return ", ".join(quoted[:-1]) + ", or " + quoted[-1]


def append_invariance_notes(notes: List[str], arg_type: Instance,
                            expected_type: Instance) -> List[str]:
    """Explain that the type is invariant and give notes for how to solve the issue."""
    from mypy.subtypes import is_subtype
    from mypy.sametypes import is_same_type
    invariant_type = ''
    covariant_suggestion = ''
    if (arg_type.type.fullname() == 'builtins.list' and
            expected_type.type.fullname() == 'builtins.list' and
            is_subtype(arg_type.args[0], expected_type.args[0])):
        invariant_type = 'List'
        covariant_suggestion = 'Consider using "Sequence" instead, which is covariant'
    elif (arg_type.type.fullname() == 'builtins.dict' and
          expected_type.type.fullname() == 'builtins.dict' and
          is_same_type(arg_type.args[0], expected_type.args[0]) and
          is_subtype(arg_type.args[1], expected_type.args[1])):
        invariant_type = 'Dict'
        covariant_suggestion = ('Consider using "Mapping" instead, '
                                'which is covariant in the value type')
    if invariant_type and covariant_suggestion:
        notes.append(
            '"{}" is invariant -- see '.format(invariant_type) +
            'http://mypy.readthedocs.io/en/latest/common_issues.html#variance')
        notes.append(covariant_suggestion)
    return notes


def make_inferred_type_note(context: Context, subtype: Type,
                            supertype: Type, supertype_str: str) -> str:
    """Explain that the user may have forgotten to type a variable.

    The user does not expect an error if the inferred container type is the same as the return
    type of a function and the argument type(s) are a subtype of the argument type(s) of the
    return type. This note suggests that they add a type annotation with the return type instead
    of relying on the inferred type.
    """
    from mypy.subtypes import is_subtype
    if (isinstance(subtype, Instance) and
            isinstance(supertype, Instance) and
            subtype.type.fullname() == supertype.type.fullname() and
            subtype.args and
            supertype.args and
            isinstance(context, ReturnStmt) and
            isinstance(context.expr, NameExpr) and
            isinstance(context.expr.node, Var) and
            context.expr.node.is_inferred):
        for subtype_arg, supertype_arg in zip(subtype.args, supertype.args):
            if not is_subtype(subtype_arg, supertype_arg):
                return ''
        var_name = context.expr.name
        return 'Perhaps you need a type annotation for "{}"? Suggestion: {}'.format(
            var_name, supertype_str)
    return ''


def format_key_list(keys: List[str], *, short: bool = False) -> str:
    reprs = [repr(key) for key in keys]
    td = '' if short else 'TypedDict '
    if len(keys) == 0:
        return 'no {}keys'.format(td)
    elif len(keys) == 1:
        return '{}key {}'.format(td, reprs[0])
    else:
        return '{}keys ({})'.format(td, ', '.join(reprs))
