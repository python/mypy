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
CANNOT_ASSIGN_TO_METHOD: Final = ErrorMessage("Cannot assign to a method", codes.ASSIGNMENT)
CANNOT_ASSIGN_TO_TYPE: Final = ErrorMessage("Cannot assign to a type")
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
BARE_GENERIC: Final = ErrorMessage("Missing type parameters for generic type {}", codes.TYPE_ARG)
IMPLICIT_GENERIC_ANY_BUILTIN: Final = ErrorMessage(
    'Implicit generic "Any". Use "{}" and specify generic parameters', codes.TYPE_ARG
)

# TypeVar
INCOMPATIBLE_TYPEVAR_VALUE: Final = 'Value of type variable "{}" of {} cannot be {}'
CANNOT_USE_TYPEVAR_AS_EXPRESSION: Final = 'Type variable "{}.{}" cannot be used as an expression'
INVALID_TYPEVAR_AS_TYPEARG: Final = 'Type variable "{}" not valid as type argument value for "{}"'
INVALID_TYPEVAR_ARG_BOUND: Final = 'Type argument {} of "{}" must be a subtype of {}'
INVALID_TYPEVAR_ARG_VALUE: Final = 'Invalid type argument value for "{}"'
TYPEVAR_VARIANCE_DEF: Final = ErrorMessage('TypeVar "{}" may only be a literal bool')
TYPEVAR_BOUND_MUST_BE_TYPE: Final = ErrorMessage('TypeVar "bound" must be a type')
TYPEVAR_UNEXPECTED_ARGUMENT: Final = ErrorMessage('Unexpected argument to "TypeVar()"')

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

