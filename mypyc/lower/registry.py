from __future__ import annotations

from typing import Callable, Final, List

from mypyc.ir.ops import Value
from mypyc.irbuild.ll_builder import LowLevelIRBuilder

LowerFunc = Callable[[LowLevelIRBuilder, List[Value], int], Value]


lowering_registry: Final[dict[str, LowerFunc]] = {}


def lower_binary_op(name: str) -> Callable[[LowerFunc], LowerFunc]:
    """Register a handler that generates low-level IR for a primitive binary op."""

    def wrapper(f: LowerFunc) -> LowerFunc:
        assert name not in lowering_registry
        lowering_registry[name] = f
        return f

    return wrapper


# Import various modules that set up global state.
import mypyc.lower.int_ops  # noqa: F401
