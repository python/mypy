"""Message constants for generating error messages during type checking.

Literal messages should be defined as constants in this module so they won't get out of sync
if used in more than one place, and so that they can be easily introspected. These messages are
ultimately consumed by messages.MessageBuilder.fail(). For more non-trivial message generation,
add a method to MessageBuilder and call this instead.
"""

from typing import Optional
from typing_extensions import Final

from mypy import errorcodes as codes


class ErrorMessage:
    def __init__(self, value: str, code: Optional[codes.ErrorCode] = None) -> None:
        self.value = value
        self.code = code

    def format(self, *args: object, **kwargs: object) -> "ErrorMessage":
        return ErrorMessage(self.value.format(*args, **kwargs), code=self.code)


# Invalid types
INVALID_TYPE_RAW_ENUM_VALUE: Final = ErrorMessage("Invalid type: try using Literal[{}.{}] instead?")

# Type checker error message constants
NO_RETURN_VALUE_EXPECTED: Final = ErrorMessage("No return value expected", codes.RETURN_VALUE)
MISSING_RETURN_STATEMENT: Final = ErrorMessage("Missing return statement", codes.RETURN)
INVALID_IMPLICIT_RETURN: Final = ErrorMessage("Implicit return in function which does not return")
INCOMPATIBLE_RETURN_VALUE_TYPE: Final = "Incompatible return value type"
RETURN_VALUE_EXPECTED: Final = ErrorMessage("Return value expected", codes.RETURN_VALUE)
NO_RETURN_EXPECTED: Final = ErrorMessage("Return statement in function which does not return")
INVALID_EXCEPTION: Final = "Exception must be derived from BaseException"
INVALID_EXCEPTION_TYPE: Final = ErrorMessage("Exception type must be derived from BaseException")
RETURN_IN_ASYNC_GENERATOR: Final = ErrorMessage('"return" with value in async generator is not allowed')
INVALID_RETURN_TYPE_FOR_GENERATOR: Final = ErrorMessage(
    'The return type of a generator function should be "Generator"' " or one of its supertypes"
)
INVALID_RETURN_TYPE_FOR_ASYNC_GENERATOR: Final = ErrorMessage(
    'The return type of an async generator function should be "AsyncGenerator" or one of its '
    "supertypes"
)
INVALID_GENERATOR_RETURN_ITEM_TYPE: Final = ErrorMessage(
    "The return type of a generator function must be None in"
    " its third type parameter in Python 2"
)
YIELD_VALUE_EXPECTED: Final = ErrorMessage("Yield value expected")
INCOMPATIBLE_TYPES: Final = "Incompatible types"
INCOMPATIBLE_TYPES_IN_ASSIGNMENT: Final = "Incompatible types in assignment"
INCOMPATIBLE_REDEFINITION: Final = ErrorMessage("Incompatible redefinition")
INCOMPATIBLE_TYPES_IN_AWAIT: Final = 'Incompatible types in "await"'
INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AENTER: Final = (
    'Incompatible types in "async with" for "__aenter__"'
)
INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AEXIT: Final = (
    'Incompatible types in "async with" for "__aexit__"'
)
INCOMPATIBLE_TYPES_IN_ASYNC_FOR: Final = 'Incompatible types in "async for"'