# strings from messages.py
MEMBER_NOT_ASSIGNABLE: Final = ErrorMessage('Member "{}" is not assignable')
UNSUPPORTED_OPERAND_FOR_IN: Final = ErrorMessage(
    "Unsupported right operand type for in ({})", codes.OPERATOR
)
UNSUPPORTED_OPERAND_FOR_UNARY_MINUS: Final = ErrorMessage(
    "Unsupported operand type for unary - ({})", codes.OPERATOR
)
UNSUPPORTED_OPERAND_FOR_UNARY_PLUS: Final = ErrorMessage(
    "Unsupported operand type for unary + ({})", codes.OPERATOR
)
UNSUPPORTED_OPERAND_FOR_INVERT: Final = ErrorMessage(
    "Unsupported operand type for ~ ({})", codes.OPERATOR
)
TYPE_NOT_GENERIC_OR_INDEXABLE: Final = ErrorMessage("The type {} is not generic and not indexable")
TYPE_NOT_INDEXABLE: Final = ErrorMessage("Value of type {} is not indexable", codes.INDEX)
UNSUPPORTED_TARGET_INDEXED_ASSIGNMENT: Final = ErrorMessage(
    "Unsupported target for indexed assignment ({})", codes.INDEX
)
CALLING_FUNCTION_OF_UNKNOWN_TYPE: Final = ErrorMessage(
    "Cannot call function of unknown type", codes.OPERATOR
)
TYPE_NOT_CALLABLE: Final = ErrorMessage("{} not callable", codes.OPERATOR)
TYPE_NOT_CALLABLE_2: Final = ErrorMessage("{} not callable")
TYPE_HAS_NO_ATTRIBUTE_X_MAYBE_Y: Final = ErrorMessage(
    '{} has no attribute "{}"; maybe {}?{}', codes.ATTR_DEFINED
)
TYPE_HAS_NO_ATTRIBUTE_X: Final = ErrorMessage('{} has no attribute "{}"{}', codes.ATTR_DEFINED)
ITEM_HAS_NO_ATTRIBUTE_X: Final = ErrorMessage(
    'Item {} of {} has no attribute "{}"{}', codes.UNION_ATTR
)
TYPEVAR_UPPER_BOUND_HAS_NO_ATTRIBUTE: Final = ErrorMessage(
    'Item {} of the upper bound {} of type variable {} has no attribute "{}"{}', codes.UNION_ATTR
)
UNSUPPORTED_OPERANDS_LIKELY_UNION: Final = ErrorMessage(
    "Unsupported operand types for {} (likely involving Union)", codes.OPERATOR
)
UNSUPPORTED_OPERANDS: Final = ErrorMessage(
    "Unsupported operand types for {} ({} and {})", codes.OPERATOR
)
UNSUPPORTED_LEFT_OPERAND_TYPE_UNION: Final = ErrorMessage(
    "Unsupported left operand type for {} (some union)", codes.OPERATOR
)
UNSUPPORTED_LEFT_OPERAND_TYPE: Final = ErrorMessage(
    "Unsupported left operand type for {} ({})", codes.OPERATOR
)
UNTYPED_FUNCTION_CALL: Final = ErrorMessage(
    "Call to untyped function {} in typed context", codes.NO_UNTYPED_CALL
)
INVALID_INDEX_TYPE: Final = ErrorMessage(
    "Invalid index type {} for {}; expected type {}", codes.INDEX
)
TARGET_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    "{} (expression has type {}, target has type {})", codes.ASSIGNMENT
)
VALUE_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    'Value of "{}" has incompatible type {}; expected {}', codes.ARG_TYPE
)
ARGUMENT_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    'Argument {} {}has incompatible type {}; expected {}', codes.ARG_TYPE
)
TYPEDDICT_VALUE_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    'Value of "{}" has incompatible type {}; expected {}', codes.TYPEDDICT_ITEM
)
TYPEDDICT_ARGUMENT_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    'Argument {} {}has incompatible type {}; expected {}', codes.TYPEDDICT_ITEM
)
LIST_ITEM_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    "{} item {} has incompatible type {}; expected {}", codes.LIST_ITEM
)
DICT_ENTRY_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    "{} entry {} has incompatible type {}: {}; expected {}: {}", codes.DICT_ITEM
)
LIST_COMP_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    "List comprehension has incompatible type List[{}]; expected List[{}]"
)
SET_COMP_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    "Set comprehension has incompatible type Set[{}]; expected Set[{}]"
)
DICT_COMP_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    "{} expression in dictionary comprehension has incompatible type {}; expected type {}"
)
GENERATOR_INCOMPATIBLE_TYPE: Final = ErrorMessage(
    "Generator has incompatible item type {}; expected {}"
)
MULTIPLE_VALUES_FOR_KWARG: Final = ErrorMessage(
    '{} gets multiple values for keyword argument "{}"'
)
NO_RETURN_VALUE: Final = ErrorMessage("{} does not return a value", codes.FUNC_RETURNS_VALUE)
FUNCTION_NO_RETURN_VALUE: Final = ErrorMessage(
    "Function does not return a value", codes.FUNC_RETURNS_VALUE
)
UNDERSCORE_FUNCTION_CALL: Final = ErrorMessage('Calling function named "_" is not allowed')
READING_DELETED_VALUE: Final = ErrorMessage("Trying to read deleted variable{}")
ASSIGNMENT_OUTSIDE_EXCEPT: Final = ErrorMessage("Assignment to variable{} outside except: block")
OVERLOADS_REQUIRE_ATLEAST_ONE_ARG: Final = ErrorMessage(
    "All overload variants{} require at least one argument"
)
UNPACK_MORE_THAN_ONE_VALUE_NEEDED: Final = ErrorMessage(
    "Need more than 1 value to unpack ({} expected)"
)
UNPACK_TOO_FEW_VALUES: Final = ErrorMessage("Need more than {} values to unpack ({} expected)")
UNPACK_TOO_MANY_VALUES: Final = ErrorMessage(
    "Too many values to unpack ({} expected, {} provided)"
)
UNPACKING_STRINGS_DISALLOWED: Final = ErrorMessage("Unpacking a string is disallowed")
TYPE_NOT_ITERABLE: Final = ErrorMessage('{} object is not iterable')
INCOMPATIBLE_OPERATOR_ASSIGNMENT: Final = ErrorMessage(
    "Result type of {} incompatible in assignment"
)
OVERLOAD_SIGNATURE_INCOMPATIBLE: Final = ErrorMessage(
    'Signature of "{}" incompatible with {}', codes.OVERRIDE
)
SIGNATURE_INCOMPATIBLE_WITH_SUPERTYPE: Final = ErrorMessage(
    'Signature of "{}" incompatible with {}', codes.OVERRIDE
)
ARG_INCOMPATIBLE_WITH_SUPERTYPE: Final = ErrorMessage(
    'Argument {} of "{}" is incompatible with {}; supertype defines the argument type as "{}"',
    codes.OVERRIDE,
)
RETURNTYPE_INCOMPATIBLE_WITH_SUPERTYPE: Final = ErrorMessage(
    'Return type {} of "{}" incompatible with return type {} in {}', codes.OVERRIDE
)
TYPE_APPLICATION_ON_NON_GENERIC_TYPE: Final = ErrorMessage(
    "Type application targets a non-generic function or class"
)
TYPE_APPLICATION_TOO_MANY_TYPES: Final = ErrorMessage(
    "Type application has too many types ({} expected)"
)
TYPE_APPLICATION_TOO_FEW_TYPES: Final = ErrorMessage(
    "Type application has too few types ({} expected)"
)
CANNOT_INFER_TYPE_ARG_NAMED_FUNC: Final = ErrorMessage("Cannot infer type argument {} of {}")
CANNOT_INFER_TYPE_ARG_FUNC: Final = ErrorMessage("Cannot infer function type argument")
INVALID_VAR_ARGS: Final = ErrorMessage("List or tuple expected as variable arguments")
KEYWORDS_MUST_BE_STRINGS: Final = ErrorMessage("Keywords must be strings")
ARG_MUST_BE_MAPPING: Final = ErrorMessage("Argument after ** must be a mapping{}", codes.ARG_TYPE)
MEMBER_UNDEFINED_IN_SUPERCLASS: Final = ErrorMessage('"{}" undefined in superclass')
SUPER_ARG_EXPECTED_TYPE: Final = ErrorMessage(
    'Argument 1 for "super" must be a type object; got {}', codes.ARG_TYPE
)
FORMAT_STR_TOO_FEW_ARGS: Final = ErrorMessage(
    "Not enough arguments for format string", codes.STRING_FORMATTING
)
FORMAT_STR_TOO_MANY_ARGS: Final = ErrorMessage(
    "Not all arguments converted during string formatting", codes.STRING_FORMATTING
)
FORMAT_STR_UNSUPPORTED_CHAR: Final = ErrorMessage(
    'Unsupported format character "{}"', codes.STRING_FORMATTING
)
STRING_INTERPOLATION_WITH_STAR_AND_KEY: Final = ErrorMessage(
    "String interpolation contains both stars and mapping keys", codes.STRING_FORMATTING
)
FORMAT_STR_INVALID_CHR_CONVERSION_RANGE: Final = ErrorMessage(
    '"{}c" requires an integer in range(256) or a single byte', codes.STRING_FORMATTING
)
FORMAT_STR_INVALID_CHR_CONVERSION: Final = ErrorMessage(
    '"{}c" requires int or char', codes.STRING_FORMATTING
)
KEY_NOT_IN_MAPPING: Final = ErrorMessage('Key "{}" not found in mapping', codes.STRING_FORMATTING)
FORMAT_STR_MIXED_KEYS_AND_NON_KEYS: Final = ErrorMessage(
    "String interpolation mixes specifier with and without mapping keys", codes.STRING_FORMATTING
)
CANNOT_DETERMINE_TYPE: Final = ErrorMessage('Cannot determine type of "{}"', codes.HAS_TYPE)
CANNOT_DETERMINE_TYPE_IN_BASE: Final = ErrorMessage(
    'Cannot determine type of "{}" in base class "{}"'
)
DOES_NOT_ACCEPT_SELF: Final = ErrorMessage(
    'Attribute function "{}" with type {} does not accept self argument'
)
INCOMPATIBLE_SELF_ARG: Final = ErrorMessage('Invalid self argument {} to {} "{}" with type {}')
INCOMPATIBLE_CONDITIONAL_FUNCS: Final = ErrorMessage(
    "All conditional function variants must have identical signatures"
)
CANNOT_INSTANTIATE_ABSTRACT_CLASS: Final = ErrorMessage(
    'Cannot instantiate abstract class "{}" with abstract attribute{} {}', codes.ABSTRACT
)
INCOMPATIBLE_BASE_CLASS_DEFNS: Final = ErrorMessage(
    'Definition of "{}" in base class "{}" is incompatible with definition in base class "{}"'
)
CANNOT_ASSIGN_TO_CLASSVAR: Final = ErrorMessage(
    'Cannot assign to class variable "{}" via instance'
)
CANNOT_OVERRIDE_TO_FINAL: Final = ErrorMessage(
    'Cannot override writable attribute "{}" with a final one'
)
CANNOT_OVERRIDE_FINAL: Final = ErrorMessage(
    'Cannot override final attribute "{}" (previously declared in base class "{}")'
)
CANNOT_ASSIGN_TO_FINAL: Final = ErrorMessage('Cannot assign to final {} "{}"')
PROTOCOL_MEMBER_CANNOT_BE_FINAL: Final = ErrorMessage("Protocol member cannot be final")
FINAL_WITHOUT_VALUE: Final = ErrorMessage("Final name must be initialized with a value")
PROPERTY_IS_READ_ONLY: Final = ErrorMessage('Property "{}" defined in "{}" is read-only')
NON_OVERLAPPING_COMPARISON: Final = ErrorMessage(
    "Non-overlapping {} check ({} type: {}, {} type: {})", codes.COMPARISON_OVERLAP
)
OVERLOAD_INCONSISTENT_DECORATOR_USE: Final = ErrorMessage(
    'Overload does not consistently use the "@{}" decorator on all function signatures.'
)
OVERLOAD_INCOMPATIBLE_RETURN_TYPES: Final = ErrorMessage(
    "Overloaded function signatures {} and {} overlap with incompatible return types"
)
OVERLOAD_SIGNATURE_WILL_NEVER_MATCH: Final = ErrorMessage(
    "Overloaded function signature {index2} will never be matched: signature {index1}'s parameter"
    " type(s) are the same or broader"
)
OVERLOAD_INCONSISTENT_TYPEVARS: Final = ErrorMessage(
    "Overloaded function implementation cannot satisfy signature {} due to inconsistencies in how"
    " they use type variables"
)
OVERLOAD_INCONSISTENT_ARGS: Final = ErrorMessage(
    "Overloaded function implementation does not accept all possible arguments of signature {}"
)
OVERLOAD_INCONSISTENT_RETURN_TYPE: Final = ErrorMessage(
    "Overloaded function implementation cannot produce return type of signature {}"
)
OPERATOR_METHOD_SIGNATURE_OVERLAP: Final = ErrorMessage(
    'Signatures of "{}" of "{}" and "{}" of {} are unsafely overlapping'
)
FORWARD_OPERATOR_NOT_CALLABLE: Final = ErrorMessage('Forward operator "{}" is not callable')
INCOMPATIBLE_SIGNATURES: Final = ErrorMessage('Signatures of "{}" and "{}" are incompatible')
INVALID_YIELD_FROM: Final = ErrorMessage('"yield from" can\'t be applied to {}')
INVALID_SIGNATURE: Final = ErrorMessage('Invalid signature {}')
INVALID_SIGNATURE_SPECIAL: Final = ErrorMessage('Invalid signature {} for "{}"')
UNSUPPORTED_TYPE_TYPE: Final = ErrorMessage('Cannot instantiate type "Type[{}]"')
REDUNDANT_CAST: Final = ErrorMessage("Redundant cast to {}", codes.REDUNDANT_CAST)
UNFOLLOWED_IMPORT: Final = ErrorMessage(
    "{} becomes {} due to an unfollowed import", codes.NO_ANY_UNIMPORTED
)
ANNOTATION_NEEDED: Final = ErrorMessage('Need type {} for "{}"{}', codes.VAR_ANNOTATED)
NO_EXPLICIT_ANY: Final = ErrorMessage('Explicit "Any" is not allowed')
TYPEDDICT_MISSING_KEYS: Final = ErrorMessage("Missing {} for TypedDict {}", codes.TYPEDDICT_ITEM)
TYPEDDICT_EXTRA_KEYS: Final = ErrorMessage("Extra {} for TypedDict {}", codes.TYPEDDICT_ITEM)
TYPEDDICT_UNEXPECTED_KEYS: Final = ErrorMessage("Unexpected TypedDict {}")
TYPEDDICT_KEYS_MISMATCH: Final = ErrorMessage("Expected {} but found {}", codes.TYPEDDICT_ITEM)
TYPEDDICT_KEY_STRING_LITERAL_EXPECTED: Final = ErrorMessage(
    "TypedDict key must be a string literal; expected one of {}"
)
TYPEDDICT_KEY_INVALID: Final = ErrorMessage(
    '"{}" is not a valid TypedDict key; expected one of {}'
)
TYPEDDICT_UNKNOWN_KEY: Final = ErrorMessage('TypedDict {} has no key "{}"', codes.TYPEDDICT_ITEM)
TYPEDDICT_AMBIGUOUS_TYPE: Final = ErrorMessage(
    "Type of TypedDict is ambiguous, could be any of ({})"
)
TYPEDDICT_CANNOT_DELETE_KEY: Final = ErrorMessage('TypedDict key "{}" cannot be deleted')
TYPEDDICT_NAMED_CANNOT_DELETE_KEY: Final = ErrorMessage(
    'Key "{}" of TypedDict {} cannot be deleted'
)
TYPEDDICT_INCONSISTENT_SETDEFAULT_ARGS: Final = ErrorMessage(
    'Argument 2 to "setdefault" of "TypedDict" has incompatible type {}; expected {}',
    codes.TYPEDDICT_ITEM,
)
PARAMETERIZED_GENERICS_DISALLOWED: Final = ErrorMessage(
    "Parameterized generics cannot be used with class or instance checks"
)
EXPR_HAS_ANY_TYPE: Final = ErrorMessage('Expression has type "Any"')
EXPR_CONTAINS_ANY_TYPE: Final = ErrorMessage('Expression type contains "Any" (has type {})')
INCORRECTLY_RETURNING_ANY: Final = ErrorMessage(
    "Returning Any from function declared to return {}", codes.NO_ANY_RETURN
)
INVALID_EXIT_RETURN_TYPE: Final = ErrorMessage(
    '"bool" is invalid as return type for "__exit__" that always returns False', codes.EXIT_RETURN
)
UNTYPED_DECORATOR_FUNCTION: Final = ErrorMessage(
    "Function is untyped after decorator transformation"
)
DECORATED_TYPE_CONTAINS_ANY: Final = ErrorMessage(
    'Type of decorated function contains type "Any" ({})'
)
DECORATOR_MAKES_FUNCTION_UNTYPED: Final = ErrorMessage(
    'Untyped decorator makes function "{}" untyped'
)
CONCRETE_ONLY_ASSIGN: Final = ErrorMessage(
    "Can only assign concrete classes to a variable of type {}"
)
EXPECTED_CONCRETE_CLASS: Final = ErrorMessage(
    "Only concrete class can be given where {} is expected"
)
CANNOT_USE_FUNCTION_WITH_TYPE: Final = ErrorMessage("Cannot use {}() with {} type")
ISSUBCLASS_ONLY_NON_METHOD_PROTOCOL: Final = ErrorMessage(
    "Only protocols that don't have non-method members can be used with issubclass()"
)
UNREACHABLE_STATEMENT: Final = ErrorMessage("Statement is unreachable", codes.UNREACHABLE)
UNREACHABLE_RIGHT_OPERAND: Final = ErrorMessage(
    'Right operand of "{}" is never evaluated', codes.UNREACHABLE
)
EXPR_IS_ALWAYS_BOOL: Final = ErrorMessage("{} is always {}", codes.REDUNDANT_EXPR)
IMPOSSIBLE_SUBCLASS: Final = ErrorMessage("Subclass of {} cannot exist: would have {}")

