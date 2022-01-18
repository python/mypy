"""Message constants for generating error messages during type checking.

Literal messages should be defined as constants in this module so they won't get out of sync
if used in more than one place, and so that they can be easily introspected. These messages are
ultimately consumed by messages.MessageBuilder.fail(). For more non-trivial message generation,
add a method to MessageBuilder and call this instead.
"""

from typing import NamedTuple, Optional
from typing_extensions import Final

from mypy import errorcodes as codes


class ErrorMessage(NamedTuple):
    value: str
    code: Optional[codes.ErrorCode] = None

    def format(self, *args: object, **kwargs: object) -> "ErrorMessage":
        return ErrorMessage(self.value.format(*args, **kwargs), code=self.code)


# Invalid types
INVALID_TYPE_RAW_ENUM_VALUE: Final = ErrorMessage(
    "Invalid type: try using Literal[{}.{}] instead?"
)

# Type checker error message constants
NO_RETURN_VALUE_EXPECTED: Final = ErrorMessage("No return value expected", codes.RETURN_VALUE)
MISSING_RETURN_STATEMENT: Final = ErrorMessage("Missing return statement", codes.RETURN)
INVALID_IMPLICIT_RETURN: Final = ErrorMessage("Implicit return in function which does not return")
INCOMPATIBLE_RETURN_VALUE_TYPE: Final = ErrorMessage(
    "Incompatible return value type", codes.RETURN_VALUE
)
RETURN_VALUE_EXPECTED: Final = ErrorMessage("Return value expected", codes.RETURN_VALUE)
NO_RETURN_EXPECTED: Final = ErrorMessage("Return statement in function which does not return")
INVALID_EXCEPTION: Final = ErrorMessage("Exception must be derived from BaseException")
INVALID_EXCEPTION_TYPE: Final = ErrorMessage("Exception type must be derived from BaseException")
RETURN_IN_ASYNC_GENERATOR: Final = ErrorMessage(
    '"return" with value in async generator is not allowed'
)
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
INCOMPATIBLE_TYPES_IN_AWAIT: Final = ErrorMessage('Incompatible types in "await"')
INCOMPATIBLE_REDEFINITION: Final = ErrorMessage("Incompatible redefinition")
INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AENTER: Final = (
    'Incompatible types in "async with" for "__aenter__"'
)
INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AEXIT: Final = (
    'Incompatible types in "async with" for "__aexit__"'
)
INCOMPATIBLE_TYPES_IN_ASYNC_FOR: Final = 'Incompatible types in "async for"'

