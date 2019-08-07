"""Classification of possible errors mypy can detect.

These can be used for filtering specific errors.
"""

from typing import List
from typing_extensions import Final


# All created error codes are implicitly stored in this list.
all_error_codes = []  # type: List[ErrorCode]


class ErrorCode:
    def __init__(self, code: str, description: str, category: str) -> None:
        self.code = code
        self.description = description
        self.category = category

    def __str__(self) -> str:
        return '<ErrorCode {}>'.format(self.code)


ATTR_DEFINED = ErrorCode(
    'attr-defined', "Check that attribute exists", 'General')  # type: Final
NAME_DEFINED = ErrorCode(
    'name-defined', "Check that name is defined", 'General')  # type: Final
CALL_ARG = ErrorCode(
    'call-arg', "Check number, names and kinds of arguments in calls", 'General')  # type: Final
ARG_TYPE = ErrorCode(
    'arg-type', "Check argument types in calls", 'General')  # type: Final
VALID_TYPE = ErrorCode(
    'valid-type', "Check that type (annotation) is valid", 'General')  # type: Final
MISSING_ANN = ErrorCode(
    'var-annotated', "Require variable annotation if type can't be inferred",
    'General')  # type: Final
OVERRIDE = ErrorCode(
    'override', "Check that method override is compatible with base class",
    'General')  # type: Final
RETURN_VALUE = ErrorCode(
    'return-value', "Check that return value is compatible with signature",
    'General')  # type: Final
ASSIGNMENT = ErrorCode(
    'assignment', "Check that assigned value is compatible with target", 'General')  # type: Final

SYNTAX = ErrorCode(
    'syntax', "Report syntax errors", 'General')  # type: Final

MISC = ErrorCode(
    'misc', "Miscenallenous other checks", 'General')  # type: Final