# Semantic Analysis
METHOD_ATLEAST_ONE_ARG: Final = ErrorMessage('Method must have at least one argument')
OVERLOAD_IMPLEMENTATION_IN_STUB: Final = ErrorMessage(
    "An implementation for an overloaded function is not allowed in a stub file"
)
OVERLOAD_IMPLEMENTATION_LAST: Final = ErrorMessage(
    "The implementation for an overloaded function must come last"
)
OVERLOAD_IMPLEMENTATION_REQUIRED: Final = ErrorMessage(
    "An overloaded function outside a stub file must have an implementation",
    codes.NO_OVERLOAD_IMPL,
)
FINAL_DEC_ON_OVERLOAD_ONLY: Final = ErrorMessage(
    "@final should be applied only to overload implementation"
)
FINAL_DEC_STUB_FIRST_OVERLOAD: Final = ErrorMessage(
    "In a stub file @final must be applied only to the first overload"
)
DECORATED_PROPERTY_UNSUPPORTED: Final = ErrorMessage("Decorated property not supported")
UNEXPECTED_PROPERTY_DEFN: Final = ErrorMessage('Unexpected definition for property "{}"')
TOO_MANY_ARGS: Final = ErrorMessage('Too many arguments')
FINAL_DEC_WITH_METHODS_ONLY: Final = ErrorMessage(
    "@final cannot be used with non-method functions"
)
DECORATOR_USED_WITH_NON_METHOD: Final = ErrorMessage('"{}" used with a non-method')
CANNOT_USE_FINAL_DEC_WITH_TYPEDDICT: Final = ErrorMessage("@final cannot be used with TypedDict")
RUNTIME_CHECKABLE_WITH_NON_PROPERTY: Final = ErrorMessage(
    '@runtime_checkable can only be used with protocol classes'
)
BASES_MUST_HAVE_SINGLE_GENERIC_OR_PROTOCOL: Final = ErrorMessage(
    'Only single Generic[...] or Protocol[...] can be in bases'
)
DUPLICATE_TYPEVARS_IN_GENERIC_OR_PROTOCOL: Final = ErrorMessage(
    "Duplicate type variables in Generic[...] or Protocol[...]"
)
GENERIC_PROTOCOL_NOT_ALL_TYPEVARS: Final = ErrorMessage(
    "If Generic[...] or Protocol[...] is present it should list all type variables"
)
FREE_TYPEVAR_EXPECTED: Final = ErrorMessage('Free type variable expected in {}[...]')
UNSUPPORTED_DYNAMIC_BASE_CLASS: Final = ErrorMessage('Unsupported dynamic base class{}')
INVALID_BASE_CLASS: Final = ErrorMessage('Invalid base class{}')
CANNOT_SUBCLASS_NEWTYPE: Final = ErrorMessage('Cannot subclass "NewType"')
CANNOT_SUBCLASS_ANY_NAMED: Final = ErrorMessage('Class cannot subclass "{}" (has type "Any")')
CANNOT_SUBCLASS_ANY: Final = ErrorMessage('Class cannot subclass value of type "Any"')
INCOMPATIBLE_BASES: Final = ErrorMessage("Class has two incompatible bases derived from tuple")
CANNOT_DETERMINE_MRO: Final = ErrorMessage(
    'Cannot determine consistent method resolution order (MRO) for "{}"'
)
INNER_METACLASS_UNSUPPORTED: Final = ErrorMessage(
    "Metaclasses defined as inner classes are not supported"
)
MULTIPLE_METACLASSES: Final = ErrorMessage("Multiple metaclass definitions")
INHERITANCE_CYCLE: Final = ErrorMessage('Cycle in inheritance hierarchy')
NAMED_INVALID_BASE_CLASS: Final = ErrorMessage('"{}" is not a valid base class')
DUPLICATE_BASE_CLASS: Final = ErrorMessage('Duplicate base class "{}"')
UNSUPPORTED_NAMED_DYNAMIC_BASE_CLASS: Final = ErrorMessage(
    'Dynamic metaclass not supported for "{}"'
)
INVALID_METACLASS: Final = ErrorMessage('Invalid metaclass "{}"')
METACLASS_MUST_INHERIT_TYPE: Final = ErrorMessage(
    'Metaclasses not inheriting from "type" are not supported'
)
INCONSISTENT_METACLAS_STRUCTURE: Final = ErrorMessage('Inconsistent metaclass structure for "{}"')
NO_GENERIC_ENUM: Final = ErrorMessage("Enum class cannot be generic")
MODULE_MISSING_ATTIRBUTE: Final = ErrorMessage(
    'Module "{}" has no attribute "{}"{}', codes.ATTR_DEFINED
)
NO_IMPLICIT_REEXPORT: Final = ErrorMessage(
    'Module "{}" does not explicitly export attribute "{}"; implicit reexport disabled',
    codes.ATTR_DEFINED
)
INCORRECT_RELATIVE_IMPORT: Final = ErrorMessage("Relative import climbs too many namespaces")
INVALID_TYPE_ALIAS_TARGET: Final = ErrorMessage(
    'Type variable "{}" is invalid as target for type alias'
)
NAMEDTUPLE_ATTRIBUTE_UNSUPPORTED: Final = ErrorMessage(
    "NamedTuple type as an attribute is not supported"
)
NAMEDTUPLE_INCORRECT_FIRST_ARG: Final = ErrorMessage(
    'First argument to namedtuple() should be "{}", not "{}"', codes.NAME_MATCH
)
TYPEDDICT_ATTRIBUTE_UNSUPPORTED: Final = ErrorMessage(
    "TypedDict type as attribute is not supported"
)
FINAL_ATMOST_ONE_ARG: Final = ErrorMessage("Final[...] takes at most one type argument")
FINAL_INITIALIZER_REQUIRED: Final = ErrorMessage(
    "Type in Final[...] can only be omitted if there is an initializer"
)
FINAL_CLASSVAR_DISALLOWED: Final = ErrorMessage(
    "Variable should not be annotated with both ClassVar and Final"
)
INVALID_FINAL: Final = ErrorMessage("Invalid final declaration")
FINAL_IN_LOOP_DISALLOWED: Final = ErrorMessage("Cannot use Final inside a loop")
FINAL_ONLY_ON_SELF_MEMBER: Final = ErrorMessage(
    "Final can be only applied to a name or an attribute on self"
)
FINAL_ONLY_IN_CLASS_BODY_OR_INIT: Final = ErrorMessage(
    "Can only declare a final attribute in class body or __init__"
)
PROTOCOL_MEMBERS_MUST_BE_TYPED: Final = ErrorMessage(
    'All protocol members must have explicitly declared types'
)
MULTIPLE_TYPES_WITHOUT_EXPLICIT_TYPE: Final = ErrorMessage(
    'Cannot assign multiple types to name "{}" without an explicit "Type[...]" annotation'
)
TYPE_DECLARATION_IN_ASSIGNMENT: Final = ErrorMessage(
    'Type cannot be declared in assignment to non-self attribute'
)
UNEXPECTED_TYPE_DECLARATION: Final = ErrorMessage('Unexpected type declaration')
STAR_ASSIGNMENT_TARGET_LIST_OR_TUPLE: Final = ErrorMessage(
    'Starred assignment target must be in a list or tuple'
)
INVALID_ASSIGNMENT_TARGET: Final = ErrorMessage('Invalid assignment target')
REDEFINE_AS_FINAL: Final = ErrorMessage("Cannot redefine an existing name as final")
TWO_STAR_EXPRESSIONS_IN_ASSIGNMENT: Final = ErrorMessage('Two starred expressions in assignment')
PROTOCOL_ASSIGNMENT_TO_SELF: Final = ErrorMessage(
    "Protocol members cannot be defined via assignment to self"
)
STARTYPE_ONLY_FOR_STAR_EXPRESSIONS: Final = ErrorMessage(
    'Star type only allowed for starred expressions'
)
INCOMPATIBLE_TUPLE_ITEM_COUNT: Final = ErrorMessage('Incompatible number of tuple items')
TUPLE_TYPE_EXPECTED: Final = ErrorMessage('Tuple type expected for multiple variables')
CANNOT_DECLARE_TYPE_OF_TYPEVAR: Final = ErrorMessage("Cannot declare the type of a type variable")
REDEFINE_AS_TYPEVAR: Final = ErrorMessage('Cannot redefine "{}" as a type variable')
TYPEVAR_CALL_TOO_FEW_ARGS: Final = ErrorMessage("Too few arguments for {}()")
TYPEVAR_CALL_EXPECTED_STRING_LITERAL: Final = ErrorMessage(
    "{}() expects a string literal as first argument"
)
TYPEVAR_NAME_ARG_MISMATCH: Final = ErrorMessage(
    'String argument 1 "{}" to {}(...) does not match variable name "{}"'
)
TYPEVAR_UNEXPECTED_ARG: Final = ErrorMessage("Unexpected argument to TypeVar()")
TYPEVAR_UNEXPECTED_ARG_NAMED: Final = ErrorMessage('Unexpected argument to "TypeVar()": "{}"')
TYPEVAR_VALUE_WITH_BOUND_DISALLOWED: Final = ErrorMessage(
    "TypeVar cannot have both values and an upper bound"
)
TYPEVAR_VALUES_ARG_UNSUPPORTED: Final = ErrorMessage('TypeVar "values" argument not supported')
USE_NEW_TYPEVAR_SYNTAX: Final = ErrorMessage(
    "Use TypeVar('T', t, ...) instead of TypeVar('T', values=(t, ...))"
)
TYPEVAR_COVARIANT_AND_CONTRAVARIANT: Final = ErrorMessage(
    "TypeVar cannot be both covariant and contravariant"
)
TYPEVAR_SINGLE_CONSTRAINT: Final = ErrorMessage("TypeVar cannot have only a single constraint")
CANNOT_DECLARE_TYPE_OF_PARAMSPEC: Final = ErrorMessage(
    "Cannot declare the type of a parameter specification"
)
TYPE_EXPECTED: Final = ErrorMessage('Type expected')
CLASSVAR_OUTSIDE_CLASS_BODY: Final = ErrorMessage(
    'ClassVar can only be used for assignments in class body'
)
MULTIPLE_MODULE_ASSIGNMENT: Final = ErrorMessage(
    'Cannot assign multiple modules to name "{}" without explicit "types.ModuleType" annotation'
)
DELETABLE_MUST_BE_WITH_LIST_OR_TUPLE: Final = ErrorMessage(
    '"__deletable__" must be initialized with a list or tuple expression'
)
DELETABLE_EXPECTED_STRING_LITERAL: Final = ErrorMessage(
    'Invalid "__deletable__" item; string literal expected'
)
RETURN_OUTSIDE_FUNCTION: Final = ErrorMessage('"return" outside function')
BREAK_OUTSIDE_LOOP: Final = ErrorMessage('"break" outside loop')
CONTINUE_OUTSIDE_LOOP: Final = ErrorMessage('"continue" outside loop')
WITH_HAS_NO_TARGETS: Final = ErrorMessage('Invalid type comment: "with" statement has no targets')
WITH_INCOMPATIBLE_TARGET_COUNT: Final = ErrorMessage(
    'Incompatible number of types for "with" targets'
)
WITH_MULTIPLE_TYPES_EXPECTED: Final = ErrorMessage(
    'Multiple types expected for multiple "with" targets'
)
INVALID_DELETE_TARGET: Final = ErrorMessage('Invalid delete target')
NAME_IS_NONLOCAL_AND_GLOBAL: Final = ErrorMessage('Name "{}" is nonlocal and global')
NONLOCAL_AT_MODULE_LEVEL: Final = ErrorMessage("nonlocal declaration not allowed at module level")
NONLOCAL_NO_BINDING_FOUND: Final = ErrorMessage('No binding for nonlocal "{}" found')
LOCAL_DEFINITION_BEFORE_NONLOCAL: Final = ErrorMessage(
    'Name "{}" is already defined in local scope before nonlocal declaration'
)
NAME_ONLY_VALID_IN_TYPE_CONTEXT: Final = ErrorMessage(
    '"{}" is a type variable and only valid in type context'
)
SUPER_OUTSIDE_CLASS: Final = ErrorMessage('"super" used outside class')
INVALID_STAR_EXPRESSION: Final = ErrorMessage(
    'Can use starred expression only as assignment target'
)
YIELD_OUTSIDE_FUNC: Final = ErrorMessage('"yield" outside function')
YIELD_FROM_OUTSIDE_FUNC: Final = ErrorMessage('"yield from" outside function')
YIELD_IN_ASYNC_FUNC: Final = ErrorMessage('"yield" in async function')
YIELD_FROM_IN_ASYNC_FUNC: Final = ErrorMessage('"yield from" in async function')
CAST_TARGET_IS_NOT_TYPE: Final = ErrorMessage('Cast target is not a type')
ANY_CALL_UNSUPPORTED: Final = ErrorMessage(
    'Any(...) is no longer supported. Use cast(Any, ...) instead'
)
PROMOTE_ARG_EXPECTED_TYPE: Final = ErrorMessage('Argument 1 to _promote is not a type')
ARG_COUNT_MISMATCH: Final = ErrorMessage('"{}" expects {} argument{}')
POS_ARG_COUNT_MISMATCH: Final = ErrorMessage('"{}" must be called with {} positional argument{}')
TYPE_EXPECTED_IN_BRACKETS: Final = ErrorMessage('Type expected within [...]')
AWAIT_OUTSIDE_FUNC: Final = ErrorMessage('"await" outside function')
AWAIT_OUTSIDE_COROUTINE: Final = ErrorMessage('"await" outside coroutine ("async def")')
CANNOT_RESOLVE_NAME: Final = ErrorMessage('Cannot resolve {} "{}" (possible cyclic definition)')
NAME_NOT_DEFINED: Final = ErrorMessage('Name "{}" is not defined', codes.NAME_DEFINED)
NAME_ALREADY_DEFINED: Final = ErrorMessage('{} "{}" already defined{}', codes.NO_REDEF)