INCOMPATIBLE_TYPES_IN_YIELD: Final = ErrorMessage('Incompatible types in "yield"')
INCOMPATIBLE_TYPES_IN_YIELD_FROM: Final = ErrorMessage('Incompatible types in "yield from"')
INCOMPATIBLE_TYPES_IN_STR_INTERPOLATION: Final = "Incompatible types in string interpolation"
INCOMPATIBLE_TYPES_IN_CAPTURE: Final = ErrorMessage('Incompatible types in capture pattern')
MUST_HAVE_NONE_RETURN_TYPE: Final = ErrorMessage('The return type of "{}" must be None')
INVALID_TUPLE_INDEX_TYPE: Final = ErrorMessage("Invalid tuple index type")
TUPLE_INDEX_OUT_OF_RANGE: Final = ErrorMessage("Tuple index out of range")
INVALID_SLICE_INDEX: Final = ErrorMessage("Slice index must be an integer or None")
CANNOT_INFER_LAMBDA_TYPE: Final = ErrorMessage("Cannot infer type of lambda")
CANNOT_ACCESS_INIT: Final = 'Cannot access "__init__" directly'
NON_INSTANCE_NEW_TYPE: Final = ErrorMessage('"__new__" must return a class instance (got {})')
INVALID_NEW_TYPE: Final = ErrorMessage('Incompatible return type for "__new__"')
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
FUNCTION_TYPE_EXPECTED: Final = ErrorMessage(
    "Function is missing a type annotation", codes.NO_UNTYPED_DEF
)
ONLY_CLASS_APPLICATION: Final = ErrorMessage(
    "Type application is only supported for generic classes"
)
RETURN_TYPE_EXPECTED: Final = ErrorMessage(
    "Function is missing a return type annotation", codes.NO_UNTYPED_DEF
)
ARGUMENT_TYPE_EXPECTED: Final = ErrorMessage(
    "Function is missing a type annotation for one or more arguments", codes.NO_UNTYPED_DEF
)
KEYWORD_ARGUMENT_REQUIRES_STR_KEY_TYPE: Final = ErrorMessage(
    'Keyword argument only valid with "str" key type in call to "dict"'
)
ALL_MUST_BE_SEQ_STR: Final = ErrorMessage("Type of __all__ must be {}, not {}")
INVALID_TYPEDDICT_ARGS: Final = ErrorMessage(
    "Expected keyword arguments, {...}, or dict(...) in TypedDict constructor"
)
TYPEDDICT_KEY_MUST_BE_STRING_LITERAL: Final = ErrorMessage(
    "Expected TypedDict key to be string literal"
)
MALFORMED_ASSERT: Final = ErrorMessage("Assertion is always true, perhaps remove parentheses?")
DUPLICATE_TYPE_SIGNATURES: Final = ErrorMessage("Function has duplicate type signatures")
DESCRIPTOR_SET_NOT_CALLABLE: Final = ErrorMessage("{}.__set__ is not callable")
DESCRIPTOR_GET_NOT_CALLABLE: Final = "{}.__get__ is not callable"
MODULE_LEVEL_GETATTRIBUTE: Final = ErrorMessage(
    "__getattribute__ is not valid at the module level"
)
NAME_NOT_IN_SLOTS: Final = ErrorMessage(
    'Trying to assign name "{}" that is not in "__slots__" of type "{}"'
)
TYPE_ALWAYS_TRUE: Final = ErrorMessage(
    "{} which does not implement __bool__ or __len__ "
    "so it could always be true in boolean context",
    code=codes.TRUTHY_BOOL,
)
TYPE_ALWAYS_TRUE_UNIONTYPE: Final = ErrorMessage(
    "{} of which no members implement __bool__ or __len__ "
    "so it could always be true in boolean context",
    code=codes.TRUTHY_BOOL,
)
FUNCTION_ALWAYS_TRUE: Final = ErrorMessage(
    'Function {} could always be true in boolean context',
    code=codes.TRUTHY_BOOL,
)
NOT_CALLABLE: Final = '{} not callable'
PYTHON2_PRINT_FILE_TYPE: Final = (
    'Argument "file" to "print" has incompatible type "{}"; expected "{}"'
)

# Generic
GENERIC_INSTANCE_VAR_CLASS_ACCESS: Final = (
    "Access to generic instance variables via class is ambiguous"
)
GENERIC_CLASS_VAR_ACCESS: Final = "Access to generic class variables is ambiguous"
BARE_GENERIC: Final = ErrorMessage(
    "Missing type parameters for generic type {}", codes.TYPE_ARG
)
IMPLICIT_GENERIC_ANY_BUILTIN: Final = ErrorMessage(
    'Implicit generic "Any". Use "{}" and specify generic parameters', codes.TYPE_ARG
)

# TypeVar
INCOMPATIBLE_TYPEVAR_VALUE: Final = 'Value of type variable "{}" of {} cannot be {}'
CANNOT_USE_TYPEVAR_AS_EXPRESSION: Final = 'Type variable "{}.{}" cannot be used as an expression'
INVALID_TYPEVAR_AS_TYPEARG: Final = 'Type variable "{}" not valid as type argument value for "{}"'
INVALID_TYPEVAR_ARG_BOUND: Final = 'Type argument {} of "{}" must be a subtype of {}'
INVALID_TYPEVAR_ARG_VALUE: Final = 'Invalid type argument value for "{}"'
TYPEVAR_VARIANCE_DEF: Final = 'TypeVar "{}" may only be a literal bool'
TYPEVAR_BOUND_MUST_BE_TYPE: Final = 'TypeVar "bound" must be a type'
TYPEVAR_UNEXPECTED_ARGUMENT: Final = 'Unexpected argument to "TypeVar()"'