INCOMPATIBLE_TYPES_IN_YIELD: Final = 'Incompatible types in "yield"'
INCOMPATIBLE_TYPES_IN_YIELD_FROM: Final = 'Incompatible types in "yield from"'
INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION: Final = "Incompatible types in string interpolation"
MUST_HAVE_NONE_RETURN_TYPE: Final = ErrorMessage('The return type of "{}" must be None')
INVALID_TUPLE_INDEX_TYPE: Final = "Invalid tuple index type"
TUPLE_INDEX_OUT_OF_RANGE: Final = ErrorMessage("Tuple index out of range")
INVALID_SLICE_INDEX: Final = "Slice index must be an integer or None"
CANNOT_INFER_LAMBDA_TYPE: Final = ErrorMessage("Cannot infer type of lambda")
CANNOT_ACCESS_INIT: Final = 'Cannot access "__init__" directly'
NON_INSTANCE_NEW_TYPE: Final = ErrorMessage('"__new__" must return a class instance (got {})')
INVALID_NEW_TYPE: Final = 'Incompatible return type for "__new__"'
BAD_CONSTRUCTOR_TYPE: Final = ErrorMessage("Unsupported decorated constructor type")
CANNOT_ASSIGN_TO_METHOD: Final = "Cannot assign to a method"
CANNOT_ASSIGN_TO_TYPE: Final = "Cannot assign to a type"
INCONSISTENT_ABSTRACT_OVERLOAD: Final = ErrorMessage(
    "Overloaded method has both abstract and non-abstract variants"
)
MULTIPLE_OVERLOADS_REQUIRED: Final = ErrorMessage("Single overload definition, multiple required")
READ_ONLY_PROPERTY_OVERRIDES_READ_WRITE: Final = ErrorMessage(
    "Read-only property cannot override read-write property"
)
FORMAT_REQUIRES_MAPPING: Final = "Format requires a mapping"
RETURN_TYPE_CANNOT_BE_CONTRAVARIANT: Final = ErrorMessage(
    "Cannot use a contravariant type variable as return type"
)
FUNCTION_PARAMETER_CANNOT_BE_COVARIANT: Final = ErrorMessage(
    "Cannot use a covariant type variable as a parameter"
)
INCOMPATIBLE_IMPORT_OF: Final = "Incompatible import of"
FUNCTION_TYPE_EXPECTED: Final = ErrorMessage("Function is missing a type annotation", codes.NO_UNTYPED_DEF)
ONLY_CLASS_APPLICATION: Final = ErrorMessage("Type application is only supported for generic classes")
RETURN_TYPE_EXPECTED: Final = ErrorMessage("Function is missing a return type annotation", codes.NO_UNTYPED_DEF)
ARGUMENT_TYPE_EXPECTED: Final = ErrorMessage("Function is missing a type annotation for one or more arguments", codes.NO_UNTYPED_DEF)
KEYWORD_ARGUMENT_REQUIRES_STR_KEY_TYPE: Final = (
    'Keyword argument only valid with "str" key type in call to "dict"'
)
ALL_MUST_BE_SEQ_STR: Final = ErrorMessage("Type of __all__ must be {}, not {}")
INVALID_TYPEDDICT_ARGS: Final = ErrorMessage(
    "Expected keyword arguments, {...}, or dict(...) in TypedDict constructor"
)
TYPEDDICT_KEY_MUST_BE_STRING_LITERAL: Final = ErrorMessage("Expected TypedDict key to be string literal")
MALFORMED_ASSERT: Final = ErrorMessage("Assertion is always true, perhaps remove parentheses?")
DUPLICATE_TYPE_SIGNATURES: Final = "Function has duplicate type signatures"
DESCRIPTOR_SET_NOT_CALLABLE: Final = ErrorMessage("{}.__set__ is not callable")
DESCRIPTOR_GET_NOT_CALLABLE: Final = "{}.__get__ is not callable"
MODULE_LEVEL_GETATTRIBUTE: Final = ErrorMessage("__getattribute__ is not valid at the module level")

# Generic
GENERIC_INSTANCE_VAR_CLASS_ACCESS: Final = (
    "Access to generic instance variables via class is ambiguous"
)
GENERIC_CLASS_VAR_ACCESS: Final = "Access to generic class variables is ambiguous"
BARE_GENERIC: Final = ErrorMessage("Missing type parameters for generic type {}", codes.TYPE_ARG)
IMPLICIT_GENERIC_ANY_BUILTIN: Final = ErrorMessage(
    'Implicit generic "Any". Use "{}" and specify generic parameters', codes.TYPE_ARG
)

# TypeVar
INCOMPATIBLE_TYPEVAR_VALUE: Final = ErrorMessage('Value of type variable "{}" of {} cannot be {}', codes.TYPE_VAR)
CANNOT_USE_TYPEVAR_AS_EXPRESSION: Final = 'Type variable "{}.{}" cannot be used as an expression'