# Semantic Analysis: Enum
ENUM_ATTRIBUTE_UNSUPPORTED: Final = ErrorMessage("Enum type as attribute is not supported")
ENUM_CALL_UNEXPECTED_ARGS: Final = ErrorMessage("Unexpected arguments to {}()")
ENUM_CALL_UNEXPECTED_KWARG: Final = ErrorMessage('Unexpected keyword argument "{}"')
ENUM_CALL_TOO_MANY_ARGS: Final = ErrorMessage("Too many arguments for {}()")
ENUM_CALL_TOO_FEW_ARGS: Final = ErrorMessage("Too few arguments for {}()")
ENUM_CALL_EXPECTED_STRING_LITERAL: Final = ErrorMessage(
    "{}() expects a string literal as the first argument"
)
ENUM_CALL_EXPECTED_STRINGS_OR_PAIRS: Final = ErrorMessage(
    "{}() with tuple or list expects strings or (name, value) pairs"
)
ENUM_CALL_DICT_EXPECTED_STRING_KEYS: Final = ErrorMessage(
    "{}() with dict literal requires string literals"
)
ENUM_CALL_EXPECTED_LITERAL: Final = ErrorMessage(
    "{}() expects a string, tuple, list or dict literal as the second argument"
)
ENUM_CALL_ATLEAST_ONE_ITEM: Final = ErrorMessage("{}() needs at least one item")
ENUM_REUSED_MEMBER_IN_DEFN: Final = ErrorMessage(
    'Attempted to reuse member name "{}" in Enum definition "{}"'
)

