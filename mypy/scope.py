"""Track current scope to easily calculate the corresponding fine-grained target.

This is currently only used by mypy.semanal and mypy.server.deps.
"""

from typing import List, Optional

from mypy.nodes import TypeInfo, FuncItem

class Scope:
    """Track which target we are processing at any given time."""

    def __init__(self) -> None:
        self.module = None  # type: Optional[str]
        self.classes = []  # type: List[TypeInfo]
        self.function = None  # type: Optional[FuncItem]
        # Number of nested scopes ignored (that don't get their own separate targets)
        self.ignored = 0

    def current_module_id(self) -> str:
        assert self.module
        return self.module

    def current_target(self) -> str:
        """Return the current target (non-class; for a class return enclosing module)."""
        assert self.module
        target = self.module
        if self.function:
            if self.classes:
                target += '.' + '.'.join(c.name() for c in self.classes)
            target += '.' + self.function.name()
        return target

    def current_full_target(self) -> str:
        """Return the current target (may be a class)."""
        assert self.module
        target = self.module
        if self.classes:
            target += '.' + '.'.join(c.name() for c in self.classes)
        if self.function:
            target += '.' + self.function.name()
        return target

    def enter_file(self, prefix: str) -> None:
        self.module = prefix
        self.classes = []
        self.function = None
        self.ignored = 0

    def enter_function(self, fdef: FuncItem) -> None:
        if not self.function:
            self.function = fdef
        else:
            # Nested functions are part of the topmost function target.
            self.ignored += 1

    def enter_class(self, info: TypeInfo) -> None:
        """Enter a class target scope."""
        if not self.function:
            self.classes.append(info)
        else:
            # Classes within functions are part of the enclosing function target.
            self.ignored += 1

    def leave(self) -> None:
        """Leave the innermost scope (can be any kind of scope)."""
        if self.ignored:
            # Leave a scope that's included in the enclosing target.
            self.ignored -= 1
        elif self.function:
            # Function is always the innermost target.
            self.function = None
        elif self.classes:
            # Leave the innermost class.
            self.classes.pop()
        else:
            # Leave module.
            assert self.module
            self.module = None
