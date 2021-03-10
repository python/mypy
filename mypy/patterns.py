"""Classes for representing match statement patterns."""
from typing import TypeVar, List, Any

from mypy_extensions import trait

from mypy.nodes import Node
from mypy.visitor import PatternVisitor

# These are not real AST nodes. CPython represents patterns using the normal expression nodes.

T = TypeVar('T')


@trait
class Pattern(Node):
    """A pattern node."""

    __slots__ = ()

    def accept(self, visitor: PatternVisitor[T]) -> T:
        raise RuntimeError('Not implemented')


class AsPattern(Pattern):
    pattern = None  # type: Pattern
    name = None  # type: str

    def __init__(self, pattern: Pattern, name: str) -> None:
        super().__init__()
        self.pattern = pattern
        self.name = name

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_as_pattern(self)


class OrPattern(Pattern):
    patterns = None  # type: List[Pattern]

    def __init__(self, patterns: List[Pattern]) -> None:
        super().__init__()
        self.patterns = patterns

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_or_pattern(self)


# TODO: Do we need subclassed for the typed of literals?
class LiteralPattern(Pattern):
    value = None  # type: Any

    def __init__(self, value: Any):
        super().__init__()
        self.value = value

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_literal_pattern(self)
