"""Stuff that we had to move out of its right place because of mypyc limitations."""


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


from typing import Dict, Any
import sys


# Extracted from build.py because we can't handle *args righit
class BuildManagerBase:
    def __init__(self) -> None:
        self.stats = {}  # type: Dict[str, Any]  # Values are ints or floats

    def verbosity(self) -> int:
        return self.options.verbosity  # type: ignore

    def log(self, *message: str) -> None:
        if self.verbosity() >= 1:
            if message:
                print('LOG: ', *message, file=sys.stderr)
            else:
                print(file=sys.stderr)
            sys.stderr.flush()

    def log_fine_grained(self, *message: str) -> None:
        import mypy.build
        if self.verbosity() >= 1:
            self.log('fine-grained:', *message)
        elif mypy.build.DEBUG_FINE_GRAINED:
            # Output log in a simplified format that is quick to browse.
            if message:
                print(*message, file=sys.stderr)
            else:
                print(file=sys.stderr)
            sys.stderr.flush()

    def trace(self, *message: str) -> None:
        if self.verbosity() >= 2:
            print('TRACE:', *message, file=sys.stderr)
            sys.stderr.flush()

    def add_stats(self, **kwds: Any) -> None:
        for key, value in kwds.items():
            if key in self.stats:
                self.stats[key] += value
            else:
                self.stats[key] = value
