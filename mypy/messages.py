"""Facilities for generating error messages during type checking.

Don't add any non-trivial message construction logic to the type
checker, as it can compromise clarity and make messages less
consistent. Add such logic to this module instead. Literal messages, including those
with format args, should be defined as constants in mypy.message_registry.

Historically we tried to avoid all message string literals in the type
checker but we are moving away from this convention.
"""
from contextlib import contextmanager

from mypy.backports import OrderedDict
import re
import difflib
from textwrap import dedent

from typing import cast, List, Dict, Any, Sequence, Iterable, Iterator, Tuple, Set, Optional, Union
from typing_extensions import Final

from mypy.erasetype import erase_type
from mypy.errors import Errors
from mypy.types import (
    Type, CallableType, Instance, TypeVarType, TupleType, TypedDictType, LiteralType,
    UnionType, NoneType, AnyType, Overloaded, FunctionLike, DeletedType, TypeType,
    UninhabitedType, TypeOfAny, UnboundType, PartialType, get_proper_type, ProperType,
    ParamSpecType, get_proper_types
)
from mypy.typetraverser import TypeTraverserVisitor
from mypy.nodes import (
    TypeInfo, Context, MypyFile, FuncDef, reverse_builtin_aliases,
    ArgKind, ARG_POS, ARG_OPT, ARG_NAMED, ARG_NAMED_OPT, ARG_STAR, ARG_STAR2,
    ReturnStmt, NameExpr, Var, CONTRAVARIANT, COVARIANT, SymbolNode,
    CallExpr, IndexExpr, StrExpr, SymbolTable, TempNode, SYMBOL_FUNCBASE_TYPES
)
from mypy.operators import op_methods, op_methods_to_symbols
from mypy.subtypes import (
    is_subtype, find_member, get_member_flags,
    IS_SETTABLE, IS_CLASSVAR, IS_CLASS_OR_STATIC,
)
from mypy.sametypes import is_same_type
from mypy.util import unmangle
from mypy.errorcodes import ErrorCode
from mypy.message_registry import ErrorMessage
from mypy import message_registry, errorcodes as codes

TYPES_FOR_UNIMPORTED_HINTS: Final = {
    'typing.Any',
    'typing.Callable',
    'typing.Dict',
    'typing.Iterable',
    'typing.Iterator',
    'typing.List',
    'typing.Optional',
    'typing.Set',
    'typing.Tuple',
    'typing.TypeVar',
    'typing.Union',
    'typing.cast',
}


ARG_CONSTRUCTOR_NAMES: Final = {
    ARG_POS: "Arg",
    ARG_OPT: "DefaultArg",
    ARG_NAMED: "NamedArg",
    ARG_NAMED_OPT: "DefaultNamedArg",
    ARG_STAR: "VarArg",
    ARG_STAR2: "KwArg",
}


