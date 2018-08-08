"""Stuff that we had to move out of its right place because of mypyc limitations."""

# Moved from util.py, because it inherits from Exception
class DecodeError(Exception):
    """Exception raised when a file cannot be decoded due to an unknown encoding type.

    Essentially a wrapper for the LookupError raised by `bytearray.decode`
    """


# Moved from types.py, because it inherits from Enum, which uses a
# metaclass in a nontrivial way.
from enum import Enum


class TypeOfAny(Enum):
    """
    This class describes different types of Any. Each 'Any' can be of only one type at a time.
    """
    # Was this Any type was inferred without a type annotation?
    unannotated = 'unannotated'
    # Does this Any come from an explicit type annotation?
    explicit = 'explicit'
    # Does this come from an unfollowed import? See --disallow-any-unimported option
    from_unimported_type = 'from_unimported_type'
    # Does this Any type come from omitted generics?
    from_omitted_generics = 'from_omitted_generics'
    # Does this Any come from an error?
    from_error = 'from_error'
    # Is this a type that can't be represented in mypy's type system? For instance, type of
    # call to NewType...). Even though these types aren't real Anys, we treat them as such.
    # Also used for variables named '_'.
    special_form = 'special_form'
    # Does this Any come from interaction with another Any?
    from_another_any = 'from_another_any'
    # Does this Any come from an implementation limitation/bug?
    implementation_artifact = 'implementation_artifact'