# Semantic Analysis: NamedTuple
NAMEDTUPLE_SUPPORTED_ABOVE_PY36: Final = ErrorMessage(
    "NamedTuple class syntax is only supported in Python 3.6"
)
NAMEDTUPLE_SINGLE_BASE: Final = ErrorMessage("NamedTuple should be a single base")
NAMEDTUPLE_CLASS_ERROR: Final = ErrorMessage(
    "Invalid statement in NamedTuple definition; " 'expected "field_name: field_type [= default]"'
)
NAMEDTUPLE_FIELD_NO_UNDERSCORE: Final = ErrorMessage(
    "NamedTuple field name cannot start with an underscore: {}"
)
NAMEDTUPLE_FIELD_DEFAULT_AFTER_NONDEFAULT: Final = ErrorMessage(
    "Non-default NamedTuple fields cannot follow default fields"
)
NAMEDTUPLE_TOO_FEW_ARGS: Final = ErrorMessage('Too few arguments for "{}()"')
NAMEDTUPLE_TOO_MANY_ARGS: Final = ErrorMessage('Too many arguments for "{}()"')
NAMEDTUPLE_EXPECTED_LIST_TUPLE_DEFAULTS: Final = ErrorMessage(
    "List or tuple literal expected as the defaults argument to {}()"
)
NAMEDTUPLE_UNEXPECTED_ARGS: Final = ErrorMessage('Unexpected arguments to "{}()"')
NAMEDTUPLE_ARG_EXPECTED_STRING_LITERAL: Final = ErrorMessage(
    '"{}()" expects a string literal as the first argument'
)
NAMEDTUPLE_ARG_EXPECTED_LIST_TUPLE: Final = ErrorMessage(
    'List or tuple literal expected as the second argument to "{}()"'
)
NAMEDTUPLE_EXPECTED_STRING_LITERAL: Final = ErrorMessage(
    'String literal expected as "namedtuple()" item'
)
NAMEDTUPLE_FIELDS_NO_UNDERSCORE: Final = ErrorMessage(
    '"{}()" field names cannot start with an underscore: {}'
)
NAMEDTUPLE_TOO_MANY_DEFAULTS: Final = ErrorMessage('Too many defaults given in call to "{}()"')
NAMEDTUPLE_INVALID_FIELD_DEFINITION: Final = ErrorMessage("Invalid NamedTuple field definition")
NAMEDTUPLE_INVALID_FIELD_NAME: Final = ErrorMessage("Invalid NamedTuple() field name")
NAMEDTUPLE_INVALID_FIELD_TYPE: Final = ErrorMessage("Invalid field type")
NAMEDTUPLE_TUPLE_EXPECTED: Final = ErrorMessage('Tuple expected as "NamedTuple()" field')
NAMEDTUPLE_CANNOT_OVERWRITE_ATTRIBUTE: Final = ErrorMessage(
    'Cannot overwrite NamedTuple attribute "{}"'
)

