from __future__ import annotations

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
