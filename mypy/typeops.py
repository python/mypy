"""Miscellaneuus type operations and helpers for use during type checking.

NOTE: These must not be accessed from mypy.nodes or mypy.types to avoid import
      cycles. These must not be called from the semantic analysis main pass
      since these may assume that MROs are ready.
"""

# TODO: Move more type operations here

from mypy.types import TupleType, Instance
from mypy.join import join_type_list


def tuple_fallback(typ: TupleType) -> Instance:
    """Return fallback type for a tuple."""
    info = typ.partial_fallback.type
    if info.fullname() != 'builtins.tuple':
        return typ.partial_fallback
    return Instance(info, [join_type_list(typ.items)])