# Semantic Analysis: NewType
NEWTYPE_USED_WITH_PROTOCOL: Final = ErrorMessage("NewType cannot be used with protocol classes")
NEWTYPE_ARG_MUST_BE_SUBCLASSABLE: Final = ErrorMessage(
    "Argument 2 to NewType(...) must be subclassable (got {})", codes.VALID_NEWTYPE
)
CANNOT_DECLARE_TYPE_OF_NEWTYPE: Final = ErrorMessage(
    "Cannot declare the type of a NewType declaration"
)
CANNOT_REDEFINE_AS_NEWTYPE: Final = ErrorMessage('Cannot redefine "{}" as a NewType')
NEWTYPE_EXPECTS_TWO_ARGS: Final = ErrorMessage(
    "NewType(...) expects exactly two positional arguments"
)
NEWTYPE_ARG_STRING_LITERAL: Final = ErrorMessage(
    "Argument 1 to NewType(...) must be a string literal"
)
NEWTYPE_ARG_VARNAME_MISMATCH: Final = ErrorMessage(
    'String argument 1 "{}" to NewType(...) does not match variable name "{}"'
)
NEWTYPE_ARG_INVALID_TYPE: Final = ErrorMessage("Argument 2 to NewType(...) must be a valid type")

# Semantic Analysis: TypedDict
TYPEDDICT_BASES_MUST_BE_TYPEDDICTS: Final = ErrorMessage(
    "All bases of a new TypedDict must be TypedDict types"
)
TYPEDDICT_OVERWRITE_FIELD_IN_MERGE: Final = ErrorMessage(
    'Overwriting TypedDict field "{}" while merging'
)
TYPEDDICT_OVERWRITE_FIELD_IN_EXTEND: Final = ErrorMessage(
    'Overwriting TypedDict field "{}" while extending'
)
TYPEDDICT_CLASS_ERROR: Final = ErrorMessage(
    "Invalid statement in TypedDict definition; " 'expected "field_name: field_type"'
)
TYPEDDICT_ARG_NAME_MISMATCH: Final = ErrorMessage(
    'First argument "{}" to TypedDict() does not match variable name "{}"', codes.NAME_MATCH
)
TYPEDDICT_TOO_FEW_ARGS: Final = ErrorMessage("Too few arguments for TypedDict()")
TYPEDDICT_TOO_MANY_ARGS: Final = ErrorMessage("Too many arguments for TypedDict()")
TYPEDDICT_UNEXPECTED_ARGS: Final = ErrorMessage("Unexpected arguments to TypedDict()")
TYPEDDICT_CALL_UNEXPECTED_KWARG: Final = ErrorMessage(
    'Unexpected keyword argument "{}" for "TypedDict"'
)
TYPEDDICT_CALL_EXPECTED_STRING_LITERAL: Final = ErrorMessage(
    "TypedDict() expects a string literal as the first argument"
)
TYPEDDICT_CALL_EXPECTED_DICT: Final = ErrorMessage(
    "TypedDict() expects a dictionary literal as the second argument"
)
TYPEDDICT_RHS_VALUE_UNSUPPORTED: Final = ErrorMessage(
    "Right hand side values are not supported in TypedDict"
)
TYPEDDICT_TOTAL_MUST_BE_BOOL: Final = ErrorMessage(
    'TypedDict() "total" argument must be True or False'
)
TYPEDDICT_TOTAL_MUST_BE_BOOL_2: Final = ErrorMessage('Value of "total" must be True or False')
TYPEDDICT_DUPLICATE_KEY: Final = ErrorMessage('Duplicate TypedDict key "{}"')
TYPEDDICT_INVALID_FIELD_NAME: Final = ErrorMessage("Invalid TypedDict() field name")
TYPEDDICT_INVALID_FIELD_TYPE: Final = ErrorMessage("Invalid field type")
TYPEDDICT_INLINE_UNSUPPORTED: Final = ErrorMessage(
    'Inline TypedDict types not supported; use assignment to define TypedDict'
)
# Type Analysis
TYPEANAL_INTERNAL_ERROR: Final = ErrorMessage("Internal error (node is None, kind={})")
NOT_SUBSCRIPTABLE: Final = ErrorMessage('"{}" is not subscriptable')
NOT_SUBSCRIPTABLE_REPLACEMENT: Final = ErrorMessage('"{}" is not subscriptable, use "{}" instead')
INVALID_LOCATION_FOR_PARAMSPEC: Final = ErrorMessage('Invalid location for ParamSpec "{}"')
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
CLASS_VAR_WITH_TYPEVARS: Final = ErrorMessage('ClassVar cannot contain type variables')
CLASS_VAR_OUTSIDE_OF_CLASS: Final = 'ClassVar can only be used for assignments in class body'

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