# Map from the full name of a missing definition to the test fixture (under
# test-data/unit/fixtures/) that provides the definition. This is used for
# generating better error messages when running mypy tests only.
SUGGESTED_TEST_FIXTURES: Final = {
    'builtins.list': 'list.pyi',
    'builtins.dict': 'dict.pyi',
    'builtins.set': 'set.pyi',
    'builtins.tuple': 'tuple.pyi',
    'builtins.bool': 'bool.pyi',
    'builtins.Exception': 'exception.pyi',
    'builtins.BaseException': 'exception.pyi',
    'builtins.isinstance': 'isinstancelist.pyi',
    'builtins.property': 'property.pyi',
    'builtins.classmethod': 'classmethod.pyi',
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
    errors: Errors

    modules: Dict[str, MypyFile]

    # Number of times errors have been disabled.
    disable_count = 0

    # Hack to deduplicate error messages from union types
    disable_type_names_count = 0

    def __init__(self, errors: Errors, modules: Dict[str, MypyFile]) -> None:
        self.errors = errors
        self.modules = modules
        self.disable_count = 0
        self.disable_type_names_count = 0

    #
    # Helpers
    #

    def copy(self) -> 'MessageBuilder':
        new = MessageBuilder(self.errors.copy(), self.modules)
        new.disable_count = self.disable_count
        new.disable_type_names_count = self.disable_type_names_count
        return new

    def clean_copy(self) -> 'MessageBuilder':
        errors = self.errors.copy()
        errors.error_info_map = OrderedDict()
        return MessageBuilder(errors, self.modules)

    def add_errors(self, messages: 'MessageBuilder') -> None:
        """Add errors in messages to this builder."""
        if self.disable_count <= 0:
            for errs in messages.errors.error_info_map.values():
                for info in errs:
                    self.errors.add_error_info(info)

    @contextmanager
    def disable_errors(self) -> Iterator[None]:
        self.disable_count += 1
        try:
            yield
        finally:
            self.disable_count -= 1

    @contextmanager
    def disable_type_names(self) -> Iterator[None]:
        self.disable_type_names_count += 1
        try:
            yield
        finally:
            self.disable_type_names_count -= 1

    def is_errors(self) -> bool:
        return self.errors.is_errors()

    def most_recent_context(self) -> Context:
        """Return a dummy context matching the most recent generated error in current file."""
        line, column = self.errors.most_recent_error_location()
        node = TempNode(NoneType())
        node.line = line
        node.column = column
        return node

    def report(self,
               msg: str,
               context: Optional[Context],
               severity: str,
               *,
               code: Optional[ErrorCode] = None,
               file: Optional[str] = None,
               origin: Optional[Context] = None,
               offset: int = 0,
               allow_dups: bool = False) -> None:
        """Report an error or note (unless disabled)."""
        if origin is not None:
            end_line = origin.end_line
        elif context is not None:
            end_line = context.end_line
        else:
            end_line = None
        if self.disable_count <= 0:
            self.errors.report(context.get_line() if context else -1,
                               context.get_column() if context else -1,
                               msg, severity=severity, file=file, offset=offset,
                               origin_line=origin.get_line() if origin else None,
                               end_line=end_line, code=code, allow_dups=allow_dups)

    def fail(self,
             msg: Union[str, ErrorMessage],
             context: Optional[Context],
             *,
             code: Optional[ErrorCode] = None,
             file: Optional[str] = None,
             origin: Optional[Context] = None,
             allow_dups: bool = False) -> None:
        """Report an error message (unless disabled)."""
        # TODO(tushar): Remove `str` support after full migration
        if isinstance(msg, ErrorMessage):
            self.report(msg, context, 'error', code=code, file=file,
                        origin=origin, allow_dups=allow_dups)
            return

        self.report(msg, context, 'error', code=code, file=file,
                    origin=origin, allow_dups=allow_dups)

    def note(self,
             msg: str,
             context: Context,
             file: Optional[str] = None,
             origin: Optional[Context] = None,
             offset: int = 0,
             allow_dups: bool = False,
             *,
             code: Optional[ErrorCode] = None) -> None:
        """Report a note (unless disabled)."""
        self.report(msg, context, 'note', file=file, origin=origin,
                    offset=offset, allow_dups=allow_dups, code=code)

    def note_multiline(self, messages: str, context: Context, file: Optional[str] = None,
                       origin: Optional[Context] = None, offset: int = 0,
                       allow_dups: bool = False,
                       code: Optional[ErrorCode] = None) -> None:
        """Report as many notes as lines in the message (unless disabled)."""
        for msg in messages.splitlines():
            self.report(msg, context, 'note', file=file, origin=origin,
                        offset=offset, allow_dups=allow_dups, code=code)

    #
    # Specific operations
    #

    # The following operations are for generating specific error messages. They
    # get some information as arguments, and they build an error message based
    # on them.

    def has_no_attr(self,
                    original_type: Type,
                    typ: Type,
                    member: str,
                    context: Context,
                    module_symbol_table: Optional[SymbolTable] = None) -> Type:
        """Report a missing or non-accessible member.

        original_type is the top-level type on which the error occurred.
        typ is the actual type that is missing the member. These can be
        different, e.g., in a union, original_type will be the union and typ
        will be the specific item in the union that does not have the member
        attribute.

        'module_symbol_table' is passed to this function if the type for which we
        are trying to get a member was originally a module. The SymbolTable allows
        us to look up and suggests attributes of the module since they are not
        directly available on original_type

        If member corresponds to an operator, use the corresponding operator
        name in the messages. Return type Any.
        """
        original_type = get_proper_type(original_type)
        typ = get_proper_type(typ)

        if (isinstance(original_type, Instance) and
                original_type.type.has_readable_member(member)):
            self.fail(message_registry.MEMBER_NOT_ASSIGNABLE.format(member), context)
        elif member == '__contains__':
            self.fail(message_registry.UNSUPPORTED_OPERAND_FOR_IN.format(
                format_type(original_type)), context)
        elif member in op_methods.values():
            # Access to a binary operator member (e.g. _add). This case does
            # not handle indexing operations.
            for op, method in op_methods.items():
                if method == member:
                    self.unsupported_left_operand(op, original_type, context)
                    break
        elif member == '__neg__':
            self.fail(message_registry.UNSUPPORTED_OPERAND_FOR_UNARY_MINUS.format(
                format_type(original_type)), context)
        elif member == '__pos__':
            self.fail(message_registry.UNSUPPORTED_OPERAND_FOR_UNARY_PLUS.format(
                format_type(original_type)), context)
        elif member == '__invert__':
            self.fail(message_registry.UNSUPPORTED_OPERAND_FOR_INVERT.format(
                format_type(original_type)), context)
        elif member == '__getitem__':
            # Indexed get.
            # TODO: Fix this consistently in format_type
            if isinstance(original_type, CallableType) and original_type.is_type_obj():
                self.fail(message_registry.TYPE_NOT_GENERIC_OR_INDEXABLE.format(
                    format_type(original_type)), context)
            else:
                self.fail(message_registry.TYPE_NOT_INDEXABLE.format(
                    format_type(original_type)), context)
        elif member == '__setitem__':
            # Indexed set.
            self.fail(message_registry.UNSUPPORTED_TARGET_INDEXED_ASSIGNMENT.format(
                format_type(original_type)), context)
        elif member == '__call__':
            if isinstance(original_type, Instance) and \
                    (original_type.type.fullname == 'builtins.function'):
                # "'function' not callable" is a confusing error message.
                # Explain that the problem is that the type of the function is not known.
                self.fail(message_registry.CALLING_FUNCTION_OF_UNKNOWN_TYPE, context)
            else:
                self.fail(message_registry.TYPE_NOT_CALLABLE.format(format_type(original_type)),
                    context)
        else:
            # The non-special case: a missing ordinary attribute.
            extra = ''
            if member == '__iter__':
                extra = ' (not iterable)'
            elif member == '__aiter__':
                extra = ' (not async iterable)'
            if not self.disable_type_names_count:
                failed = False
                if isinstance(original_type, Instance) and original_type.type.names:
                    alternatives = set(original_type.type.names.keys())

                    if module_symbol_table is not None:
                        alternatives |= {key for key in module_symbol_table.keys()}

                    # in some situations, the member is in the alternatives set
                    # but since we're in this function, we shouldn't suggest it
                    if member in alternatives:
                        alternatives.remove(member)

                    matches = [m for m in COMMON_MISTAKES.get(member, []) if m in alternatives]
                    matches.extend(best_matches(member, alternatives)[:3])
                    if member == '__aiter__' and matches == ['__iter__']:
                        matches = []  # Avoid misleading suggestion
                    if member == '__div__' and matches == ['__truediv__']:
                        # TODO: Handle differences in division between Python 2 and 3 more cleanly
                        matches = []
                    if matches:
                        self.fail(
                            message_registry.TYPE_HAS_NO_ATTRIBUTE_X_MAYBE_Y.format(
                                format_type(original_type),
                                member,
                                pretty_seq(matches, "or"),
                                extra,
                            ),
                            context)
                        failed = True
                if not failed:
                    self.fail(
                        message_registry.TYPE_HAS_NO_ATTRIBUTE_X.format(
                            format_type(original_type), member, extra),
                        context)
            elif isinstance(original_type, UnionType):
                # The checker passes "object" in lieu of "None" for attribute
                # checks, so we manually convert it back.
                typ_format, orig_type_format = format_type_distinctly(typ, original_type)
                if typ_format == '"object"' and \
                        any(type(item) == NoneType for item in original_type.items):
                    typ_format = '"None"'
                self.fail(message_registry.ITEM_HAS_NO_ATTRIBUTE_X.format(
                    typ_format, orig_type_format, member, extra), context)
            elif isinstance(original_type, TypeVarType):
                bound = get_proper_type(original_type.upper_bound)
                if isinstance(bound, UnionType):
                    typ_fmt, bound_fmt = format_type_distinctly(typ, bound)
                    original_type_fmt = format_type(original_type)
                    self.fail(
                        message_registry.TYPEVAR_UPPER_BOUND_HAS_NO_ATTRIBUTE.format(
                            typ_fmt, bound_fmt, original_type_fmt, member, extra),
                        context, code=codes.UNION_ATTR)
        return AnyType(TypeOfAny.from_error)

    def unsupported_operand_types(self,
                                  op: str,
                                  left_type: Any,
                                  right_type: Any,
                                  context: Context) -> None:
        """Report unsupported operand types for a binary operation.

        Types can be Type objects or strings.
        """
        left_str = ''
        if isinstance(left_type, str):
            left_str = left_type
        else:
            left_str = format_type(left_type)

        right_str = ''
        if isinstance(right_type, str):
            right_str = right_type
        else:
            right_str = format_type(right_type)

        if self.disable_type_names_count:
            msg = message_registry.UNSUPPORTED_OPERANDS_LIKELY_UNION.format(op)
        else:
            msg = message_registry.UNSUPPORTED_OPERANDS.format(op, left_str, right_str)
        self.fail(msg, context)

    def unsupported_left_operand(self, op: str, typ: Type,
                                 context: Context) -> None:
        if self.disable_type_names_count:
            msg = message_registry.UNSUPPORTED_LEFT_OPERAND_TYPE_UNION.format(op)
        else:
            msg = message_registry.UNSUPPORTED_LEFT_OPERAND_TYPE.format(op, format_type(typ))
        self.fail(msg, context)

    def not_callable(self, typ: Type, context: Context) -> Type:
        self.fail(message_registry.TYPE_NOT_CALLABLE_2.format(format_type(typ)), context)
        return AnyType(TypeOfAny.from_error)

    def untyped_function_call(self, callee: CallableType, context: Context) -> Type:
        name = callable_name(callee) or '(unknown)'
        self.fail(message_registry.UNTYPED_FUNCTION_CALL.format(name), context)
        return AnyType(TypeOfAny.from_error)

    def incompatible_argument(self,
                              n: int,
                              m: int,
                              callee: CallableType,
                              arg_type: Type,
                              arg_kind: ArgKind,
                              object_type: Optional[Type],
                              context: Context,
                              outer_context: Context) -> Optional[ErrorCode]:
        """Report an error about an incompatible argument type.

        The argument type is arg_type, argument number is n and the
        callee type is 'callee'. If the callee represents a method
        that corresponds to an operator, use the corresponding
        operator name in the messages.

        Return the error code that used for the argument (multiple error
        codes are possible).
        """
        arg_type = get_proper_type(arg_type)

        target = ''
        callee_name = callable_name(callee)
        if callee_name is not None:
            name = callee_name
            if callee.bound_args and callee.bound_args[0] is not None:
                base = format_type(callee.bound_args[0])
            else:
                base = extract_type(name)

            for method, op in op_methods_to_symbols.items():
                for variant in method, '__r' + method[2:]:
                    # FIX: do not rely on textual formatting
                    if name.startswith('"{}" of'.format(variant)):
                        if op == 'in' or variant != method:
                            # Reversed order of base/argument.
                            self.unsupported_operand_types(op, arg_type, base, context)
                        else:
                            self.unsupported_operand_types(op, base, arg_type, context)
                        return codes.OPERATOR

            if name.startswith('"__cmp__" of'):
                self.unsupported_operand_types("comparison", arg_type, base, context)
                return codes.OPERATOR

            if name.startswith('"__getitem__" of'):
                self.invalid_index_type(arg_type, callee.arg_types[n - 1], base, context)
                return codes.INDEX

            if name.startswith('"__setitem__" of'):
                if n == 1:
                    self.invalid_index_type(arg_type, callee.arg_types[n - 1], base, context)
                    return codes.INDEX
                else:
                    msg = message_registry.TARGET_INCOMPATIBLE_TYPE
                    arg_type_str, callee_type_str = format_type_distinctly(arg_type,
                                                                           callee.arg_types[n - 1])
                    self.fail(msg.format(message_registry.INCOMPATIBLE_TYPES_IN_ASSIGNMENT,
                                         arg_type_str, callee_type_str),
                              context)
                    return codes.ASSIGNMENT

            target = 'to {} '.format(name)

        msg = ''
        code = codes.MISC
        notes: List[str] = []
        if callee_name == '<list>':
            name = callee_name[1:-1]
            n -= 1
            actual_type_str, expected_type_str = format_type_distinctly(arg_type,
                                                                        callee.arg_types[0])
            msg = message_registry.LIST_ITEM_INCOMPATIBLE_TYPE.format(
                name.title(), n, actual_type_str, expected_type_str)
        elif callee_name == '<dict>':
            name = callee_name[1:-1]
            n -= 1
            key_type, value_type = cast(TupleType, arg_type).items
            expected_key_type, expected_value_type = cast(TupleType, callee.arg_types[0]).items

            # don't increase verbosity unless there is need to do so
            if is_subtype(key_type, expected_key_type):
                key_type_str = format_type(key_type)
                expected_key_type_str = format_type(expected_key_type)
            else:
                key_type_str, expected_key_type_str = format_type_distinctly(
                    key_type, expected_key_type)
            if is_subtype(value_type, expected_value_type):
                value_type_str = format_type(value_type)
                expected_value_type_str = format_type(expected_value_type)
            else:
                value_type_str, expected_value_type_str = format_type_distinctly(
                    value_type, expected_value_type)

            msg = message_registry.DICT_ENTRY_INCOMPATIBLE_TYPE.format(
                name.title(), n, key_type_str, value_type_str,
                expected_key_type_str, expected_value_type_str)
        elif callee_name == '<list-comprehension>':
            actual_type_str, expected_type_str = map(strip_quotes,
                                                     format_type_distinctly(arg_type,
                                                                            callee.arg_types[0]))
            msg = message_registry.LIST_COMP_INCOMPATIBLE_TYPE.format(
                actual_type_str, expected_type_str)
        elif callee_name == '<set-comprehension>':
            actual_type_str, expected_type_str = map(strip_quotes,
                                                     format_type_distinctly(arg_type,
                                                                            callee.arg_types[0]))
            msg = message_registry.SET_COMP_INCOMPATIBLE_TYPE.format(
                actual_type_str, expected_type_str)
        elif callee_name == '<dictionary-comprehension>':
            actual_type_str, expected_type_str = format_type_distinctly(arg_type,
                                                                        callee.arg_types[n - 1])
            msg = message_registry.DICT_COMP_INCOMPATIBLE_TYPE.format(
                'Key' if n == 1 else 'Value',
                actual_type_str,
                expected_type_str)
        elif callee_name == '<generator>':
            actual_type_str, expected_type_str = format_type_distinctly(arg_type,
                                                                        callee.arg_types[0])
            msg = message_registry.GENERATOR_INCOMPATIBLE_TYPE.format(
                actual_type_str, expected_type_str)
        else:
            try:
                expected_type = callee.arg_types[m - 1]
            except IndexError:  # Varargs callees
                expected_type = callee.arg_types[-1]
            arg_type_str, expected_type_str = format_type_distinctly(
                arg_type, expected_type, bare=True)
            if arg_kind == ARG_STAR:
                arg_type_str = '*' + arg_type_str
            elif arg_kind == ARG_STAR2:
                arg_type_str = '**' + arg_type_str

            # For function calls with keyword arguments, display the argument name rather than the
            # number.
            arg_label = str(n)
            if isinstance(outer_context, CallExpr) and len(outer_context.arg_names) >= n:
                arg_name = outer_context.arg_names[n - 1]
                if arg_name is not None:
                    arg_label = '"{}"'.format(arg_name)
            if (arg_kind == ARG_STAR2
                    and isinstance(arg_type, TypedDictType)
                    and m <= len(callee.arg_names)
                    and callee.arg_names[m - 1] is not None
                    and callee.arg_kinds[m - 1] != ARG_STAR2):
                arg_name = callee.arg_names[m - 1]
                assert arg_name is not None
                arg_type_str, expected_type_str = format_type_distinctly(
                    arg_type.items[arg_name],
                    expected_type,
                    bare=True)
                arg_label = '"{}"'.format(arg_name)
            if isinstance(outer_context, IndexExpr) and isinstance(outer_context.index, StrExpr):
                msg = message_registry.VALUE_INCOMPATIBLE_TYPE.format(
                    outer_context.index.value, quote_type_string(arg_type_str),
                    quote_type_string(expected_type_str))
            else:
                msg = message_registry.ARGUMENT_INCOMPATIBLE_TYPE.format(
                    arg_label, target, quote_type_string(arg_type_str),
                    quote_type_string(expected_type_str))
            object_type = get_proper_type(object_type)
            if isinstance(object_type, TypedDictType):
                code = codes.TYPEDDICT_ITEM
            else:
                code = codes.ARG_TYPE
            expected_type = get_proper_type(expected_type)
            if isinstance(expected_type, UnionType):
                expected_types = list(expected_type.items)
            else:
                expected_types = [expected_type]
            for type in get_proper_types(expected_types):
                if isinstance(arg_type, Instance) and isinstance(type, Instance):
                    notes = append_invariance_notes(notes, arg_type, type)
        self.fail(msg, context)
        if notes:
            for note_msg in notes:
                self.note(note_msg, context, code=code)
        return msg.code

    def incompatible_argument_note(self,
                                   original_caller_type: ProperType,
                                   callee_type: ProperType,
                                   context: Context,
                                   code: Optional[ErrorCode]) -> None:
        if isinstance(original_caller_type, (Instance, TupleType, TypedDictType)):
            if isinstance(callee_type, Instance) and callee_type.type.is_protocol:
                self.report_protocol_problems(original_caller_type, callee_type,
                                              context, code=code)
            if isinstance(callee_type, UnionType):
                for item in callee_type.items:
                    item = get_proper_type(item)
                    if isinstance(item, Instance) and item.type.is_protocol:
                        self.report_protocol_problems(original_caller_type, item,
                                                      context, code=code)
        if (isinstance(callee_type, CallableType) and
                isinstance(original_caller_type, Instance)):
            call = find_member('__call__', original_caller_type, original_caller_type,
                               is_operator=True)
            if call:
                self.note_call(original_caller_type, call, context, code=code)

    def invalid_index_type(self, index_type: Type, expected_type: Type, base_str: str,
                           context: Context) -> None:
        index_str, expected_str = format_type_distinctly(index_type, expected_type)
        self.fail(message_registry.INVALID_INDEX_TYPE.format(
            index_str, base_str, expected_str), context)

    def too_few_arguments(self, callee: CallableType, context: Context,
                          argument_names: Optional[Sequence[Optional[str]]]) -> None:
        if argument_names is not None:
            num_positional_args = sum(k is None for k in argument_names)
            arguments_left = callee.arg_names[num_positional_args:callee.min_args]
            diff = [k for k in arguments_left if k not in argument_names]
            if len(diff) == 1:
                msg = 'Missing positional argument'
            else:
                msg = 'Missing positional arguments'
            callee_name = callable_name(callee)
            if callee_name is not None and diff and all(d is not None for d in diff):
                args = '", "'.join(cast(List[str], diff))
                msg += ' "{}" in call to {}'.format(args, callee_name)
            else:
                msg = 'Too few arguments' + for_function(callee)

        else:
            msg = 'Too few arguments' + for_function(callee)
        self.fail(ErrorMessage(msg, codes.CALL_ARG), context)

    def missing_named_argument(self, callee: CallableType, context: Context, name: str) -> None:
        msg = 'Missing named argument "{}"'.format(name) + for_function(callee)
        self.fail(ErrorMessage(msg, codes.CALL_ARG), context)

    def too_many_arguments(self, callee: CallableType, context: Context) -> None:
        msg = 'Too many arguments' + for_function(callee)
        self.fail(ErrorMessage(msg, codes.CALL_ARG), context)
        self.maybe_note_about_special_args(callee, context)

    def too_many_arguments_from_typed_dict(self,
                                           callee: CallableType,
                                           arg_type: TypedDictType,
                                           context: Context) -> None:
        # Try to determine the name of the extra argument.
        for key in arg_type.items:
            if key not in callee.arg_names:
                msg = 'Extra argument "{}" from **args'.format(key) + for_function(callee)
                break
        else:
            self.too_many_arguments(callee, context)
            return
        self.fail(ErrorMessage(msg), context)

    def too_many_positional_arguments(self, callee: CallableType,
                                      context: Context) -> None:
        msg = 'Too many positional arguments' + for_function(callee)
        self.fail(ErrorMessage(msg), context)
        self.maybe_note_about_special_args(callee, context)

    def maybe_note_about_special_args(self, callee: CallableType, context: Context) -> None:
        # https://github.com/python/mypy/issues/11309
        first_arg = callee.def_extras.get('first_arg')
        if first_arg and first_arg not in {'self', 'cls', 'mcs'}:
            self.note(
                'Looks like the first special argument in a method '
                'is not named "self", "cls", or "mcs", '
                'maybe it is missing?',
                context,
            )


    def unexpected_keyword_argument(self, callee: CallableType, name: str, arg_type: Type,
                                    context: Context) -> None:
        msg = 'Unexpected keyword argument "{}"'.format(name) + for_function(callee)
        # Suggest intended keyword, look for type match else fallback on any match.
        matching_type_args = []
        not_matching_type_args = []
        for i, kwarg_type in enumerate(callee.arg_types):
            callee_arg_name = callee.arg_names[i]
            if callee_arg_name is not None and callee.arg_kinds[i] != ARG_STAR:
                if is_subtype(arg_type, kwarg_type):
                    matching_type_args.append(callee_arg_name)
                else:
                    not_matching_type_args.append(callee_arg_name)
        matches = best_matches(name, matching_type_args)
        if not matches:
            matches = best_matches(name, not_matching_type_args)
        if matches:
            msg += "; did you mean {}?".format(pretty_seq(matches[:3], "or"))
        self.fail(ErrorMessage(msg, codes.CALL_ARG), context)
        module = find_defining_module(self.modules, callee)
        if module:
            assert callee.definition is not None
            fname = callable_name(callee)
            if not fname:  # an alias to function with a different name
                fname = 'Called function'
            self.note('{} defined here'.format(fname), callee.definition,
                      file=module.path, origin=context, code=codes.CALL_ARG)

    def duplicate_argument_value(self, callee: CallableType, index: int,
                                 context: Context) -> None:
        self.fail(message_registry.MULTIPLE_VALUES_FOR_KWARG.
                  format(callable_name(callee) or 'Function', callee.arg_names[index]),
                  context)

    def does_not_return_value(self, callee_type: Optional[Type], context: Context) -> None:
        """Report an error about use of an unusable type."""
        name: Optional[str] = None
        callee_type = get_proper_type(callee_type)
        if isinstance(callee_type, FunctionLike):
            name = callable_name(callee_type)
        if name is not None:
            self.fail(message_registry.NO_RETURN_VALUE.format(capitalize(name)), context)
        else:
            self.fail(message_registry.FUNCTION_NO_RETURN_VALUE, context)

    def underscore_function_call(self, context: Context) -> None:
        self.fail(message_registry.UNDERSCORE_FUNCTION_CALL, context)

    def deleted_as_rvalue(self, typ: DeletedType, context: Context) -> None:
        """Report an error about using an deleted type as an rvalue."""
        if typ.source is None:
            s = ""
        else:
            s = ' "{}"'.format(typ.source)
        self.fail(message_registry.READING_DELETED_VALUE.format(s), context)

    def deleted_as_lvalue(self, typ: DeletedType, context: Context) -> None:
        """Report an error about using an deleted type as an lvalue.

        Currently, this only occurs when trying to assign to an
        exception variable outside the local except: blocks.
        """
        if typ.source is None:
            s = ""
        else:
            s = ' "{}"'.format(typ.source)
        self.fail(message_registry.ASSIGNMENT_OUTSIDE_EXCEPT.format(s), context)

    def no_variant_matches_arguments(self,
                                     overload: Overloaded,
                                     arg_types: List[Type],
                                     context: Context,
                                     *,
                                     code: Optional[ErrorCode] = None) -> None:
        code = code or codes.CALL_OVERLOAD
        name = callable_name(overload)
        if name:
            name_str = ' of {}'.format(name)
        else:
            name_str = ''
        arg_types_str = ', '.join(format_type(arg) for arg in arg_types)
        num_args = len(arg_types)
        if num_args == 0:
            msg = 'All overload variants{} require at least one argument'.format(name_str)
            self.fail(ErrorMessage(msg, code), context)
        elif num_args == 1:
            msg = 'No overload variant{} matches argument type {}'.format(name_str, arg_types_str)
            self.fail(ErrorMessage(msg, code), context)
        else:
            msg = 'No overload variant{} matches argument types {}'.format(name_str, arg_types_str)
            self.fail(ErrorMessage(msg, code), context)

        self.note(
            'Possible overload variant{}:'.format(plural_s(len(overload.items))),
            context, code=code)
        for item in overload.items:
            self.note(pretty_callable(item), context, offset=4, code=code)

    def wrong_number_values_to_unpack(self, provided: int, expected: int,
                                      context: Context) -> None:
        if provided < expected:
            if provided == 1:
                self.fail(message_registry.UNPACK_MORE_THAN_ONE_VALUE_NEEDED.format(expected),
                          context)
            else:
                self.fail(message_registry.UNPACK_TOO_FEW_VALUES.format(
                    provided, expected), context)
        elif provided > expected:
            self.fail(message_registry.UNPACK_TOO_MANY_VALUES.format(
                expected, provided), context)

    def unpacking_strings_disallowed(self, context: Context) -> None:
        self.fail(message_registry.UNPACKING_STRINGS_DISALLOWED, context)

    def type_not_iterable(self, type: Type, context: Context) -> None:
        self.fail(message_registry.TYPE_NOT_ITERABLE.format(format_type(type)), context)

    def incompatible_operator_assignment(self, op: str,
                                         context: Context) -> None:
        self.fail(message_registry.INCOMPATIBLE_OPERATOR_ASSIGNMENT.format(op), context)

    def overload_signature_incompatible_with_supertype(
            self, name: str, name_in_super: str, supertype: str,
            context: Context) -> None:
        target = self.override_target(name, name_in_super, supertype)
        self.fail(message_registry.OVERLOAD_SIGNATURE_INCOMPATIBLE.format(
            name, target), context)

        note_template = 'Overload variants must be defined in the same order as they are in "{}"'
        self.note(note_template.format(supertype), context, code=codes.OVERRIDE)

    def signature_incompatible_with_supertype(
            self, name: str, name_in_super: str, supertype: str, context: Context,
            original: Optional[FunctionLike] = None,
            override: Optional[FunctionLike] = None) -> None:
        code = codes.OVERRIDE
        target = self.override_target(name, name_in_super, supertype)
        self.fail(message_registry.SIGNATURE_INCOMPATIBLE_WITH_SUPERTYPE.format(
            name, target), context)

        INCLUDE_DECORATOR = True  # Include @classmethod and @staticmethod decorators, if any
        ALLOW_DUPS = True  # Allow duplicate notes, needed when signatures are duplicates
        ALIGN_OFFSET = 1  # One space, to account for the difference between error and note
        OFFSET = 4  # Four spaces, so that notes will look like this:
        # error: Signature of "f" incompatible with supertype "A"
        # note:      Superclass:
        # note:          def f(self) -> str
        # note:      Subclass:
        # note:          def f(self, x: str) -> None
        if original is not None and isinstance(original, (CallableType, Overloaded)) \
                and override is not None and isinstance(override, (CallableType, Overloaded)):
            self.note('Superclass:', context, offset=ALIGN_OFFSET + OFFSET, code=code)
            self.pretty_callable_or_overload(original, context, offset=ALIGN_OFFSET + 2 * OFFSET,
                                            add_class_or_static_decorator=INCLUDE_DECORATOR,
                                            allow_dups=ALLOW_DUPS, code=code)

            self.note('Subclass:', context, offset=ALIGN_OFFSET + OFFSET, code=code)
            self.pretty_callable_or_overload(override, context, offset=ALIGN_OFFSET + 2 * OFFSET,
                                            add_class_or_static_decorator=INCLUDE_DECORATOR,
                                            allow_dups=ALLOW_DUPS, code=code)

    def pretty_callable_or_overload(self,
                                    tp: Union[CallableType, Overloaded],
                                    context: Context,
                                    *,
                                    offset: int = 0,
                                    add_class_or_static_decorator: bool = False,
                                    allow_dups: bool = False,
                                    code: Optional[ErrorCode] = None) -> None:
        if isinstance(tp, CallableType):
            if add_class_or_static_decorator:
                decorator = pretty_class_or_static_decorator(tp)
                if decorator is not None:
                    self.note(decorator, context, offset=offset, allow_dups=allow_dups, code=code)
            self.note(pretty_callable(tp), context,
                      offset=offset, allow_dups=allow_dups, code=code)
        elif isinstance(tp, Overloaded):
            self.pretty_overload(tp, context, offset,
                                 add_class_or_static_decorator=add_class_or_static_decorator,
                                 allow_dups=allow_dups, code=code)

    def argument_incompatible_with_supertype(
            self, arg_num: int, name: str, type_name: Optional[str],
            name_in_supertype: str, arg_type_in_supertype: Type, supertype: str,
            context: Context) -> None:
        target = self.override_target(name, name_in_supertype, supertype)
        arg_type_in_supertype_f = format_type_bare(arg_type_in_supertype)
        self.fail(message_registry.ARG_INCOMPATIBLE_WITH_SUPERTYPE
                  .format(arg_num, name, target, arg_type_in_supertype_f),
                  context)
        self.note(
            'This violates the Liskov substitution principle',
            context,
            code=codes.OVERRIDE)
        self.note(
            'See https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides',
            context,
            code=codes.OVERRIDE)

        if name == "__eq__" and type_name:
            multiline_msg = self.comparison_method_example_msg(class_name=type_name)
            self.note_multiline(multiline_msg, context, code=codes.OVERRIDE)

    def comparison_method_example_msg(self, class_name: str) -> str:
        return dedent('''\
        It is recommended for "__eq__" to work with arbitrary objects, for example:
            def __eq__(self, other: object) -> bool:
                if not isinstance(other, {class_name}):
                    return NotImplemented
                return <logic to compare two {class_name} instances>
        '''.format(class_name=class_name))

    def return_type_incompatible_with_supertype(
            self, name: str, name_in_supertype: str, supertype: str,
            original: Type, override: Type,
            context: Context) -> None:
        target = self.override_target(name, name_in_supertype, supertype)
        override_str, original_str = format_type_distinctly(override, original)
        self.fail(message_registry.RETURNTYPE_INCOMPATIBLE_WITH_SUPERTYPE
                  .format(override_str, name, original_str, target),
                  context)

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
            self.fail(message_registry.TYPE_APPLICATION_ON_NON_GENERIC_TYPE,
                      context)
        elif actual_arg_count > expected_arg_count:
            self.fail(message_registry.TYPE_APPLICATION_TOO_MANY_TYPES
                      .format(expected_arg_count), context)
        else:
            self.fail(message_registry.TYPE_APPLICATION_TOO_FEW_TYPES
                      .format(expected_arg_count), context)

    def could_not_infer_type_arguments(self, callee_type: CallableType, n: int,
                                       context: Context) -> None:
        callee_name = callable_name(callee_type)
        if callee_name is not None and n > 0:
            self.fail(message_registry.CANNOT_INFER_TYPE_ARG_NAMED_FUNC.format(n, callee_name),
                      context)
        else:
            self.fail(message_registry.CANNOT_INFER_TYPE_ARG_FUNC, context)

    def invalid_var_arg(self, typ: Type, context: Context) -> None:
        self.fail(message_registry.INVALID_VAR_ARGS, context)

    def invalid_keyword_var_arg(self, typ: Type, is_mapping: bool, context: Context) -> None:
        typ = get_proper_type(typ)
        if isinstance(typ, Instance) and is_mapping:
            self.fail(message_registry.KEYWORDS_MUST_BE_STRINGS, context)
        else:
            suffix = ''
            if isinstance(typ, Instance):
                suffix = ', not {}'.format(format_type(typ))
            self.fail(message_registry.ARG_MUST_BE_MAPPING.format(suffix), context)

    def undefined_in_superclass(self, member: str, context: Context) -> None:
        self.fail(message_registry.MEMBER_UNDEFINED_IN_SUPERCLASS.format(member), context)

    def first_argument_for_super_must_be_type(self, actual: Type, context: Context) -> None:
        actual = get_proper_type(actual)
        if isinstance(actual, Instance):
            # Don't include type of instance, because it can look confusingly like a type
            # object.
            type_str = 'a non-type instance'
        else:
            type_str = format_type(actual)
        self.fail(message_registry.SUPER_ARG_EXPECTED_TYPE.format(type_str), context)

    def too_few_string_formatting_arguments(self, context: Context) -> None:
        self.fail(message_registry.FORMAT_STR_TOO_FEW_ARGS, context)

    def too_many_string_formatting_arguments(self, context: Context) -> None:
        self.fail(message_registry.FORMAT_STR_TOO_MANY_ARGS, context)

    def unsupported_placeholder(self, placeholder: str, context: Context) -> None:
        self.fail(message_registry.FORMAT_STR_UNSUPPORTED_CHAR.format(placeholder), context)

    def string_interpolation_with_star_and_key(self, context: Context) -> None:
        self.fail(message_registry.STRING_INTERPOLATION_WITH_STAR_AND_KEY, context)

    def requires_int_or_single_byte(self, context: Context,
                                    format_call: bool = False) -> None:
        self.fail(message_registry.FORMAT_STR_INVALID_CHR_CONVERSION_RANGE
                  .format(':' if format_call else '%'),
                  context)

    def requires_int_or_char(self, context: Context,
                             format_call: bool = False) -> None:
        self.fail(message_registry.FORMAT_STR_INVALID_CHR_CONVERSION
                  .format(':' if format_call else '%'),
                  context)

    def key_not_in_mapping(self, key: str, context: Context) -> None:
        self.fail(message_registry.KEY_NOT_IN_MAPPING.format(key), context)

    def string_interpolation_mixing_key_and_non_keys(self, context: Context) -> None:
        self.fail(message_registry.FORMAT_STR_MIXED_KEYS_AND_NON_KEYS, context)

    def cannot_determine_type(self, name: str, context: Context) -> None:
        self.fail(message_registry.CANNOT_DETERMINE_TYPE.format(name), context)

    def cannot_determine_type_in_base(self, name: str, base: str, context: Context) -> None:
        self.fail(message_registry.CANNOT_DETERMINE_TYPE_IN_BASE.format(name, base), context)

    def no_formal_self(self, name: str, item: CallableType, context: Context) -> None:
        self.fail(message_registry.DOES_NOT_ACCEPT_SELF.format(name, format_type(item)), context)

    def incompatible_self_argument(self, name: str, arg: Type, sig: CallableType,
                                   is_classmethod: bool, context: Context) -> None:
        kind = 'class attribute function' if is_classmethod else 'attribute function'
        self.fail(message_registry.INCOMPATIBLE_SELF_ARG
                  .format(format_type(arg), kind, name, format_type(sig)), context)

    def incompatible_conditional_function_def(self, defn: FuncDef) -> None:
        self.fail(message_registry.INCOMPATIBLE_CONDITIONAL_FUNCS, defn)

    def cannot_instantiate_abstract_class(self, class_name: str,
                                          abstract_attributes: List[str],
                                          context: Context) -> None:
        attrs = format_string_list(['"%s"' % a for a in abstract_attributes])
        self.fail(message_registry.CANNOT_INSTANTIATE_ABSTRACT_CLASS
                  .format(class_name, plural_s(abstract_attributes), attrs),
                  context)

    def base_class_definitions_incompatible(self, name: str, base1: TypeInfo,
                                            base2: TypeInfo,
                                            context: Context) -> None:
        self.fail(message_registry.INCOMPATIBLE_BASE_CLASS_DEFNS.format(
                      name, base1.name, base2.name), context)

    def cant_assign_to_method(self, context: Context) -> None:
        self.fail(message_registry.CANNOT_ASSIGN_TO_METHOD, context)

    def cant_assign_to_classvar(self, name: str, context: Context) -> None:
        self.fail(message_registry.CANNOT_ASSIGN_TO_CLASSVAR.format(name), context)

    def final_cant_override_writable(self, name: str, ctx: Context) -> None:
        self.fail(message_registry.CANNOT_OVERRIDE_TO_FINAL.format(name), ctx)

    def cant_override_final(self, name: str, base_name: str, ctx: Context) -> None:
        self.fail(message_registry.CANNOT_OVERRIDE_FINAL.format(name, base_name), ctx)

    def cant_assign_to_final(self, name: str, attr_assign: bool, ctx: Context) -> None:
        """Warn about a prohibited assignment to a final attribute.

        Pass `attr_assign=True` if the assignment assigns to an attribute.
        """
        kind = "attribute" if attr_assign else "name"
        self.fail(message_registry.CANNOT_ASSIGN_TO_FINAL.format(kind, unmangle(name)), ctx)

    def protocol_members_cant_be_final(self, ctx: Context) -> None:
        self.fail(message_registry.PROTOCOL_MEMBER_CANNOT_BE_FINAL, ctx)

    def final_without_value(self, ctx: Context) -> None:
        self.fail(message_registry.FINAL_WITHOUT_VALUE, ctx)

    def read_only_property(self, name: str, type: TypeInfo,
                           context: Context) -> None:
        self.fail(message_registry.PROPERTY_IS_READ_ONLY.format(
            name, type.name), context)

    def incompatible_typevar_value(self,
                                   callee: CallableType,
                                   typ: Type,
                                   typevar_name: str,
                                   context: Context) -> None:
        self.fail(message_registry.INCOMPATIBLE_TYPEVAR_VALUE
                  .format(typevar_name, callable_name(callee) or 'function', format_type(typ)),
                  context)

    def dangerous_comparison(self, left: Type, right: Type, kind: str, ctx: Context) -> None:
        left_str = 'element' if kind == 'container' else 'left operand'
        right_str = 'container item' if kind == 'container' else 'right operand'
        message = message_registry.NON_OVERLAPPING_COMPARISON
        left_typ, right_typ = format_type_distinctly(left, right)
        self.fail(message.format(kind, left_str, left_typ, right_str, right_typ), ctx)

    def overload_inconsistently_applies_decorator(self, decorator: str, context: Context) -> None:
        self.fail(message_registry.OVERLOAD_INCONSISTENT_DECORATOR_USE.format(decorator), context)

    def overloaded_signatures_overlap(self, index1: int, index2: int, context: Context) -> None:
        self.fail(message_registry.OVERLOAD_INCOMPATIBLE_RETURN_TYPES.format(index1, index2),
                  context)

    def overloaded_signature_will_never_match(self, index1: int, index2: int,
                                              context: Context) -> None:
        self.fail(message_registry.OVERLOAD_SIGNATURE_WILL_NEVER_MATCH
                  .format(index1=index1, index2=index2),
                  context)

    def overloaded_signatures_typevar_specific(self, index: int, context: Context) -> None:
        self.fail(message_registry.OVERLOAD_INCONSISTENT_TYPEVARS.format(index), context)

    def overloaded_signatures_arg_specific(self, index: int, context: Context) -> None:
        self.fail(message_registry.OVERLOAD_INCONSISTENT_ARGS.format(index), context)

    def overloaded_signatures_ret_specific(self, index: int, context: Context) -> None:
        self.fail(message_registry.OVERLOAD_INCONSISTENT_RETURN_TYPE.format(index), context)

    def warn_both_operands_are_from_unions(self, context: Context) -> None:
        self.note('Both left and right operands are unions', context, code=codes.OPERATOR)

    def warn_operand_was_from_union(self, side: str, original: Type, context: Context) -> None:
        self.note('{} operand is of type {}'.format(side, format_type(original)), context,
                  code=codes.OPERATOR)

    def operator_method_signatures_overlap(
            self, reverse_class: TypeInfo, reverse_method: str, forward_class: Type,
            forward_method: str, context: Context) -> None:
        self.fail(message_registry.OPERATOR_METHOD_SIGNATURE_OVERLAP.format(
                      reverse_method, reverse_class.name,
                      forward_method, format_type(forward_class)),
                  context)

    def forward_operator_not_callable(
            self, forward_method: str, context: Context) -> None:
        self.fail(message_registry.FORWARD_OPERATOR_NOT_CALLABLE.format(
            forward_method), context)

    def signatures_incompatible(self, method: str, other_method: str,
                                context: Context) -> None:
        self.fail(message_registry.INCOMPATIBLE_SIGNATURES.format(
            method, other_method), context)

    def yield_from_invalid_operand_type(self, expr: Type, context: Context) -> Type:
        text = format_type(expr) if format_type(expr) != 'object' else expr
        self.fail(message_registry.INVALID_YIELD_FROM.format(text), context)
        return AnyType(TypeOfAny.from_error)

    def invalid_signature(self, func_type: Type, context: Context) -> None:
        self.fail(message_registry.INVALID_SIGNATURE.format(format_type(func_type)), context)

    def invalid_signature_for_special_method(
            self, func_type: Type, context: Context, method_name: str) -> None:
        self.fail(message_registry.INVALID_SIGNATURE_SPECIAL.format(
            format_type(func_type), method_name), context)

    def reveal_type(self, typ: Type, context: Context) -> None:
        self.note('Revealed type is "{}"'.format(typ), context)

    def reveal_locals(self, type_map: Dict[str, Optional[Type]], context: Context) -> None:
        # To ensure that the output is predictable on Python < 3.6,
        # use an ordered dictionary sorted by variable name
        sorted_locals = OrderedDict(sorted(type_map.items(), key=lambda t: t[0]))
        self.note("Revealed local types are:", context)
        for line in ['    {}: {}'.format(k, v) for k, v in sorted_locals.items()]:
            self.note(line, context)

    def unsupported_type_type(self, item: Type, context: Context) -> None:
        self.fail(message_registry.UNSUPPORTED_TYPE_TYPE.format(format_type_bare(item)), context)

    def redundant_cast(self, typ: Type, context: Context) -> None:
        self.fail(message_registry.REDUNDANT_CAST.format(format_type(typ)), context)

    def unimported_type_becomes_any(self, prefix: str, typ: Type, ctx: Context) -> None:
        self.fail(message_registry.UNFOLLOWED_IMPORT.format(prefix, format_type(typ)), ctx)

    def need_annotation_for_var(self, node: SymbolNode, context: Context,
                                python_version: Optional[Tuple[int, int]] = None) -> None:
        hint = ''
        has_variable_annotations = not python_version or python_version >= (3, 6)
        # Only gives hint if it's a variable declaration and the partial type is a builtin type
        if (python_version and isinstance(node, Var) and isinstance(node.type, PartialType) and
                node.type.type and node.type.type.fullname in reverse_builtin_aliases):
            alias = reverse_builtin_aliases[node.type.type.fullname]
            alias = alias.split('.')[-1]
            type_dec = '<type>'
            if alias == 'Dict':
                type_dec = '{}, {}'.format(type_dec, type_dec)
            if has_variable_annotations:
                hint = ' (hint: "{}: {}[{}] = ...")'.format(node.name, alias, type_dec)
            else:
                hint = ' (hint: "{} = ...  # type: {}[{}]")'.format(node.name, alias, type_dec)

        if has_variable_annotations:
            needed = 'annotation'
        else:
            needed = 'comment'

        self.fail(message_registry.ANNOTATION_NEEDED.format(needed, unmangle(node.name), hint),
                  context)

    def explicit_any(self, ctx: Context) -> None:
        self.fail(message_registry.NO_EXPLICIT_ANY, ctx)

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
                self.fail(message_registry.TYPEDDICT_MISSING_KEYS.format(
                    format_key_list(missing, short=True), format_type(typ)),
                    context)
                return
            else:
                extra = [key for key in actual_keys if key not in expected_set]
                if extra:
                    # If there are both extra and missing keys, only report extra ones for
                    # simplicity.
                    self.fail(message_registry.TYPEDDICT_EXTRA_KEYS.format(
                        format_key_list(extra, short=True), format_type(typ)),
                        context)
                    return
        found = format_key_list(actual_keys, short=True)
        if not expected_keys:
            self.fail(message_registry.TYPEDDICT_UNEXPECTED_KEYS.format(found), context)
            return
        expected = format_key_list(expected_keys)
        if actual_keys and actual_set < expected_set:
            found = 'only {}'.format(found)
        self.fail(message_registry.TYPEDDICT_KEYS_MISMATCH.format(expected, found), context)

    def typeddict_key_must_be_string_literal(
            self,
            typ: TypedDictType,
            context: Context) -> None:
        self.fail(message_registry.TYPEDDICT_KEY_STRING_LITERAL_EXPECTED.format(
                format_item_name_list(typ.items.keys())), context)

    def typeddict_key_not_found(
            self,
            typ: TypedDictType,
            item_name: str,
            context: Context) -> None:
        if typ.is_anonymous():
            self.fail(message_registry.TYPEDDICT_KEY_INVALID.format(
                item_name, format_item_name_list(typ.items.keys())), context)
        else:
            self.fail(message_registry.TYPEDDICT_UNKNOWN_KEY.format(
                format_type(typ), item_name), context)
            matches = best_matches(item_name, typ.items.keys())
            if matches:
                self.note("Did you mean {}?".format(
                    pretty_seq(matches[:3], "or")), context)

    def typeddict_context_ambiguous(
            self,
            types: List[TypedDictType],
            context: Context) -> None:
        formatted_types = ', '.join(list(format_type_distinctly(*types)))
        self.fail(message_registry.TYPEDDICT_AMBIGUOUS_TYPE.format(
                  formatted_types), context)

    def typeddict_key_cannot_be_deleted(
            self,
            typ: TypedDictType,
            item_name: str,
            context: Context) -> None:
        if typ.is_anonymous():
            self.fail(message_registry.TYPEDDICT_CANNOT_DELETE_KEY.format(item_name),
                      context)
        else:
            self.fail(message_registry.TYPEDDICT_NAMED_CANNOT_DELETE_KEY.format(
                item_name, format_type(typ)), context)

    def typeddict_setdefault_arguments_inconsistent(
            self,
            default: Type,
            expected: Type,
            context: Context) -> None:
        msg = message_registry.TYPEDDICT_INCONSISTENT_SETDEFAULT_ARGS
        self.fail(msg.format(format_type(default), format_type(expected)), context)

    def type_arguments_not_allowed(self, context: Context) -> None:
        self.fail(message_registry.PARAMETERIZED_GENERICS_DISALLOWED, context)

    def disallowed_any_type(self, typ: Type, context: Context) -> None:
        typ = get_proper_type(typ)
        if isinstance(typ, AnyType):
            message = message_registry.EXPR_HAS_ANY_TYPE
        else:
            message = message_registry.EXPR_CONTAINS_ANY_TYPE.format(format_type(typ))
        self.fail(message, context)

    def incorrectly_returning_any(self, typ: Type, context: Context) -> None:
        message = message_registry.INCORRECTLY_RETURNING_ANY.format(format_type(typ))
        self.fail(message, context)

    def incorrect__exit__return(self, context: Context) -> None:
        self.fail(message_registry.INVALID_EXIT_RETURN_TYPE, context)
        self.note(
            'Use "typing_extensions.Literal[False]" as the return type or change it to "None"',
            context, code=codes.EXIT_RETURN)
        self.note(
            'If return type of "__exit__" implies that it may return True, '
            'the context manager may swallow exceptions',
            context, code=codes.EXIT_RETURN)

    def untyped_decorated_function(self, typ: Type, context: Context) -> None:
        typ = get_proper_type(typ)
        if isinstance(typ, AnyType):
            self.fail(message_registry.UNTYPED_DECORATOR_FUNCTION, context)
        else:
            self.fail(message_registry.DECORATED_TYPE_CONTAINS_ANY.format(
                format_type(typ)), context)

    def typed_function_untyped_decorator(self, func_name: str, context: Context) -> None:
        self.fail(message_registry.DECORATOR_MAKES_FUNCTION_UNTYPED.format(func_name), context)

    def bad_proto_variance(self, actual: int, tvar_name: str, expected: int,
                           context: Context) -> None:
        msg = capitalize('{} type variable "{}" used in protocol where'
                         ' {} one is expected'.format(variance_string(actual),
                                                      tvar_name,
                                                      variance_string(expected)))
        self.fail(ErrorMessage(msg), context)

    def concrete_only_assign(self, typ: Type, context: Context) -> None:
        self.fail(message_registry.CONCRETE_ONLY_ASSIGN.format(format_type(typ)), context)

    def concrete_only_call(self, typ: Type, context: Context) -> None:
        self.fail(message_registry.EXPECTED_CONCRETE_CLASS
                  .format(format_type(typ)), context)

    def cannot_use_function_with_type(
            self, method_name: str, type_name: str, context: Context) -> None:
        self.fail(message_registry.CANNOT_USE_FUNCTION_WITH_TYPE.format(method_name, type_name),
                  context)

    def report_non_method_protocol(self, tp: TypeInfo, members: List[str],
                                   context: Context) -> None:
        self.fail(message_registry.ISSUBCLASS_ONLY_NON_METHOD_PROTOCOL, context)
        if len(members) < 3:
            attrs = ', '.join(members)
            self.note('Protocol "{}" has non-method member(s): {}'
                      .format(tp.name, attrs), context)

    def note_call(self,
                  subtype: Type,
                  call: Type,
                  context: Context,
                  *,
                  code: Optional[ErrorCode]) -> None:
        self.note('"{}.__call__" has type {}'.format(format_type_bare(subtype),
                                                     format_type(call, verbosity=1)),
                  context, code=code)

    def unreachable_statement(self, context: Context) -> None:
        self.fail(message_registry.UNREACHABLE_STATEMENT, context)

    def redundant_left_operand(self, op_name: str, context: Context) -> None:
        """Indicates that the left operand of a boolean expression is redundant:
        it does not change the truth value of the entire condition as a whole.
        'op_name' should either be the string "and" or the string "or".
        """
        self.redundant_expr('Left operand of "{}"'.format(op_name), op_name == 'and', context)

    def unreachable_right_operand(self, op_name: str, context: Context) -> None:
        """Indicates that the right operand of a boolean expression is redundant:
        it does not change the truth value of the entire condition as a whole.
        'op_name' should either be the string "and" or the string "or".
        """
        self.fail(message_registry.UNREACHABLE_RIGHT_OPERAND.format(op_name), context)

    def redundant_condition_in_comprehension(self, truthiness: bool, context: Context) -> None:
        self.redundant_expr("If condition in comprehension", truthiness, context)

    def redundant_condition_in_if(self, truthiness: bool, context: Context) -> None:
        self.redundant_expr("If condition", truthiness, context)

    def redundant_expr(self, description: str, truthiness: bool, context: Context) -> None:
        self.fail(message_registry.EXPR_IS_ALWAYS_BOOL
                  .format(description, str(truthiness).lower()),
                  context)

    def impossible_intersection(self,
                                formatted_base_class_list: str,
                                reason: str,
                                context: Context,
                                ) -> None:
        self.fail(message_registry.IMPOSSIBLE_SUBCLASS
                  .format(formatted_base_class_list, reason),
                  context)

    def report_protocol_problems(self,
                                 subtype: Union[Instance, TupleType, TypedDictType],
                                 supertype: Instance,
                                 context: Context,
                                 *,
                                 code: Optional[ErrorCode]) -> None:
        """Report possible protocol conflicts between 'subtype' and 'supertype'.

        This includes missing members, incompatible types, and incompatible
        attribute flags, such as settable vs read-only or class variable vs
        instance variable.
        """
        OFFSET = 4  # Four spaces, so that notes will look like this:
        # note: 'Cls' is missing following 'Proto' members:
        # note:     method, attr
        MAX_ITEMS = 2  # Maximum number of conflicts, missing members, and overloads shown
        # List of special situations where we don't want to report additional problems
        exclusions: Dict[type, List[str]] = {
            TypedDictType: ["typing.Mapping"],
            TupleType: ["typing.Iterable", "typing.Sequence"],
            Instance: [],
        }
        if supertype.type.fullname in exclusions[type(subtype)]:
            return
        if any(isinstance(tp, UninhabitedType) for tp in get_proper_types(supertype.args)):
            # We don't want to add notes for failed inference (e.g. Iterable[<nothing>]).
            # This will be only confusing a user even more.
            return

        if isinstance(subtype, TupleType):
            if not isinstance(subtype.partial_fallback, Instance):
                return
            subtype = subtype.partial_fallback
        elif isinstance(subtype, TypedDictType):
            if not isinstance(subtype.fallback, Instance):
                return
            subtype = subtype.fallback

        # Report missing members
        missing = get_missing_protocol_members(subtype, supertype)
        if (missing and len(missing) < len(supertype.type.protocol_members) and
                len(missing) <= MAX_ITEMS):
            self.note('"{}" is missing following "{}" protocol member{}:'
                      .format(subtype.type.name, supertype.type.name, plural_s(missing)),
                      context,
                      code=code)
            self.note(', '.join(missing), context, offset=OFFSET, code=code)
        elif len(missing) > MAX_ITEMS or len(missing) == len(supertype.type.protocol_members):
            # This is an obviously wrong type: too many missing members
            return

        # Report member type conflicts
        conflict_types = get_conflict_protocol_types(subtype, supertype)
        if conflict_types and (not is_subtype(subtype, erase_type(supertype)) or
                               not subtype.type.defn.type_vars or
                               not supertype.type.defn.type_vars):
            self.note('Following member(s) of {} have '
                      'conflicts:'.format(format_type(subtype)),
                      context,
                      code=code)
            for name, got, exp in conflict_types[:MAX_ITEMS]:
                exp = get_proper_type(exp)
                got = get_proper_type(got)
                if (not isinstance(exp, (CallableType, Overloaded)) or
                        not isinstance(got, (CallableType, Overloaded))):
                    self.note('{}: expected {}, got {}'.format(name,
                                                               *format_type_distinctly(exp, got)),
                              context,
                              offset=OFFSET,
                              code=code)
                else:
                    self.note('Expected:', context, offset=OFFSET, code=code)
                    if isinstance(exp, CallableType):
                        self.note(pretty_callable(exp), context, offset=2 * OFFSET, code=code)
                    else:
                        assert isinstance(exp, Overloaded)
                        self.pretty_overload(exp, context, 2 * OFFSET, code=code)
                    self.note('Got:', context, offset=OFFSET, code=code)
                    if isinstance(got, CallableType):
                        self.note(pretty_callable(got), context, offset=2 * OFFSET, code=code)
                    else:
                        assert isinstance(got, Overloaded)
                        self.pretty_overload(got, context, 2 * OFFSET, code=code)
            self.print_more(conflict_types, context, OFFSET, MAX_ITEMS, code=code)

        # Report flag conflicts (i.e. settable vs read-only etc.)
        conflict_flags = get_bad_protocol_flags(subtype, supertype)
        for name, subflags, superflags in conflict_flags[:MAX_ITEMS]:
            if IS_CLASSVAR in subflags and IS_CLASSVAR not in superflags:
                self.note('Protocol member {}.{} expected instance variable,'
                          ' got class variable'.format(supertype.type.name, name),
                          context,
                          code=code)
            if IS_CLASSVAR in superflags and IS_CLASSVAR not in subflags:
                self.note('Protocol member {}.{} expected class variable,'
                          ' got instance variable'.format(supertype.type.name, name),
                          context,
                          code=code)
            if IS_SETTABLE in superflags and IS_SETTABLE not in subflags:
                self.note('Protocol member {}.{} expected settable variable,'
                          ' got read-only attribute'.format(supertype.type.name, name),
                          context,
                          code=code)
            if IS_CLASS_OR_STATIC in superflags and IS_CLASS_OR_STATIC not in subflags:
                self.note('Protocol member {}.{} expected class or static method'
                          .format(supertype.type.name, name),
                          context,
                          code=code)
        self.print_more(conflict_flags, context, OFFSET, MAX_ITEMS, code=code)

    def pretty_overload(self,
                        tp: Overloaded,
                        context: Context,
                        offset: int,
                        *,
                        add_class_or_static_decorator: bool = False,
                        allow_dups: bool = False,
                        code: Optional[ErrorCode] = None) -> None:
        for item in tp.items:
            self.note('@overload', context, offset=offset, allow_dups=allow_dups, code=code)

            if add_class_or_static_decorator:
                decorator = pretty_class_or_static_decorator(item)
                if decorator is not None:
                    self.note(decorator, context, offset=offset, allow_dups=allow_dups, code=code)

            self.note(pretty_callable(item), context,
                      offset=offset, allow_dups=allow_dups, code=code)

    def print_more(self,
                   conflicts: Sequence[Any],
                   context: Context,
                   offset: int,
                   max_items: int,
                   *,
                   code: Optional[ErrorCode] = None) -> None:
        if len(conflicts) > max_items:
            self.note('<{} more conflict(s) not shown>'
                      .format(len(conflicts) - max_items),
                      context, offset=offset, code=code)

    def try_report_long_tuple_assignment_error(self,
                                               subtype: ProperType,
                                               supertype: ProperType,
                                               context: Context,
                                               msg: str = message_registry.INCOMPATIBLE_TYPES,
                                               subtype_label: Optional[str] = None,
                                               supertype_label: Optional[str] = None,
                                               code: Optional[ErrorCode] = None) -> bool:
        """Try to generate meaningful error message for very long tuple assignment

        Returns a bool: True when generating long tuple assignment error,
        False when no such error reported
        """
        if isinstance(subtype, TupleType):
            if (len(subtype.items) > 10 and
                isinstance(supertype, Instance) and
                    supertype.type.fullname == 'builtins.tuple'):
                lhs_type = supertype.args[0]
                lhs_types = [lhs_type] * len(subtype.items)
                self.generate_incompatible_tuple_error(lhs_types,
                                    subtype.items, context, msg, code)
                return True
            elif (isinstance(supertype, TupleType) and
                    (len(subtype.items) > 10 or len(supertype.items) > 10)):
                if len(subtype.items) != len(supertype.items):
                    if supertype_label is not None and subtype_label is not None:
                        error_msg = "{} ({} {}, {} {})".format(msg, subtype_label,
                                        self.format_long_tuple_type(subtype), supertype_label,
                                        self.format_long_tuple_type(supertype))
                        self.fail(ErrorMessage(error_msg, code), context)
                        return True
                self.generate_incompatible_tuple_error(supertype.items,
                                    subtype.items, context, msg, code)
                return True
        return False

    def format_long_tuple_type(self, typ: TupleType) -> str:
        """Format very long tuple type using an ellipsis notation"""
        item_cnt = len(typ.items)
        if item_cnt > 10:
            return 'Tuple[{}, {}, ... <{} more items>]'\
                    .format(format_type_bare(typ.items[0]),
                        format_type_bare(typ.items[1]), str(item_cnt - 2))
        else:
            return format_type_bare(typ)

    def generate_incompatible_tuple_error(self,
                                          lhs_types: List[Type],
                                          rhs_types: List[Type],
                                          context: Context,
                                          msg: str = message_registry.INCOMPATIBLE_TYPES,
                                          code: Optional[ErrorCode] = None) -> None:
        """Generate error message for individual incompatible tuple pairs"""
        error_cnt = 0
        notes = []  # List[str]
        for i, (lhs_t, rhs_t) in enumerate(zip(lhs_types, rhs_types)):
            if not is_subtype(lhs_t, rhs_t):
                if error_cnt < 3:
                    notes.append('Expression tuple item {} has type {}; {} expected; '
                        .format(str(i), format_type(rhs_t), format_type(lhs_t)))
                error_cnt += 1

        error_msg = msg + ' ({} tuple items are incompatible'.format(str(error_cnt))
        if error_cnt - 3 > 0:
            error_msg += '; {} items are omitted)'.format(str(error_cnt - 3))
        else:
            error_msg += ')'
        self.fail(ErrorMessage(error_msg, code), context)
        for note in notes:
            self.note(note, context, code=code)

    def add_fixture_note(self, fullname: str, ctx: Context) -> None:
        self.note('Maybe your test fixture does not define "{}"?'.format(fullname), ctx)
        if fullname in SUGGESTED_TEST_FIXTURES:
            self.note(
                'Consider adding [builtins fixtures/{}] to your test description'.format(
                    SUGGESTED_TEST_FIXTURES[fullname]), ctx)


def quote_type_string(type_string: str) -> str:
    """Quotes a type representation for use in messages."""
    no_quote_regex = r'^<(tuple|union): \d+ items>$'
    if (type_string in ['Module', 'overloaded function', '<nothing>', '<deleted>']
            or re.match(no_quote_regex, type_string) is not None or type_string.endswith('?')):
        # Messages are easier to read if these aren't quoted.  We use a
        # regex to match strings with variable contents.
        return type_string
    return '"{}"'.format(type_string)


def format_type_inner(typ: Type,
                      verbosity: int,
                      fullnames: Optional[Set[str]]) -> str:
    """
    Convert a type to a relatively short string suitable for error messages.

    Args:
      verbosity: a coarse grained control on the verbosity of the type
      fullnames: a set of names that should be printed in full
    """
    def format(typ: Type) -> str:
        return format_type_inner(typ, verbosity, fullnames)

    # TODO: show type alias names in errors.
    typ = get_proper_type(typ)

    if isinstance(typ, Instance):
        itype = typ
        # Get the short name of the type.
        if itype.type.fullname in ('types.ModuleType', '_importlib_modulespec.ModuleType'):
            # Make some common error messages simpler and tidier.
            return 'Module'
        if verbosity >= 2 or (fullnames and itype.type.fullname in fullnames):
            base_str = itype.type.fullname
        else:
            base_str = itype.type.name
        if not itype.args:
            # No type arguments, just return the type name
            return base_str
        elif itype.type.fullname == 'builtins.tuple':
            item_type_str = format(itype.args[0])
            return 'Tuple[{}, ...]'.format(item_type_str)
        elif itype.type.fullname in reverse_builtin_aliases:
            alias = reverse_builtin_aliases[itype.type.fullname]
            alias = alias.split('.')[-1]
            items = [format(arg) for arg in itype.args]
            return '{}[{}]'.format(alias, ', '.join(items))
        else:
            # There are type arguments. Convert the arguments to strings.
            a: List[str] = []
            for arg in itype.args:
                a.append(format(arg))
            s = ', '.join(a)
            return '{}[{}]'.format(base_str, s)
    elif isinstance(typ, TypeVarType):
        # This is similar to non-generic instance types.
        return typ.name
    elif isinstance(typ, ParamSpecType):
        return typ.name_with_suffix()
    elif isinstance(typ, TupleType):
        # Prefer the name of the fallback class (if not tuple), as it's more informative.
        if typ.partial_fallback.type.fullname != 'builtins.tuple':
            return format(typ.partial_fallback)
        items = []
        for t in typ.items:
            items.append(format(t))
        s = 'Tuple[{}]'.format(', '.join(items))
        return s
    elif isinstance(typ, TypedDictType):
        # If the TypedDictType is named, return the name
        if not typ.is_anonymous():
            return format(typ.fallback)
        items = []
        for (item_name, item_type) in typ.items.items():
            modifier = '' if item_name in typ.required_keys else '?'
            items.append('{!r}{}: {}'.format(item_name,
                                             modifier,
                                             format(item_type)))
        s = 'TypedDict({{{}}})'.format(', '.join(items))
        return s
    elif isinstance(typ, LiteralType):
        if typ.is_enum_literal():
            underlying_type = format(typ.fallback)
            return 'Literal[{}.{}]'.format(underlying_type, typ.value)
        else:
            return str(typ)
    elif isinstance(typ, UnionType):
        # Only print Unions as Optionals if the Optional wouldn't have to contain another Union
        print_as_optional = (len(typ.items) -
                             sum(isinstance(get_proper_type(t), NoneType)
                                 for t in typ.items) == 1)
        if print_as_optional:
            rest = [t for t in typ.items if not isinstance(get_proper_type(t), NoneType)]
            return 'Optional[{}]'.format(format(rest[0]))
        else:
            items = []
            for t in typ.items:
                items.append(format(t))
            s = 'Union[{}]'.format(', '.join(items))
            return s
    elif isinstance(typ, NoneType):
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
        return 'Type[{}]'.format(format(typ.item))
    elif isinstance(typ, FunctionLike):
        func = typ
        if func.is_type_obj():
            # The type of a type object type can be derived from the
            # return type (this always works).
            return format(TypeType.make_normalized(erase_type(func.items[0].ret_type)))
        elif isinstance(func, CallableType):
            if func.type_guard is not None:
                return_type = f'TypeGuard[{format(func.type_guard)}]'
            else:
                return_type = format(func.ret_type)
            if func.is_ellipsis_args:
                return 'Callable[..., {}]'.format(return_type)
            param_spec = func.param_spec()
            if param_spec is not None:
                return f'Callable[{param_spec.name}, {return_type}]'
            arg_strings = []
            for arg_name, arg_type, arg_kind in zip(
                    func.arg_names, func.arg_types, func.arg_kinds):
                if (arg_kind == ARG_POS and arg_name is None
                        or verbosity == 0 and arg_kind.is_positional()):

                    arg_strings.append(format(arg_type))
                else:
                    constructor = ARG_CONSTRUCTOR_NAMES[arg_kind]
                    if arg_kind.is_star() or arg_name is None:
                        arg_strings.append("{}({})".format(
                            constructor,
                            format(arg_type)))
                    else:
                        arg_strings.append("{}({}, {})".format(
                            constructor,
                            format(arg_type),
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


def collect_all_instances(t: Type) -> List[Instance]:
    """Return all instances that `t` contains (including `t`).

    This is similar to collect_all_inner_types from typeanal but only
    returns instances and will recurse into fallbacks.
    """
    visitor = CollectAllInstancesQuery()
    t.accept(visitor)
    return visitor.instances


class CollectAllInstancesQuery(TypeTraverserVisitor):
    def __init__(self) -> None:
        self.instances: List[Instance] = []

    def visit_instance(self, t: Instance) -> None:
        self.instances.append(t)
        super().visit_instance(t)


def find_type_overlaps(*types: Type) -> Set[str]:
    """Return a set of fullnames that share a short name and appear in either type.

    This is used to ensure that distinct types with the same short name are printed
    with their fullname.
    """
    d: Dict[str, Set[str]] = {}
    for type in types:
        for inst in collect_all_instances(type):
            d.setdefault(inst.type.name, set()).add(inst.type.fullname)
    for shortname in d.keys():
        if 'typing.{}'.format(shortname) in TYPES_FOR_UNIMPORTED_HINTS:
            d[shortname].add('typing.{}'.format(shortname))

    overlaps: Set[str] = set()
    for fullnames in d.values():
        if len(fullnames) > 1:
            overlaps.update(fullnames)
    return overlaps


def format_type(typ: Type, verbosity: int = 0) -> str:
    """
    Convert a type to a relatively short string suitable for error messages.

    `verbosity` is a coarse grained control on the verbosity of the type

    This function returns a string appropriate for unmodified use in error
    messages; this means that it will be quoted in most cases.  If
    modification of the formatted string is required, callers should use
    format_type_bare.
    """
    return quote_type_string(format_type_bare(typ, verbosity))


def format_type_bare(typ: Type,
                     verbosity: int = 0) -> str:
    """
    Convert a type to a relatively short string suitable for error messages.

    `verbosity` is a coarse grained control on the verbosity of the type
    `fullnames` specifies a set of names that should be printed in full

    This function will return an unquoted string.  If a caller doesn't need to
    perform post-processing on the string output, format_type should be used
    instead.  (The caller may want to use quote_type_string after
    processing has happened, to maintain consistent quoting in messages.)
    """
    return format_type_inner(typ, verbosity, find_type_overlaps(typ))


def format_type_distinctly(*types: Type, bare: bool = False) -> Tuple[str, ...]:
    """Jointly format types to distinct strings.

    Increase the verbosity of the type strings until they become distinct
    while also requiring that distinct types with the same short name are
    formatted distinctly.

    By default, the returned strings are created using format_type() and will be
    quoted accordingly. If ``bare`` is True, the returned strings will not
    be quoted; callers who need to do post-processing of the strings before
    quoting them (such as prepending * or **) should use this.
    """
    overlapping = find_type_overlaps(*types)
    for verbosity in range(2):
        strs = [
            format_type_inner(type, verbosity=verbosity, fullnames=overlapping)
            for type in types
        ]
        if len(set(strs)) == len(strs):
            break
    if bare:
        return tuple(strs)
    else:
        return tuple(quote_type_string(s) for s in strs)


def pretty_class_or_static_decorator(tp: CallableType) -> Optional[str]:
    """Return @classmethod or @staticmethod, if any, for the given callable type."""
    if tp.definition is not None and isinstance(tp.definition, SYMBOL_FUNCBASE_TYPES):
        if tp.definition.is_class:
            return '@classmethod'
        if tp.definition.is_static:
            return '@staticmethod'
    return None


def pretty_callable(tp: CallableType) -> str:
    """Return a nice easily-readable representation of a callable type.
    For example:
        def [T <: int] f(self, x: int, y: T) -> None
    """
    s = ''
    asterisk = False
    for i in range(len(tp.arg_types)):
        if s:
            s += ', '
        if tp.arg_kinds[i].is_named() and not asterisk:
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
        s += format_type_bare(tp.arg_types[i])
        if tp.arg_kinds[i].is_optional():
            s += ' = ...'

    # If we got a "special arg" (i.e: self, cls, etc...), prepend it to the arg list
    if isinstance(tp.definition, FuncDef) and tp.definition.name is not None:
        definition_args = [arg.variable.name for arg in tp.definition.arguments]
        if definition_args and tp.arg_names != definition_args \
                and len(definition_args) > 0 and definition_args[0]:
            if s:
                s = ', ' + s
            s = definition_args[0] + s
        s = '{}({})'.format(tp.definition.name, s)
    elif tp.name:
        first_arg = tp.def_extras.get('first_arg')
        if first_arg:
            if s:
                s = ', ' + s
            s = first_arg + s
        s = '{}({})'.format(tp.name.split()[0], s)  # skip "of Class" part
    else:
        s = '({})'.format(s)

    s += ' -> '
    if tp.type_guard is not None:
        s += 'TypeGuard[{}]'.format(format_type_bare(tp.type_guard))
    else:
        s += format_type_bare(tp.ret_type)

    if tp.variables:
        tvars = []
        for tvar in tp.variables:
            if isinstance(tvar, TypeVarType):
                upper_bound = get_proper_type(tvar.upper_bound)
                if (isinstance(upper_bound, Instance) and
                        upper_bound.type.fullname != 'builtins.object'):
                    tvars.append('{} <: {}'.format(tvar.name, format_type_bare(upper_bound)))
                elif tvar.values:
                    tvars.append('{} in ({})'
                                 .format(tvar.name, ', '.join([format_type_bare(tp)
                                                               for tp in tvar.values])))
                else:
                    tvars.append(tvar.name)
            else:
                # For other TypeVarLikeTypes, just use the repr
                tvars.append(repr(tvar))
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
    assert right.type.is_protocol
    missing: List[str] = []
    for member in right.type.protocol_members:
        if not find_member(member, left, left):
            missing.append(member)
    return missing


def get_conflict_protocol_types(left: Instance, right: Instance) -> List[Tuple[str, Type, Type]]:
    """Find members that are defined in 'left' but have incompatible types.
    Return them as a list of ('member', 'got', 'expected').
    """
    assert right.type.is_protocol
    conflicts: List[Tuple[str, Type, Type]] = []
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
    assert right.type.is_protocol
    all_flags: List[Tuple[str, Set[int], Set[int]]] = []
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


def plural_s(s: Union[int, Sequence[Any]]) -> str:
    count = s if isinstance(s, int) else len(s)
    if count > 1:
        return 's'
    else:
        return ''


def format_string_list(lst: List[str]) -> str:
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
        return '(' + ', '.join(['"%s"' % name for name in lst]) + ')'
    else:
        return '(' + ', '.join(['"%s"' % name for name in lst[:5]]) + ', ...)'


def callable_name(type: FunctionLike) -> Optional[str]:
    name = type.get_name()
    if name is not None and name[0] != '<':
        return '"{}"'.format(name).replace(' of ', '" of "')
    return name


def for_function(callee: CallableType) -> str:
    name = callable_name(callee)
    if name is not None:
        return ' for {}'.format(name)
    return ''


def find_defining_module(modules: Dict[str, MypyFile], typ: CallableType) -> Optional[MypyFile]:
    if not typ.definition:
        return None
    fullname = typ.definition.fullname
    if fullname is not None and '.' in fullname:
        for i in range(fullname.count('.')):
            module_name = fullname.rsplit('.', i + 1)[0]
            try:
                return modules[module_name]
            except KeyError:
                pass
        assert False, "Couldn't determine module from CallableType"
    return None


# For hard-coding suggested missing member alternatives.
COMMON_MISTAKES: Final[Dict[str, Sequence[str]]] = {
    'add': ('append', 'extend'),
}


def best_matches(current: str, options: Iterable[str]) -> List[str]:
    ratios = {v: difflib.SequenceMatcher(a=current, b=v).ratio() for v in options}
    return sorted((o for o in options if ratios[o] > 0.75),
                  reverse=True, key=lambda v: (ratios[v], v))


def pretty_seq(args: Sequence[str], conjunction: str) -> str:
    quoted = ['"' + a + '"' for a in args]
    if len(quoted) == 1:
        return quoted[0]
    if len(quoted) == 2:
        return "{} {} {}".format(quoted[0], conjunction, quoted[1])
    last_sep = ", " + conjunction + " "
    return ", ".join(quoted[:-1]) + last_sep + quoted[-1]


def append_invariance_notes(notes: List[str], arg_type: Instance,
                            expected_type: Instance) -> List[str]:
    """Explain that the type is invariant and give notes for how to solve the issue."""
    invariant_type = ''
    covariant_suggestion = ''
    if (arg_type.type.fullname == 'builtins.list' and
            expected_type.type.fullname == 'builtins.list' and
            is_subtype(arg_type.args[0], expected_type.args[0])):
        invariant_type = 'List'
        covariant_suggestion = 'Consider using "Sequence" instead, which is covariant'
    elif (arg_type.type.fullname == 'builtins.dict' and
          expected_type.type.fullname == 'builtins.dict' and
          is_same_type(arg_type.args[0], expected_type.args[0]) and
          is_subtype(arg_type.args[1], expected_type.args[1])):
        invariant_type = 'Dict'
        covariant_suggestion = ('Consider using "Mapping" instead, '
                                'which is covariant in the value type')
    if invariant_type and covariant_suggestion:
        notes.append(
            '"{}" is invariant -- see '.format(invariant_type) +
            "https://mypy.readthedocs.io/en/stable/common_issues.html#variance")
        notes.append(covariant_suggestion)
    return notes


def make_inferred_type_note(context: Context,
                            subtype: Type,
                            supertype: Type,
                            supertype_str: str) -> str:
    """Explain that the user may have forgotten to type a variable.

    The user does not expect an error if the inferred container type is the same as the return
    type of a function and the argument type(s) are a subtype of the argument type(s) of the
    return type. This note suggests that they add a type annotation with the return type instead
    of relying on the inferred type.
    """
    subtype = get_proper_type(subtype)
    supertype = get_proper_type(supertype)
    if (isinstance(subtype, Instance) and
            isinstance(supertype, Instance) and
            subtype.type.fullname == supertype.type.fullname and
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
    formatted_keys = ['"{}"'.format(key) for key in keys]
    td = '' if short else 'TypedDict '
    if len(keys) == 0:
        return 'no {}keys'.format(td)
    elif len(keys) == 1:
        return '{}key {}'.format(td, formatted_keys[0])
    else:
        return '{}keys ({})'.format(td, ', '.join(formatted_keys))
