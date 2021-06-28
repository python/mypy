"""Message constants for generating error messages during type checking.

Literal messages should be defined as constants in this module so they won't get out of sync
if used in more than one place, and so that they can be easily introspected. These messages are
ultimately consumed by messages.MessageBuilder.fail(). For more non-trivial message generation,
add a method to MessageBuilder and call this instead.
"""

from typing_extensions import Final

# Invalid types
INVALID_TYPE_RAW_ENUM_VALUE: Final = "Invalid type: try using Literal[{}.{}] instead?"

# Type checker error message constants
NO_RETURN_VALUE_EXPECTED: Final = "No return value expected"
MISSING_RETURN_STATEMENT: Final = "Missing return statement"
INVALID_IMPLICIT_RETURN: Final = "Implicit return in function which does not return"
INCOMPATIBLE_RETURN_VALUE_TYPE: Final = "Incompatible return value type"
RETURN_VALUE_EXPECTED: Final = "Return value expected"
NO_RETURN_EXPECTED: Final = "Return statement in function which does not return"
INVALID_EXCEPTION: Final = "Exception must be derived from BaseException"
INVALID_EXCEPTION_TYPE: Final = "Exception type must be derived from BaseException"
RETURN_IN_ASYNC_GENERATOR: Final = '"return" with value in async generator is not allowed'
INVALID_RETURN_TYPE_FOR_GENERATOR: Final = (
    'The return type of a generator function should be "Generator"' " or one of its supertypes"
)
INVALID_RETURN_TYPE_FOR_ASYNC_GENERATOR: Final = (
    'The return type of an async generator function should be "AsyncGenerator" or one of its '
    "supertypes"
)
INVALID_GENERATOR_RETURN_ITEM_TYPE: Final = (
    "The return type of a generator function must be None in"
    " its third type parameter in Python 2"
)
YIELD_VALUE_EXPECTED: Final = "Yield value expected"
INCOMPATIBLE_TYPES: Final = "Incompatible types"
INCOMPATIBLE_TYPES_IN_ASSIGNMENT: Final = "Incompatible types in assignment"
INCOMPATIBLE_REDEFINITION: Final = "Incompatible redefinition"
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
MUST_HAVE_NONE_RETURN_TYPE: Final = 'The return type of "{}" must be None'
INVALID_TUPLE_INDEX_TYPE: Final = "Invalid tuple index type"
TUPLE_INDEX_OUT_OF_RANGE: Final = "Tuple index out of range"
INVALID_SLICE_INDEX: Final = "Slice index must be an integer or None"
CANNOT_INFER_LAMBDA_TYPE: Final = "Cannot infer type of lambda"
CANNOT_ACCESS_INIT: Final = 'Cannot access "__init__" directly'
NON_INSTANCE_NEW_TYPE: Final = '"__new__" must return a class instance (got {})'
INVALID_NEW_TYPE: Final = 'Incompatible return type for "__new__"'
BAD_CONSTRUCTOR_TYPE: Final = "Unsupported decorated constructor type"
CANNOT_ASSIGN_TO_METHOD: Final = "Cannot assign to a method"
CANNOT_ASSIGN_TO_TYPE: Final = "Cannot assign to a type"
INCONSISTENT_ABSTRACT_OVERLOAD: Final = (
    "Overloaded method has both abstract and non-abstract variants"
)
MULTIPLE_OVERLOADS_REQUIRED: Final = "Single overload definition, multiple required"
READ_ONLY_PROPERTY_OVERRIDES_READ_WRITE: Final = (
    "Read-only property cannot override read-write property"
)
FORMAT_REQUIRES_MAPPING: Final = "Format requires a mapping"
RETURN_TYPE_CANNOT_BE_CONTRAVARIANT: Final = (
    "Cannot use a contravariant type variable as return type"
)
FUNCTION_PARAMETER_CANNOT_BE_COVARIANT: Final = (
    "Cannot use a covariant type variable as a parameter"
)
INCOMPATIBLE_IMPORT_OF: Final = "Incompatible import of"
FUNCTION_TYPE_EXPECTED: Final = "Function is missing a type annotation"
ONLY_CLASS_APPLICATION: Final = "Type application is only supported for generic classes"
RETURN_TYPE_EXPECTED: Final = "Function is missing a return type annotation"
ARGUMENT_TYPE_EXPECTED: Final = "Function is missing a type annotation for one or more arguments"
KEYWORD_ARGUMENT_REQUIRES_STR_KEY_TYPE: Final = (
    'Keyword argument only valid with "str" key type in call to "dict"'
)
ALL_MUST_BE_SEQ_STR: Final = "Type of __all__ must be {}, not {}"
INVALID_TYPEDDICT_ARGS: Final = (
    "Expected keyword arguments, {...}, or dict(...) in TypedDict constructor"
)
TYPEDDICT_KEY_MUST_BE_STRING_LITERAL: Final = "Expected TypedDict key to be string literal"
MALFORMED_ASSERT: Final = "Assertion is always true, perhaps remove parentheses?"
DUPLICATE_TYPE_SIGNATURES: Final = "Function has duplicate type signatures"
DESCRIPTOR_SET_NOT_CALLABLE: Final = "{}.__set__ is not callable"
DESCRIPTOR_GET_NOT_CALLABLE: Final = "{}.__get__ is not callable"
MODULE_LEVEL_GETATTRIBUTE: Final = "__getattribute__ is not valid at the module level"