# Super
TOO_MANY_ARGS_FOR_SUPER: Final = ErrorMessage('Too many arguments for "super"')
TOO_FEW_ARGS_FOR_SUPER: Final = ErrorMessage('Too few arguments for "super"', codes.CALL_ARG)
SUPER_WITH_SINGLE_ARG_NOT_SUPPORTED: Final = ErrorMessage('"super" with a single argument not supported')
UNSUPPORTED_ARG_1_FOR_SUPER: Final = ErrorMessage('Unsupported argument 1 for "super"')
UNSUPPORTED_ARG_2_FOR_SUPER: Final = ErrorMessage('Unsupported argument 2 for "super"')
SUPER_VARARGS_NOT_SUPPORTED: Final = ErrorMessage('Varargs not supported with "super"')
SUPER_POSITIONAL_ARGS_REQUIRED: Final = ErrorMessage('"super" only accepts positional arguments')
SUPER_ARG_2_NOT_INSTANCE_OF_ARG_1: Final = ErrorMessage('Argument 2 for "super" not an instance of argument 1')
TARGET_CLASS_HAS_NO_BASE_CLASS: Final = ErrorMessage("Target class has no base class")
SUPER_OUTSIDE_OF_METHOD_NOT_SUPPORTED: Final = ErrorMessage("super() outside of a method is not supported")
SUPER_ENCLOSING_POSITIONAL_ARGS_REQUIRED: Final = ErrorMessage(
    "super() requires one or more positional arguments in enclosing function"
)

# Self-type
MISSING_OR_INVALID_SELF_TYPE: Final = ErrorMessage(
    "Self argument missing for a non-static method (or an invalid type for self)"
)
ERASED_SELF_TYPE_NOT_SUPERTYPE: Final =ErrorMessage(
    'The erased type of self "{}" is not a supertype of its class "{}"'
)
INVALID_SELF_TYPE_OR_EXTRA_ARG: Final = ErrorMessage(
    "Invalid type for self, or extra argument type in function annotation"
)

# Final
CANNOT_INHERIT_FROM_FINAL: Final = ErrorMessage('Cannot inherit from final class "{}"')
DEPENDENT_FINAL_IN_CLASS_BODY: Final = ErrorMessage(
    "Final name declared in class body cannot depend on type variables"
)
CANNOT_ACCESS_FINAL_INSTANCE_ATTR: Final = (
    'Cannot access final instance attribute "{}" on class object'
)
CANNOT_MAKE_DELETABLE_FINAL: Final = ErrorMessage("Deletable attribute cannot be final")

# ClassVar
CANNOT_OVERRIDE_INSTANCE_VAR: Final = ErrorMessage(
    'Cannot override instance variable (previously declared on base class "{}") with class '
    "variable"
)
CANNOT_OVERRIDE_CLASS_VAR: Final = ErrorMessage(
    'Cannot override class variable (previously declared on base class "{}") with instance '
    "variable"
)

# Protocol
RUNTIME_PROTOCOL_EXPECTED: Final = ErrorMessage(
    "Only @runtime_checkable protocols can be used with instance and class checks"
)
CANNOT_INSTANTIATE_PROTOCOL: Final = ErrorMessage('Cannot instantiate protocol class "{}"')

CONTIGUOUS_ITERABLE_EXPECTED: Final = ErrorMessage("Contiguous iterable with same type expected")
ITERABLE_TYPE_EXPECTED: Final = ErrorMessage("Invalid type '{}' for *expr (iterable expected)")
TYPE_GUARD_POS_ARG_REQUIRED: Final = ErrorMessage("Type guard requires positional argument")
TOO_MANY_UNION_COMBINATIONS: Final = ErrorMessage("Not all union combinations were tried because there are too many unions")

