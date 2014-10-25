"""Facilities and constants for generating error messages during type checking.

The type checker itself does not deal with message string literals to
improve code clarity and to simplify localization (in the future)."""

import re

from typing import Undefined, cast, List, Any, Sequence, Iterable

from mypy.errors import Errors
from mypy.types import (
    Type, Callable, Instance, TypeVar, TupleType, UnionType, Void, NoneTyp, AnyType,
    Overloaded, FunctionLike
)
from mypy.nodes import (
    TypeInfo, Context, op_methods, FuncDef, reverse_type_aliases
)


# Constants that represent simple type checker error message, i.e. messages
# that do not have any parameters.

NO_RETURN_VALUE_EXPECTED = 'No return value expected'
INCOMPATIBLE_RETURN_VALUE_TYPE = 'Incompatible return value type'
RETURN_VALUE_EXPECTED = 'Return value expected'
BOOLEAN_VALUE_EXPECTED = 'Boolean value expected'
BOOLEAN_EXPECTED_FOR_IF = 'Boolean value expected for if condition'
BOOLEAN_EXPECTED_FOR_WHILE = 'Boolean value expected for while condition'
BOOLEAN_EXPECTED_FOR_UNTIL = 'Boolean value expected for until condition'
BOOLEAN_EXPECTED_FOR_NOT = 'Boolean value expected for not operand'
INVALID_EXCEPTION = 'Exception must be derived from BaseException'
INVALID_EXCEPTION_TYPE = 'Exception type must be derived from BaseException'
INVALID_RETURN_TYPE_FOR_YIELD = \
    'Iterator function return type expected for "yield"'
INCOMPATIBLE_TYPES = 'Incompatible types'
INCOMPATIBLE_TYPES_IN_ASSIGNMENT = 'Incompatible types in assignment'
INCOMPATIBLE_TYPES_IN_YIELD = 'Incompatible types in yield'
INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION = 'Incompatible types in string interpolation'
INIT_MUST_NOT_HAVE_RETURN_TYPE = 'Cannot define return type for "__init__"'
GETTER_TYPE_INCOMPATIBLE_WITH_SETTER = \
    'Type of getter incompatible with setter'
TUPLE_INDEX_MUST_BE_AN_INT_LITERAL = 'Tuple index must an integer literal'
TUPLE_INDEX_OUT_OF_RANGE = 'Tuple index out of range'
TYPE_CONSTANT_EXPECTED = 'Type "Constant" or initializer expected'
INCOMPATIBLE_PAIR_ITEM_TYPE = 'Incompatible Pair item type'
INVALID_TYPE_APPLICATION_TARGET_TYPE = 'Invalid type application target type'
INCOMPATIBLE_TUPLE_ITEM_TYPE = 'Incompatible tuple item type'
INCOMPATIBLE_KEY_TYPE = 'Incompatible dictionary key type'
INCOMPATIBLE_VALUE_TYPE = 'Incompatible dictionary value type'
NEED_ANNOTATION_FOR_VAR = 'Need type annotation for variable'
ITERABLE_EXPECTED = 'Iterable expected'
INCOMPATIBLE_TYPES_IN_FOR = 'Incompatible types in for statement'
INCOMPATIBLE_ARRAY_VAR_ARGS = 'Incompatible variable arguments in call'
INVALID_SLICE_INDEX = 'Slice index must be an integer or None'
CANNOT_INFER_LAMBDA_TYPE = 'Cannot infer type of lambda'
CANNOT_INFER_ITEM_TYPE = 'Cannot infer iterable item type'
CANNOT_ACCESS_INIT = 'Cannot access "__init__" directly'
CANNOT_ASSIGN_TO_METHOD = 'Cannot assign to a method'
CANNOT_ASSIGN_TO_TYPE = 'Cannot assign to a type'
INCONSISTENT_ABSTRACT_OVERLOAD = \
    'Overloaded method has both abstract and non-abstract variants'
