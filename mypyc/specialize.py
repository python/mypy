"""General infrastructure for special casing calls to builtin functions.

Most special cases should be handled using the data driven "primitive
ops" system, but certain operations require special handling that has
access to the AST/IR directly and can make decisions/optimizations
based on it.

For example, we use specializers to statically emit the length of a
fixed length tuple and to emit optimized code for any()/all() calls with
generator comprehensions as the argument.

See comment below for more documentation.
"""

from typing import Callable, Optional, Dict, Tuple
from typing_extensions import TYPE_CHECKING

from mypy.nodes import CallExpr, RefExpr

from mypyc.ops import Value, RType

if TYPE_CHECKING:
    from mypyc.genops import IRBuilder  # noqa


# Specializers are attempted before compiling the arguments to the
# function.  Specializers can return None to indicate that they failed
# and the call should be compiled normally. Otherwise they should emit
# code for the call and return a Value containing the result.
#
# Specializers take three arguments: the IRBuilder, the CallExpr being
# compiled, and the RefExpr that is the left hand side of the call.
#
# Specializers can operate on methods as well, and are keyed on the
# name and RType in that case.
Specializer = Callable[['IRBuilder', CallExpr, RefExpr], Optional[Value]]

specializers = {}  # type: Dict[Tuple[str, Optional[RType]], Specializer]


def specialize_function(
        name: str, typ: Optional[RType] = None) -> Callable[[Specializer], Specializer]:
    """Decorator to register a function as being a specializer."""
    def wrapper(f: Specializer) -> Specializer:
        specializers[name, typ] = f
        return f
    return wrapper