# Type Analysis
TYPEANAL_INTERNAL_ERROR: Final = ErrorMessage('Internal error (node is None, kind={})')
NOT_SUBSCRIPTABLE: Final = ErrorMessage('"{}" is not subscriptable')
NOT_SUBSCRIPTABLE_REPLACEMENT: Final = ErrorMessage('"{}" is not subscriptable, use "{}" instead')
PARAMSPEC_UNBOUND: Final = ErrorMessage('ParamSpec "{}" is unbound')
PARAMSPEC_INVALID_LOCATION: Final = ErrorMessage('Invalid location for ParamSpec "{}"')
NO_BOUND_TYPEVAR_GENERIC_ALIAS: Final = ErrorMessage('Can\'t use bound type variable "{}" to define generic alias')
TYPEVAR_USED_WITH_ARGS: Final = ErrorMessage('Type variable "{}" used with arguments')
ONLY_OUTERMOST_FINAL: Final =  ErrorMessage("Final can be only used as an outermost qualifier in a variable annotation")
BUILTIN_TUPLE_NOT_DEFINED: Final = ErrorMessage('Name "tuple" is not defined')
SINGLE_TYPE_ARG: Final = ErrorMessage('{} must have exactly one type argument')
INVALID_NESTED_CLASSVAR: Final = ErrorMessage('Invalid type: ClassVar nested inside other type')
CLASSVAR_ATMOST_ONE_TYPE_ARG: Final = ErrorMessage('ClassVar[...] must have at most one type argument')
ANNOTATED_SINGLE_TYPE_ARG: Final = ErrorMessage('Annotated[...] must have exactly one type argument and at least one annotation')
GENERIC_TUPLE_UNSUPPORTED: Final = ErrorMessage('Generic tuple types not supported')
GENERIC_TYPED_DICT_UNSUPPORTED: Final = ErrorMessage('Generic TypedDict types not supported')
VARIABLE_NOT_VALID_TYPE: Final = ErrorMessage('Variable "{}" is not valid as a type', codes.VALID_TYPE)
FUNCTION_NOT_VALID_TYPE: Final = ErrorMessage('Function "{}" is not valid as a type', codes.VALID_TYPE)
MODULE_NOT_VALID_TYPE: Final = ErrorMessage('Module "{}" is not valid as a type', codes.VALID_TYPE)
UNBOUND_TYPEVAR: Final = ErrorMessage('Type variable "{}" is unbound', codes.VALID_TYPE)
CANNOT_INTERPRET_AS_TYPE: Final = ErrorMessage('Cannot interpret reference "{}" as a type', codes.VALID_TYPE)
INVALID_TYPE: Final = ErrorMessage('Invalid type')
BRACKETED_EXPR_INVALID_TYPE: Final = ErrorMessage('Bracketed expression "[...]" is not valid as a type')
ANNOTATION_SYNTAX_ERROR: Final = ErrorMessage('Syntax error in type annotation', codes.SYNTAX)
TUPLE_SINGLE_STAR_TYPE: Final = ErrorMessage('At most one star type allowed in a tuple')
INVALID_TYPE_USE_LITERAL: Final = ErrorMessage("Invalid type: try using Literal[{}] instead?", codes.VALID_TYPE)
INVALID_LITERAL_TYPE: Final = ErrorMessage("Invalid type: {} literals cannot be used as a type", codes.VALID_TYPE)
INVALID_ANNOTATION: Final = ErrorMessage('Invalid type comment or annotation', codes.VALID_TYPE)
PIPE_UNION_REQUIRES_PY310: Final = ErrorMessage("X | Y syntax for unions requires Python 3.10")
UNEXPECTED_ELLIPSIS: Final = ErrorMessage('Unexpected "..."')
CALLABLE_INVALID_FIRST_ARG: Final = ErrorMessage('The first argument to Callable must be a list of types or "..."')
CALLABLE_INVALID_ARGS: Final = ErrorMessage('Please use "Callable[[<parameters>], <return type>]" or "Callable"')
INVALID_ARG_CONSTRUCTOR: Final = ErrorMessage('Invalid argument constructor "{}"')
ARGS_SHOULD_NOT_HAVE_NAMES: Final = ErrorMessage("{} arguments should not have names")
LITERAL_AT_LEAST_ONE_ARG: Final = ErrorMessage('Literal[...] must have at least one parameter')
LITERAL_INDEX_CANNOT_BE_ANY: Final = ErrorMessage('Parameter {} of Literal[...] cannot be of type "Any"')
LITERAL_INDEX_INVALID_TYPE: Final = ErrorMessage('Parameter {} of Literal[...] cannot be of type "{}"')
LITERAL_INVALID_EXPRESSION: Final = ErrorMessage('Invalid type: Literal[...] cannot contain arbitrary expressions')
LITERAL_INVALID_PARAMETER: Final = ErrorMessage('Parameter {} of Literal[...] is invalid')
TYPEVAR_BOUND_BY_OUTER_CLASS: Final = ErrorMessage('Type variable "{}" is bound by an outer class')
TYPE_ARG_COUNT_MISMATCH: Final = ErrorMessage('"{}" expects {}, but {} given', codes.TYPE_ARG)
TYPE_ALIAS_ARG_COUNT_MISMATCH: Final = ErrorMessage('Bad number of arguments for type alias, expected: {}, given: {}')