# Generic
GENERIC_INSTANCE_VAR_CLASS_ACCESS: Final = (
    "Access to generic instance variables via class is ambiguous"
)
GENERIC_CLASS_VAR_ACCESS: Final = "Access to generic class variables is ambiguous"
BARE_GENERIC: Final = "Missing type parameters for generic type {}"
IMPLICIT_GENERIC_ANY_BUILTIN: Final = (
    'Implicit generic "Any". Use "{}" and specify generic parameters'
)

# TypeVar
INCOMPATIBLE_TYPEVAR_VALUE: Final = 'Value of type variable "{}" of {} cannot be {}'
CANNOT_USE_TYPEVAR_AS_EXPRESSION: Final = 'Type variable "{}.{}" cannot be used as an expression'

# Super
TOO_MANY_ARGS_FOR_SUPER: Final = 'Too many arguments for "super"'
TOO_FEW_ARGS_FOR_SUPER: Final = 'Too few arguments for "super"'
SUPER_WITH_SINGLE_ARG_NOT_SUPPORTED: Final = '"super" with a single argument not supported'
UNSUPPORTED_ARG_1_FOR_SUPER: Final = 'Unsupported argument 1 for "super"'
UNSUPPORTED_ARG_2_FOR_SUPER: Final = 'Unsupported argument 2 for "super"'
SUPER_VARARGS_NOT_SUPPORTED: Final = 'Varargs not supported with "super"'
SUPER_POSITIONAL_ARGS_REQUIRED: Final = '"super" only accepts positional arguments'
SUPER_ARG_2_NOT_INSTANCE_OF_ARG_1: Final = 'Argument 2 for "super" not an instance of argument 1'
TARGET_CLASS_HAS_NO_BASE_CLASS: Final = "Target class has no base class"
SUPER_OUTSIDE_OF_METHOD_NOT_SUPPORTED: Final = "super() outside of a method is not supported"
SUPER_ENCLOSING_POSITIONAL_ARGS_REQUIRED: Final = (
    "super() requires one or more positional arguments in enclosing function"
)

# Self-type
MISSING_OR_INVALID_SELF_TYPE: Final = (
    "Self argument missing for a non-static method (or an invalid type for self)"
)
ERASED_SELF_TYPE_NOT_SUPERTYPE: Final = (
    'The erased type of self "{}" is not a supertype of its class "{}"'
)
INVALID_SELF_TYPE_OR_EXTRA_ARG: Final = (
    "Invalid type for self, or extra argument type in function annotation"
)

# Final
CANNOT_INHERIT_FROM_FINAL: Final = 'Cannot inherit from final class "{}"'
DEPENDENT_FINAL_IN_CLASS_BODY: Final = (
    "Final name declared in class body cannot depend on type variables"
)
CANNOT_ACCESS_FINAL_INSTANCE_ATTR: Final = (
    'Cannot access final instance attribute "{}" on class object'
)
CANNOT_MAKE_DELETABLE_FINAL: Final = "Deletable attribute cannot be final"

# ClassVar
CANNOT_OVERRIDE_INSTANCE_VAR: Final = (
    'Cannot override instance variable (previously declared on base class "{}") with class '
    "variable"
)
CANNOT_OVERRIDE_CLASS_VAR: Final = (
    'Cannot override class variable (previously declared on base class "{}") with instance '
    "variable"
)

# Protocol
RUNTIME_PROTOCOL_EXPECTED: Final = (
    "Only @runtime_checkable protocols can be used with instance and class checks"
)
CANNOT_INSTANTIATE_PROTOCOL: Final = 'Cannot instantiate protocol class "{}"'