# FastParse
TYPE_COMMENT_SYNTAX_ERROR_VALUE: Final = ErrorMessage(
    'syntax error in type comment "{}"', codes.SYNTAX
)
INVALID_TYPE_IGNORE: Final = ErrorMessage('Invalid "type: ignore" comment', codes.SYNTAX)
ELLIPSIS_WITH_OTHER_TYPEARGS: Final = ErrorMessage(
    "Ellipses cannot accompany other argument types in function type signature", codes.SYNTAX
)
TYPE_SIGNATURE_TOO_MANY_ARGS: Final = ErrorMessage(
    "Type signature has too many arguments", codes.SYNTAX
)
TYPE_SIGNATURE_TOO_FEW_ARGS: Final = ErrorMessage(
    "Type signature has too few arguments", codes.SYNTAX
)
ARG_CONSTRUCTOR_NAME_EXPECTED: Final = ErrorMessage("Expected arg constructor name", codes.SYNTAX)
ARG_CONSTRUCTOR_TOO_MANY_ARGS: Final = ErrorMessage(
    "Too many arguments for argument constructor", codes.SYNTAX
)
MULTIPLE_VALUES_FOR_NAME_KWARG: Final = ErrorMessage(
    '"{}" gets multiple values for keyword argument "name"', codes.SYNTAX
)
MULTIPLE_VALUES_FOR_TYPE_KWARG: Final = ErrorMessage(
    '"{}" gets multiple values for keyword argument "type"', codes.SYNTAX
)
ARG_CONSTRUCTOR_UNEXPECTED_ARG: Final = ErrorMessage(
    'Unexpected argument "{}" for argument constructor', codes.SYNTAX
)
ARG_NAME_EXPECTED_STRING_LITERAL: Final = ErrorMessage(
    "Expected string literal for argument name, got {}", codes.SYNTAX
)
EXCEPT_EXPR_NOTNAME_UNSUPPORTED: Final = ErrorMessage(
    'Sorry, "except <expr>, <anything but a name>" is not supported', codes.SYNTAX
)

# Nodes
DUPLICATE_ARGUMENT_IN_X: Final = ErrorMessage('Duplicate argument "{}" in {}')
POS_ARGS_BEFORE_DEFAULT_NAMED_OR_VARARGS: Final = ErrorMessage(
    "Required positional args may not appear after default, named or var args"
)
DEFAULT_ARGS_BEFORE_NAMED_OR_VARARGS: Final = ErrorMessage(
    "Positional default args may not appear after named or var args"
)
VAR_ARGS_BEFORE_NAMED_OR_VARARGS: Final = ErrorMessage(
    "Var args may not appear after named or var args"
)
KWARGS_MUST_BE_LAST: Final = ErrorMessage("A **kwargs argument must be the last argument")
MULTIPLE_KWARGS: Final = ErrorMessage("You may only have one **kwargs argument")