# function definitions, from nodes.py
DUPLICATE_ARGUMENT_IN_X: Final = ErrorMessage('Duplicate argument "{}" in {}')
POS_ARGS_BEFORE_DEFAULT_NAMED_OR_VARARGS: Final = ErrorMessage("Required positional args may not appear after default, named or var args")
DEFAULT_ARGS_BEFORE_NAMED_OR_VARARGS: Final = ErrorMessage("Positional default args may not appear after named or var args")
VAR_ARGS_BEFORE_NAMED_OR_VARARGS: Final = ErrorMessage("Var args may not appear after named or var args")
KWARGS_MUST_BE_LAST: Final = ErrorMessage("A **kwargs argument must be the last argument")
MULTIPLE_KWARGS: Final = ErrorMessage("You may only have one **kwargs argument")

# from type_anal_hook.py
INVALID_SIGNAL_TYPE: Final = ErrorMessage('Invalid "Signal" type (expected "Signal[[t, ...]]")')

# NewType
NEWTYPE_USED_WITH_PROTOCOL: Final = ErrorMessage("NewType cannot be used with protocol classes")
NEWTYPE_ARG_MUST_BE_SUBCLASSABLE: Final = ErrorMessage("Argument 2 to NewType(...) must be subclassable (got {})", codes.VALID_NEWTYPE)
CANNOT_DECLARE_TYPE_OF_NEWTYPE: Final = ErrorMessage("Cannot declare the type of a NewType declaration")
CANNOT_REDEFINE_AS_NEWTYPE: Final = ErrorMessage('Cannot redefine "{}" as a NewType')
NEWTYPE_EXPECTS_TWO_ARGS: Final = ErrorMessage("NewType(...) expects exactly two positional arguments")
NEWTYPE_ARG_STRING_LITERAL: Final = ErrorMessage("Argument 1 to NewType(...) must be a string literal")
NEWTYPE_ARG_VARNAME_MISMATCH: Final = ErrorMessage('String argument 1 "{}" to NewType(...) does not match variable name "{}"')
NEWTYPE_ARG_INVALID_TYPE: Final = ErrorMessage("Argument 2 to NewType(...) must be a valid type")

# TypedDict
TYPEDDICT_BASES_MUST_BE_TYPEDDICTS: Final = ErrorMessage("All bases of a new TypedDict must be TypedDict types")
TYPEDDICT_OVERWRITE_FIELD_IN_MERGE: Final = ErrorMessage('Overwriting TypedDict field "{}" while merging')
TYPEDDICT_OVERWRITE_FIELD_IN_EXTEND: Final = ErrorMessage('Overwriting TypedDict field "{}" while extending')
TYPEDDICT_CLASS_ERROR: Final = ErrorMessage(
    "Invalid statement in TypedDict definition; " 'expected "field_name: field_type"'
)
TYPEDDICT_ARG_NAME_MISMATCH: Final = ErrorMessage('First argument "{}" to TypedDict() does not match variable name "{}"', codes.NAME_MATCH)
TYPEDDICT_TOO_FEW_ARGS: Final = ErrorMessage("Too few arguments for TypedDict()")
TYPEDDICT_TOO_MANY_ARGS: Final = ErrorMessage("Too many arguments for TypedDict()")
TYPEDDICT_UNEXPECTED_ARGS: Final = ErrorMessage("Unexpected arguments to TypedDict()")
TYPEDDICT_CALL_UNEXPECTED_KWARG: Final = ErrorMessage('Unexpected keyword argument "{}" for "TypedDict"')
TYPEDDICT_CALL_EXPECTED_STRING_LITERAL: Final = ErrorMessage("TypedDict() expects a string literal as the first argument")
TYPEDDICT_CALL_EXPECTED_DICT: Final = ErrorMessage("TypedDict() expects a dictionary literal as the second argument")
TYPEDDICT_RHS_VALUE_UNSUPPORTED: Final = ErrorMessage('Right hand side values are not supported in TypedDict')
TYPEDDICT_TOTAL_MUST_BE_BOOL: Final = ErrorMessage('TypedDict() "total" argument must be True or False')
TYPEDDICT_TOTAL_MUST_BE_BOOL_2: Final = ErrorMessage('Value of "total" must be True or False')
TYPEDDICT_DUPLICATE_KEY: Final = ErrorMessage('Duplicate TypedDict key "{}"')
TYPEDDICT_INVALID_FIELD_NAME: Final = ErrorMessage("Invalid TypedDict() field name")
TYPEDDICT_INVALID_FIELD_TYPE: Final = ErrorMessage('Invalid field type')

