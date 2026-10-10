"""Classes for representing match statement patterns."""

from __future__ import annotations

from typing import TypeAlias, TypeVar

from mypy_extensions import trait

from mypy.nodes import Expression, NameExpr, Node, RefExpr
from mypy.visitor import PatternVisitor

T = TypeVar("T")


@trait
class Pattern(Node):
    """A pattern node."""

    __slots__ = ()

    def accept(self, visitor: PatternVisitor[T]) -> T:
        raise RuntimeError("Not implemented", type(self))


class AsPattern(Pattern):
    """The pattern <pattern> as <name>"""

    # The python ast, and therefore also our ast merges capture, wildcard and as patterns into one
    # for easier handling.
    # If pattern is None this is a capture pattern. If name and pattern are both none this is a
    # wildcard pattern.
    # Only name being None should not happen but also won't break anything.
    pattern: ConcretePattern | None
    name: NameExpr | None

    def __init__(self, pattern: ConcretePattern | None, name: NameExpr | None) -> None:
        super().__init__()
        self.pattern = pattern
        self.name = name

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_as_pattern(self)


class OrPattern(Pattern):
    """The pattern <pattern> | <pattern> | ..."""

    patterns: list[ConcretePattern]

    def __init__(self, patterns: list[ConcretePattern]) -> None:
        super().__init__()
        self.patterns = patterns

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_or_pattern(self)


class ValuePattern(Pattern):
    """The pattern x.y (or x.y.z, ...)"""

    expr: Expression

    def __init__(self, expr: Expression) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_value_pattern(self)


class SingletonPattern(Pattern):
    # This can be exactly True, False or None
    value: bool | None

    def __init__(self, value: bool | None) -> None:
        super().__init__()
        self.value = value

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_singleton_pattern(self)


class SequencePattern(Pattern):
    """The pattern [<pattern>, ...]"""

    patterns: list[ConcretePattern]

    def __init__(self, patterns: list[ConcretePattern]) -> None:
        super().__init__()
        self.patterns = patterns

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_sequence_pattern(self)


class StarredPattern(Pattern):
    # None corresponds to *_ in a list pattern. It will match multiple items but won't bind them to
    # a name.
    capture: NameExpr | None

    def __init__(self, capture: NameExpr | None) -> None:
        super().__init__()
        self.capture = capture

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_starred_pattern(self)


class MappingPattern(Pattern):
    keys: list[Expression]
    values: list[ConcretePattern]
    rest: NameExpr | None

    def __init__(
        self, keys: list[Expression], values: list[ConcretePattern], rest: NameExpr | None
    ) -> None:
        super().__init__()
        assert len(keys) == len(values)
        self.keys = keys
        self.values = values
        self.rest = rest

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_mapping_pattern(self)


class ClassPattern(Pattern):
    """The pattern Cls(...)"""

    class_ref: RefExpr
    positionals: list[ConcretePattern]
    keyword_keys: list[str]
    keyword_values: list[ConcretePattern]

    def __init__(
        self,
        class_ref: RefExpr,
        positionals: list[ConcretePattern],
        keyword_keys: list[str],
        keyword_values: list[ConcretePattern],
    ) -> None:
        super().__init__()
        assert len(keyword_keys) == len(keyword_values)
        self.class_ref = class_ref
        self.positionals = positionals
        self.keyword_keys = keyword_keys
        self.keyword_values = keyword_values

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_class_pattern(self)


ConcretePattern: TypeAlias = (
    AsPattern
    | OrPattern
    | ValuePattern
    | SingletonPattern
    | SequencePattern
    | StarredPattern
    | MappingPattern
    | ClassPattern
)