# Type Analysis
TYPEANAL_INTERNAL_ERROR: Final = ErrorMessage("Internal error (node is None, kind={})")
NOT_SUBSCRIPTABLE: Final = ErrorMessage('"{}" is not subscriptable')
NOT_SUBSCRIPTABLE_REPLACEMENT: Final = ErrorMessage('"{}" is not subscriptable, use "{}" instead')
INVALID_LOCATION_FOR_PARAMSPEC: Final = ErrorMessage(
    'Invalid location for ParamSpec "{}"'
)
UNBOUND_PARAMSPEC: Final = ErrorMessage('ParamSpec "{}" is unbound')
PARAMSPEC_USED_WITH_ARGS: Final = ErrorMessage('ParamSpec "{}" used with arguments')
NO_BOUND_TYPEVAR_GENERIC_ALIAS: Final = ErrorMessage(
    'Can\'t use bound type variable "{}" to define generic alias'
)
TYPEVAR_USED_WITH_ARGS: Final = ErrorMessage('Type variable "{}" used with arguments')
ONLY_OUTERMOST_FINAL: Final = ErrorMessage(
    "Final can be only used as an outermost qualifier in a variable annotation"
)
BUILTIN_TUPLE_NOT_DEFINED: Final = ErrorMessage('Name "tuple" is not defined')
SINGLE_TYPE_ARG: Final = ErrorMessage("{} must have exactly one type argument")
INVALID_NESTED_CLASSVAR: Final = ErrorMessage("Invalid type: ClassVar nested inside other type")
CLASSVAR_ATMOST_ONE_TYPE_ARG: Final = ErrorMessage(
    "ClassVar[...] must have at most one type argument"
)
ANNOTATED_SINGLE_TYPE_ARG: Final = ErrorMessage(
    "Annotated[...] must have exactly one type argument and at least one annotation"
)
REQUIRED_OUTSIDE_TYPEDDICT: Final = ErrorMessage(
    "Required[] can be only used in a TypedDict definition"
)
NOTREQUIRED_OUTSIDE_TYPEDDICT: Final = ErrorMessage(
    "NotRequired[] can be only used in a TypedDict definition"
)
REQUIRED_SINGLE_TYPE_ARG: Final = ErrorMessage("Required[] must have exactly one type argument")
NOTREQUIRED_SINGLE_TYPE_ARG: Final = ErrorMessage(
    "NotRequired[] must have exactly one type argument"
)
GENERIC_TUPLE_UNSUPPORTED: Final = ErrorMessage("Generic tuple types not supported")
GENERIC_TYPED_DICT_UNSUPPORTED: Final = ErrorMessage("Generic TypedDict types not supported")
VARIABLE_NOT_VALID_TYPE: Final = ErrorMessage(
    'Variable "{}" is not valid as a type', codes.VALID_TYPE
)
FUNCTION_NOT_VALID_TYPE: Final = ErrorMessage(
    'Function "{}" is not valid as a type', codes.VALID_TYPE
)
MODULE_NOT_VALID_TYPE: Final = ErrorMessage('Module "{}" is not valid as a type', codes.VALID_TYPE)
UNBOUND_TYPEVAR: Final = ErrorMessage('Type variable "{}" is unbound', codes.VALID_TYPE)
CANNOT_INTERPRET_AS_TYPE: Final = ErrorMessage(
    'Cannot interpret reference "{}" as a type', codes.VALID_TYPE
)
INVALID_TYPE: Final = ErrorMessage("Invalid type")
BRACKETED_EXPR_INVALID_TYPE: Final = ErrorMessage(
    'Bracketed expression "[...]" is not valid as a type'
)
ANNOTATION_SYNTAX_ERROR: Final = ErrorMessage("Syntax error in type annotation", codes.SYNTAX)
TUPLE_SINGLE_STAR_TYPE: Final = ErrorMessage("At most one star type allowed in a tuple")
INVALID_TYPE_USE_LITERAL: Final = ErrorMessage(
    "Invalid type: try using Literal[{}] instead?", codes.VALID_TYPE
)
INVALID_LITERAL_TYPE: Final = ErrorMessage(
    "Invalid type: {} literals cannot be used as a type", codes.VALID_TYPE
)
INVALID_ANNOTATION: Final = ErrorMessage("Invalid type comment or annotation", codes.VALID_TYPE)
PIPE_UNION_REQUIRES_PY310: Final = ErrorMessage("X | Y syntax for unions requires Python 3.10")
UNEXPECTED_ELLIPSIS: Final = ErrorMessage('Unexpected "..."')
CALLABLE_INVALID_FIRST_ARG: Final = ErrorMessage(
    'The first argument to Callable must be a list of types or "..."'
)
CALLABLE_INVALID_ARGS: Final = ErrorMessage(
    'Please use "Callable[[<parameters>], <return type>]" or "Callable"'
)
INVALID_ARG_CONSTRUCTOR: Final = ErrorMessage('Invalid argument constructor "{}"')
ARGS_SHOULD_NOT_HAVE_NAMES: Final = ErrorMessage("{} arguments should not have names")
LITERAL_AT_LEAST_ONE_ARG: Final = ErrorMessage("Literal[...] must have at least one parameter")
LITERAL_INDEX_CANNOT_BE_ANY: Final = ErrorMessage(
    'Parameter {} of Literal[...] cannot be of type "Any"'
)
LITERAL_INDEX_INVALID_TYPE: Final = ErrorMessage(
    'Parameter {} of Literal[...] cannot be of type "{}"'
)
LITERAL_INVALID_EXPRESSION: Final = ErrorMessage(
    "Invalid type: Literal[...] cannot contain arbitrary expressions"
)
LITERAL_INVALID_PARAMETER: Final = ErrorMessage("Parameter {} of Literal[...] is invalid")
TYPEVAR_BOUND_BY_OUTER_CLASS: Final = ErrorMessage('Type variable "{}" is bound by an outer class')
TYPE_ARG_COUNT_MISMATCH: Final = ErrorMessage('"{}" expects {}, but {} given', codes.TYPE_ARG)
TYPE_ALIAS_ARG_COUNT_MISMATCH: Final = ErrorMessage(
    "Bad number of arguments for type alias, expected: {}, given: {}"
)
INVALID_TYPE_ALIAS: Final = ErrorMessage("Invalid type alias: expression is not a valid type")
CANNOT_RESOLVE_TYPE: Final = ErrorMessage('Cannot resolve {} "{}" (possible cyclic definition)')
UNION_SYNTAX_REQUIRES_PY310: Final = ErrorMessage("X | Y syntax for unions requires Python 3.10")