# Enum
ENUM_ATTRIBUTE_UNSUPPORTED: Final = ErrorMessage("Enum type as attribute is not supported")
ENUM_CALL_UNEXPECTED_ARGS: Final = ErrorMessage("Unexpected arguments to {}()")
ENUM_CALL_UNEXPECTED_KWARG: Final = ErrorMessage('Unexpected keyword argument "{}"')
ENUM_CALL_TOO_MANY_ARGS: Final = ErrorMessage("Too many arguments for {}()")
ENUM_CALL_TOO_FEW_ARGS: Final = ErrorMessage("Too few arguments for {}()")
ENUM_CALL_EXPECTED_STRING_LITERAL: Final = ErrorMessage("{}() expects a string literal as the first argument")
ENUM_CALL_EXPECTED_STRINGS_OR_PAIRS: Final = ErrorMessage("{}() with tuple or list expects strings or (name, value) pairs")
ENUM_CALL_DICT_EXPECTED_STRING_KEYS: Final = ErrorMessage("{}() with dict literal requires string literals")
ENUM_CALL_EXPECTED_LITERAL: Final = ErrorMessage("{}() expects a string, tuple, list or dict literal as the second argument")
ENUM_CALL_ATLEAST_ONE_ITEM: Final = ErrorMessage("{}() needs at least one item")

# NamedTuple
NAMEDTUPLE_SUPPORTED_ABOVE_PY36: Final = ErrorMessage('NamedTuple class syntax is only supported in Python 3.6')
NAMEDTUPLE_SINGLE_BASE: Final = ErrorMessage('NamedTuple should be a single base')
NAMEDTUPLE_CLASS_ERROR: Final = ErrorMessage(
    "Invalid statement in NamedTuple definition; " 'expected "field_name: field_type [= default]"'
)
NAMEDTUPLE_FIELD_NO_UNDERSCORE: Final = ErrorMessage('NamedTuple field name cannot start with an underscore: {}')
NAMEDTUPLE_FIELD_DEFAULT_AFTER_NONDEFAULT: Final = ErrorMessage('Non-default NamedTuple fields cannot follow default fields')
NAMEDTUPLE_TOO_FEW_ARGS: Final = ErrorMessage("Too few arguments for namedtuple()")
NAMEDTUPLE_TOO_MANY_ARGS: Final = ErrorMessage("Too many arguments for namedtuple()")
NAMEDTUPLE_EXPECTED_LIST_TUPLE_DEFAULTS: Final = ErrorMessage("List or tuple literal expected as the defaults argument to namedtuple()")
NAMEDTUPLE_UNEXPECTED_ARGS: Final = ErrorMessage("Unexpected arguments to namedtuple()")
NAMEDTUPLE_ARG_EXPECTED_STRING_LITERAL : Final = ErrorMessage("namedtuple() expects a string literal as the first argument")
NAMEDTUPLE_ARG_EXPECTED_LIST_TUPLE: Final = ErrorMessage("List or tuple literal expected as the second argument to namedtuple()")
NAMEDTUPLE_EXPECTED_STRING_LITERAL : Final = ErrorMessage("String literal expected as namedtuple() item")
NAMEDTUPLE_FIELDS_NO_UNDERSCORE: Final = ErrorMessage("namedtuple() field names cannot start with an underscore: {}")
NAMEDTUPLE_TOO_MANY_DEFAULTS: Final = ErrorMessage("Too many defaults given in call to namedtuple()")
NAMEDTUPLE_INVALID_FIELD_DEFINITION: Final = ErrorMessage("Invalid NamedTuple field definition")
NAMEDTUPLE_INVALID_FIELD_NAME: Final = ErrorMessage("Invalid NamedTuple() field name")
NAMEDTUPLE_INVALID_FIELD_TYPE: Final = ErrorMessage('Invalid field type')
NAMEDTUPLE_TUPLE_EXPECTED: Final = ErrorMessage("Tuple expected as NamedTuple() field")
NAMEDTUPLE_CANNOT_OVERWRITE_ATTRIBUTE: Final = ErrorMessage('Cannot overwrite NamedTuple attribute "{}"')

# TypeArgs
TYPEVAR_INVALID_TYPE_ARG: Final = ErrorMessage('Type variable "{}" not valid as type argument value for "{}"', codes.TYPE_VAR)
TYPE_ARG_INVALID_SUBTYPE: Final = ErrorMessage('Type argument "{}" of "{}" must be a subtype of "{}"', codes.TYPE_VAR)
TYPE_ARG_INVALID_VALUE: Final = ErrorMessage('Invalid type argument value for "{}"', codes.TYPE_VAR)

