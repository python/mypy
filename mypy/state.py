from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from mypy.checker_shared import TypeCheckerSharedApi

# These are global mutable state. Don't add anything here unless there's a very
# good reason.


class SubtypeState:
    # Wrap this in a class since it's faster that using a module-level attribute.

    def __init__(self, strict_optional: bool, type_checker: TypeCheckerSharedApi | None) -> None:
        # Values vary by file being processed
        self.strict_optional = strict_optional
        self.type_checker = type_checker

    @contextmanager
    def strict_optional_set(self, value: bool) -> Iterator[None]:
        saved = self.strict_optional
        self.strict_optional = value
        try:
            yield
        finally:
            self.strict_optional = saved

    @contextmanager
    def type_checker_set(self, value: TypeCheckerSharedApi) -> Iterator[None]:
        saved = self.type_checker
        self.type_checker = value
        try:
            yield
        finally:
            self.type_checker = saved


state: Final = SubtypeState(strict_optional=True, type_checker=None)
find_occurrences: tuple[str, str] | None = None
