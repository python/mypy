from __future__ import annotations
from mypy.types import Instance

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final


class DisallowStrIterationState:
    # Wrap this in a class since it's faster that using a module-level attribute.

    def __init__(self, disallow_str_iteration: bool) -> None:
        # Value varies by file being processed
        self.disallow_str_iteration = disallow_str_iteration

    @contextmanager
    def set(self, value: bool) -> Iterator[None]:
        saved = self.disallow_str_iteration
        self.disallow_str_iteration = value
        try:
            yield
        finally:
            self.disallow_str_iteration = saved


disallow_str_iteration_state: Final = DisallowStrIterationState(disallow_str_iteration=False)


STR_ITERATION_PROTOCOL_BASES: Final = frozenset(
    {
        "collections.abc.Collection",
        "collections.abc.Iterable",
        "collections.abc.Sequence",
        "typing.Collection",
        "typing.Iterable",
        "typing.Sequence",
    }
)


def is_subtype_relation_ignored_to_disallow_str_iteration(left: Instance, right: Instance) -> bool:
    return (
        left.type.has_base("builtins.str")
        and not right.type.has_base("builtins.str")
        and any(right.type.has_base(base) for base in STR_ITERATION_PROTOCOL_BASES)
    )