INSTANCE_LAYOUT_CONFLICT = 'Instance layout conflict in multiple inheritance'
FORMAT_REQUIRES_MAPPING = 'Format requires a mapping'

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
    errors = Undefined(Errors)

    # Number of times errors have been disabled.
    disable_count = 0

    # Hack to deduplicate error messages from union types
    disable_type_names = 0

    def __init__(self, errors: Errors) -> None:
        self.errors = errors
        self.disable_count = 0
        self.disable_type_names = 0

    #
    # Helpers
    #

    def copy(self) -> 'MessageBuilder':
        new = MessageBuilder(self.errors.copy())
        new.disable_count = self.disable_count
        return new

    def add_errors(self, messages: 'MessageBuilder') -> None:
        """Add errors in messages to this builder."""
        self.errors.error_info.extend(messages.errors.error_info)

    def disable_errors(self) -> None:
        self.disable_count += 1

    def enable_errors(self) -> None:
        self.disable_count -= 1

    def is_errors(self) -> bool:
        return self.errors.is_errors()

    def fail(self, msg: str, context: Context) -> None:
        """Report an error message (unless disabled)."""
        if self.disable_count <= 0:
            self.errors.report(context.get_line(), msg.strip())

    def format(self, typ: Type) -> str:
        """Convert a type to a relatively short string that is
        suitable for error messages. Mostly behave like format_simple
        below, but never return an empty string.
        """
        s = self.format_simple(typ)
        if s != '':
            # If format_simple returns a non-trivial result, use that.
            return s
        elif isinstance(typ, FunctionLike):
            func = cast(FunctionLike, typ)
            if func.is_type_obj():
                # The type of a type object type can be derived from the
                # return type (this always works).
                itype = cast(Instance, func.items()[0].ret_type)
                return self.format(itype)
            elif isinstance(func, Callable):
                arg_types = map(self.format, func.arg_types)
                return_type = self.format(func.ret_type)
                return 'Function[[{}] -> {}]'.format(", ".join(arg_types), return_type)
            else:
                # Use a simple representation for function types; proper
                # function types may result in long and difficult-to-read
                # error messages.
                return 'functionlike'
        else:
            # Default case; we simply have to return something meaningful here.
            return 'object'

    def format_simple(self, typ: Type) -> str:
        """Convert simple types to string that is suitable for error messages.

        Return "" for complex types. Try to keep the length of the result
        relatively short to avoid overly long error messages.

        Examples:
          builtins.int -> 'int'
          Any type -> 'Any'
          void -> None
          function type -> "" (empty string)
        """
        if isinstance(typ, Instance):
            itype = cast(Instance, typ)
            # Get the short name of the type.
            base_str = itype.type.name()
            if itype.args == []:
                # No type arguments. Place the type name in quotes to avoid
                # potential for confusion: otherwise, the type name could be
                # interpreted as a normal word.
                return '"{}"'.format(base_str)
            elif itype.type.fullname() in reverse_type_aliases:
                alias = reverse_type_aliases[itype.type.fullname()]
                alias = alias.split('.')[-1]
                items = [strip_quotes(self.format(arg)) for arg in itype.args]
                return '{}[{}]'.format(alias, ', '.join(items))
            else:
                # There are type arguments. Convert the arguments to strings
                # (using format() instead of format_simple() to avoid empty
                # strings). If the result is too long, replace arguments
                # with [...].
                a = []  # type: List[str]
                for arg in itype.args:
                    a.append(strip_quotes(self.format(arg)))
                s = ', '.join(a)
                if len((base_str + s)) < 25:
                    return '{}[{}]'.format(base_str, s)
                else:
                    return '{}[...]'.format(base_str)
        elif isinstance(typ, TypeVar):
            # This is similar to non-generic instance types.
            return '"{}"'.format((cast(TypeVar, typ)).name)
        elif isinstance(typ, TupleType):
            items = []
            for t in (cast(TupleType, typ)).items:
                items.append(strip_quotes(self.format(t)))
            s = '"Tuple[{}]"'.format(', '.join(items))
            if len(s) < 40:
                return s
            else:
                return 'tuple(length {})'.format(len(items))
        elif isinstance(typ, UnionType):
            items = []
            for t in (cast(UnionType, typ)).items:
                items.append(strip_quotes(self.format(t)))
            s = '"Union[{}]"'.format(', '.join(items))
            if len(s) < 40:
                return s
            else:
                return 'union(length {})'.format(len(items))
        elif isinstance(typ, Void):
            return 'None'
        elif isinstance(typ, NoneTyp):
            return 'None'
        elif isinstance(typ, AnyType):
            return '"Any"'
        elif typ is None:
            raise RuntimeError('Type is None')
        else:
            # No simple representation for this type that would convey very
            # useful information. No need to mention the type explicitly in a
            # message.
            return ''

    #
    # Specific operations
    #

    # The following operations are for genering specific error messages. They
    # get some information as arguments, and they build an error message based
    # on them.

    def has_no_attr(self, typ: Type, member: str, context: Context) -> Type:
        """Report a missing or non-accessible member.

        The type argument is the base type. If member corresponds to
        an operator, use the corresponding operator name in the
        messages. Return type Any.
        """
        if (isinstance(typ, Instance) and
                (cast(Instance, typ)).type.has_readable_member(member)):
            self.fail('Member "{}" is not assignable'.format(member), context)
        elif isinstance(typ, Void):
            self.check_void(typ, context)
        elif member == '__contains__':
            self.fail('Unsupported right operand type for in ({})'.format(
                self.format(typ)), context)
        elif member in op_methods.values():
            # Access to a binary operator member (e.g. _add). This case does
            # not handle indexing operations.
            for op, method in op_methods.items():
                if method == member:
                    self.unsupported_left_operand(op, typ, context)
                    break
        elif member == '__neg__':
            self.fail('Unsupported operand type for unary - ({})'.format(
                self.format(typ)), context)
        elif member == '__pos__':
            self.fail('Unsupported operand type for unary + ({})'.format(
                self.format(typ)), context)
        elif member == '__invert__':
            self.fail('Unsupported operand type for ~ ({})'.format(
                self.format(typ)), context)
        elif member == '__getitem__':
            # Indexed get.
            self.fail('Value of type {} is not indexable'.format(
                self.format(typ)), context)
        elif member == '__setitem__':
            # Indexed set.
            self.fail('Unsupported target for indexed assignment', context)
        else:
            # The non-special case: a missing ordinary attribute.
            if not self.disable_type_names:
                self.fail('{} has no attribute "{}"'.format(self.format(typ),
                                                            member), context)
            else:
                self.fail('Some element of union has no attribute "{}"'.format(
                    member), context)
        return AnyType()

    def unsupported_operand_types(self, op: str, left_type: Any,
                                  right_type: Any, context: Context) -> None:
        """Report unsupported operand types for a binary operation.

        Types can be Type objects or strings.
        """
        if isinstance(left_type, Void) or isinstance(right_type, Void):
            self.check_void(left_type, context)
            self.check_void(right_type, context)
            return
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
        if not self.check_void(typ, context):
            if self.disable_type_names:
                msg = 'Unsupported left operand type for {} (some union)'.format(op)
            else:
                msg = 'Unsupported left operand type for {} ({})'.format(
                    op, self.format(typ))
            self.fail(msg, context)

    def type_expected_as_right_operand_of_is(self, context: Context) -> None:
        self.fail('Type expected as right operand of "is"', context)

    def not_callable(self, typ: Type, context: Context) -> Type:
        self.fail('{} not callable'.format(self.format(typ)), context)
        return AnyType()

    def incompatible_argument(self, n: int, callee: Callable, arg_type: Type,
                              context: Context) -> None:
        """Report an error about an incompatible argument type.

        The argument type is arg_type, argument number is n and the
        callee type is 'callee'. If the callee represents a method
        that corresponds to an operator, use the corresponding
        operator name in the messages.
        """
        target = ''
        if callee.name:
            name = callee.name
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
                self.invalid_index_type(arg_type, base, context)
                return

            if name.startswith('"__setitem__" of'):
                if n == 1:
                    self.invalid_index_type(arg_type, base, context)
                else:
                    self.fail(INCOMPATIBLE_TYPES_IN_ASSIGNMENT, context)
                return

            target = 'to {} '.format(name)

        msg = ''
        if callee.name == '<list>':
            name = callee.name[1:-1]
            msg = '{} item {} has incompatible type {}'.format(
                name[0].upper() + name[1:], n, self.format_simple(arg_type))
        elif callee.name == '<list-comprehension>':
            msg = 'List comprehension has incompatible type List[{}]'.format(
                strip_quotes(self.format(arg_type)))
        elif callee.name == '<generator>':
            msg = 'Generator has incompatible item type {}'.format(
                self.format_simple(arg_type))
        else:
            try:
                expected_type = callee.arg_types[n - 1]
            except IndexError:  # Varargs callees
                expected_type = callee.arg_types[-1]
            msg = 'Argument {} {}has incompatible type {}; expected {}'.format(
                n, target, self.format(arg_type), self.format(expected_type))
        self.fail(msg, context)

    def invalid_index_type(self, index_type: Type, base_str: str,
                           context: Context) -> None:
        self.fail('Invalid index type {} for {}'.format(
            self.format(index_type), base_str), context)

    def invalid_argument_count(self, callee: Callable, num_args: int,
                               context: Context) -> None:
        if num_args < len(callee.arg_types):
            self.too_few_arguments(callee, context)
        else:
            self.too_many_arguments(callee, context)

    def too_few_arguments(self, callee: Callable, context: Context) -> None:
        msg = 'Too few arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    def too_many_arguments(self, callee: Callable, context: Context) -> None:
        msg = 'Too many arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    def too_many_positional_arguments(self, callee: Callable,
                                      context: Context) -> None:
        msg = 'Too many positional arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    def unexpected_keyword_argument(self, callee: Callable, name: str,
                                    context: Context) -> None:
        msg = 'Unexpected keyword argument "{}"'.format(name)
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    def duplicate_argument_value(self, callee: Callable, index: int,
                                 context: Context) -> None:
        self.fail('{} gets multiple values for keyword argument "{}"'.
                  format(capitalize(callable_name(callee)),
                         callee.arg_names[index]), context)

    def does_not_return_value(self, void_type: Type, context: Context) -> None:
        """Report an error about a void type in a non-void context.

        The first argument must be a void type. If the void type has a
        source in it, report it in the error message. This allows
        giving messages such as 'Foo does not return a value'.
        """
        if (cast(Void, void_type)).source is None:
            self.fail('Function does not return a value', context)
        else:
            self.fail('{} does not return a value'.format(
                capitalize((cast(Void, void_type)).source)), context)

    def no_variant_matches_arguments(self, overload: Overloaded,
                                     context: Context) -> None:
        if overload.name():
            self.fail('No overload variant of {} matches argument types'
                      .format(overload.name()), context)
        else:
            self.fail('No overload variant matches argument types', context)

    def function_variants_overlap(self, n1: int, n2: int,
                                  context: Context) -> None:
        self.fail('Function signature variants {} and {} overlap'.format(
            n1 + 1, n2 + 1), context)

    def invalid_cast(self, target_type: Type, source_type: Type,
                     context: Context) -> None:
        if not self.check_void(source_type, context):
            self.fail('Cannot cast from {} to {}'.format(
                self.format(source_type), self.format(target_type)), context)

    def wrong_number_values_to_unpack(self, provided: int, expected: int, context: Context) -> None:
        if provided < expected:
            if provided == 1:
                self.fail('Need more than 1 value to unpack ({} expected)'.format(expected), context)
            else:
                self.fail('Need more than {} values to unpack ({} expected)'.format(provided, expected), context)
        elif provided > expected:
            self.fail('Too many values to unpack ({} expected, {} provided)'.format(expected, provided), context)

    def type_not_iterable(self, type: Type, context: Context) -> None:
        self.fail('\'{}\' object is not iterable'.format(type), context)

    def incompatible_operator_assignment(self, op: str,
                                         context: Context) -> None:
        self.fail('Result type of {} incompatible in assignment'.format(op),
                  context)

    def incompatible_value_count_in_assignment(self, lvalue_count: int,
                                               rvalue_count: int,
                                               context: Context) -> None:
        if rvalue_count < lvalue_count:
            self.fail('Need {} values to assign'.format(lvalue_count), context)
        elif rvalue_count > lvalue_count:
            self.fail('Too many values to assign', context)

    def type_incompatible_with_supertype(self, name: str, supertype: TypeInfo,
                                         context: Context) -> None:
        self.fail('Type of "{}" incompatible with supertype "{}"'.format(
            name, supertype.name), context)

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

    def boolean_return_value_expected(self, method: str,
                                      context: Context) -> None:
        self.fail('Boolean return value expected for method "{}"'.format(
            method), context)

    def incompatible_type_application(self, expected_arg_count: int,
                                      actual_arg_count: int,
                                      context: Context) -> None:
        if expected_arg_count == 0:
            self.fail('Type application targets a non-generic function',
                      context)
        elif actual_arg_count > expected_arg_count:
            self.fail('Type application has too many types ({} expected)'
                      .format(expected_arg_count), context)
        else:
            self.fail('Type application has too few types ({} expected)'
                      .format(expected_arg_count), context)

    def incompatible_array_item_type(self, typ: Type, index: int,
                                     context: Context) -> None:
        self.fail('Array item {} has incompatible type {}'.format(
            index, self.format(typ)), context)

    def could_not_infer_type_arguments(self, callee_type: Callable, n: int,
                                       context: Context) -> None:
        if callee_type.name and n > 0:
            self.fail('Cannot infer type argument {} of {}'.format(
                n, callee_type.name), context)
        else:
            self.fail('Cannot infer function type argument', context)

    def invalid_var_arg(self, typ: Type, context: Context) -> None:
        self.fail('List or tuple expected as variable arguments', context)

    def invalid_keyword_var_arg(self, typ: Type, context: Context) -> None:
        if isinstance(typ, Instance) and (
                (cast(Instance, typ)).type.fullname() == 'builtins.dict'):
            self.fail('Keywords must be strings', context)
        else:
            self.fail('Argument after ** must be a dictionary',
                      context)

    def incomplete_type_var_match(self, member: str, context: Context) -> None:
        self.fail('"{}" has incomplete match to supertype type variable'
                  .format(member), context)

    def not_implemented(self, msg: str, context: Context) -> Type:
        self.fail('Feature not implemented yet ({})'.format(msg), context)
        return AnyType()

    def undefined_in_superclass(self, member: str, context: Context) -> None:
        self.fail('"{}" undefined in superclass'.format(member), context)

    def check_void(self, typ: Type, context: Context) -> bool:
        """If type is void, report an error such as '.. does not
        return a value' and return True. Otherwise, return False.
        """
        if isinstance(typ, Void):
            self.does_not_return_value(typ, context)
            return True
        else:
            return False

    def too_few_string_formatting_arguments(self, context: Context) -> None:
        self.fail('Not enough arguments for format string', context)

    def too_many_string_formatting_arguments(self, context: Context) -> None:
        self.fail('Not all arguments converted during string formatting', context)

    def incomplete_conversion_specifier_format(self, context: Context) -> None:
        self.fail('Incomplete format', context)

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

    def invalid_method_type(self, sig: Callable, context: Context) -> None:
        self.fail('Invalid method type', context)

    def incompatible_conditional_function_def(self, defn: FuncDef) -> None:
        self.fail('All conditional function variants must have identical '
                  'signatures', defn)

    def cannot_instantiate_abstract_class(self, class_name: str,
                                          abstract_attributes: List[str],
                                          context: Context) -> None:
        attrs = format_string_list("'%s'" % a for a in abstract_attributes[:5])
        self.fail("Cannot instantiate abstract class '%s' with abstract "
                  "method%s %s" % (class_name, plural_s(abstract_attributes),
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

    def read_only_property(self, name: str, type: TypeInfo,
                           context: Context) -> None:
        self.fail('Property "{}" defined in "{}" is read-only'.format(
            name, type.name()), context)

    def incompatible_typevar_value(self, callee: Callable, index: int,
                                   type: Type, context: Context) -> None:
        self.fail('Type argument {} of {} has incompatible value {}'.format(
            index, callable_name(callee), self.format(type)), context)

    def disjointness_violation(self, cls: TypeInfo, disjoint: TypeInfo,
                               context: Context) -> None:
        self.fail('disjointclass constraint of class {} disallows {} as a '
                  'base class'.format(cls.name(), disjoint.name()), context)

    def overloaded_signatures_overlap(self, index1: int, index2: int,
                                      context: Context) -> None:
        self.fail('Overloaded function signatures {} and {} overlap with '
                  'incompatible return types'.format(index1, index2), context)

    def invalid_reverse_operator_signature(self, reverse: str, other: str,
                                           context: Context) -> None:
        self.fail('"Any" return type expected since argument to {} does not '
                  'support {}'.format(reverse, other), context)

    def reverse_operator_method_with_any_arg_must_return_any(
            self, method: str, context: Context) -> None:
        self.fail('"Any" return type expected since argument to {} has type '
                  '"Any"'.format(method), context)

    def operator_method_signatures_overlap(
            self, reverse_class: str, reverse_method: str, forward_class: str,
            forward_method: str, context: Context) -> None:
        self.fail('Signatures of "{}" of "{}" and "{}" of "{}" are unsafely '
                  'overlapping'.format(reverse_method, reverse_class,
                                       forward_method, forward_class), context)

    def signatures_incompatible(self, method: str, other_method: str,
                                context: Context) -> None:
        self.fail('Signatures of "{}" and "{}" are incompatible'.format(
            method, other_method), context)


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
    l = list(s)
    assert len(l) > 0
    if len(l) == 1:
        return l[0]
    else:
        return '%s and %s' % (', '.join(l[:-1]), l[-1])


def callable_name(type: Callable) -> str:
    if type.name:
        return type.name
    else:
        return 'function'


def temp_message_builder() -> MessageBuilder:
    """Return a message builder usable for collecting errors locally."""
    return MessageBuilder(Errors())