# Super
TOO_MANY_ARGS_FOR_SUPER: Final = ErrorMessage('Too many arguments for "super"')
TOO_FEW_ARGS_FOR_SUPER: Final = ErrorMessage('Too few arguments for "super"', codes.CALL_ARG)
SUPER_WITH_SINGLE_ARG_NOT_SUPPORTED: Final = ErrorMessage(
    '"super" with a single argument not supported'
)
UNSUPPORTED_ARG_1_FOR_SUPER: Final = ErrorMessage('Unsupported argument 1 for "super"')
UNSUPPORTED_ARG_2_FOR_SUPER: Final = ErrorMessage('Unsupported argument 2 for "super"')
SUPER_VARARGS_NOT_SUPPORTED: Final = ErrorMessage('Varargs not supported with "super"')
SUPER_POSITIONAL_ARGS_REQUIRED: Final = ErrorMessage('"super" only accepts positional arguments')
SUPER_ARG_2_NOT_INSTANCE_OF_ARG_1: Final = ErrorMessage(
    'Argument 2 for "super" not an instance of argument 1'
)
TARGET_CLASS_HAS_NO_BASE_CLASS: Final = ErrorMessage("Target class has no base class")
SUPER_OUTSIDE_OF_METHOD_NOT_SUPPORTED: Final = ErrorMessage(
    "super() outside of a method is not supported"
)
SUPER_ENCLOSING_POSITIONAL_ARGS_REQUIRED: Final = ErrorMessage(
    "super() requires one or more positional arguments in enclosing function"
)

# Self-type
MISSING_OR_INVALID_SELF_TYPE: Final = ErrorMessage(
    "Self argument missing for a non-static method (or an invalid type for self)"
)
ERASED_SELF_TYPE_NOT_SUPERTYPE: Final = ErrorMessage(
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
CLASS_VAR_WITH_TYPEVARS: Final = 'ClassVar cannot contain type variables'
CLASS_VAR_OUTSIDE_OF_CLASS: Final = (
    'ClassVar can only be used for assignments in class body'
)

# Protocol
RUNTIME_PROTOCOL_EXPECTED: Final = ErrorMessage(
    "Only @runtime_checkable protocols can be used with instance and class checks"
)
CANNOT_INSTANTIATE_PROTOCOL: Final = ErrorMessage('Cannot instantiate protocol class "{}"')
TOO_MANY_UNION_COMBINATIONS: Final = ErrorMessage(
    "Not all union combinations were tried because there are too many unions"
)

CONTIGUOUS_ITERABLE_EXPECTED: Final = ErrorMessage("Contiguous iterable with same type expected")
ITERABLE_TYPE_EXPECTED: Final = ErrorMessage("Invalid type '{}' for *expr (iterable expected)")
TYPE_GUARD_POS_ARG_REQUIRED: Final = ErrorMessage("Type guard requires positional argument")

# Match Statement
MISSING_MATCH_ARGS: Final = 'Class "{}" doesn\'t define "__match_args__"'
OR_PATTERN_ALTERNATIVE_NAMES: Final = "Alternative patterns bind different names"
CLASS_PATTERN_GENERIC_TYPE_ALIAS: Final = (
    "Class pattern class must not be a type alias with type parameters"
)
CLASS_PATTERN_TYPE_REQUIRED: Final = 'Expected type in class pattern; found "{}"'
CLASS_PATTERN_TOO_MANY_POSITIONAL_ARGS: Final = "Too many positional patterns for class pattern"
CLASS_PATTERN_KEYWORD_MATCHES_POSITIONAL: Final = (
    'Keyword "{}" already matches a positional pattern'
)
CLASS_PATTERN_DUPLICATE_KEYWORD_PATTERN: Final = 'Duplicate keyword pattern "{}"'
CLASS_PATTERN_UNKNOWN_KEYWORD: Final = 'Class "{}" has no attribute "{}"'
MULTIPLE_ASSIGNMENTS_IN_PATTERN: Final = 'Multiple assignments to name "{}" in pattern'
