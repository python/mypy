"""Classes for representing match statement patterns."""
from typing import TypeVar, List, Any, Union, Optional

from mypy_extensions import trait

from mypy.nodes import Node, MemberExpr, RefExpr
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


# TODO: Do we need subclasses for the types of literals?
class LiteralPattern(Pattern):
    value = None  # type: Any

    def __init__(self, value: Any):
        super().__init__()
        self.value = value

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_literal_pattern(self)


class CapturePattern(Pattern):
    name = None  # type: str

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_capture_pattern(self)


class WildcardPattern(Pattern):
    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_wildcard_pattern(self)


class ValuePattern(Pattern):
    expr = None  # type: MemberExpr

    def __init__(self, expr: MemberExpr):
        super().__init__()
        self.expr = expr

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_value_pattern(self)


class SequencePattern(Pattern):
    patterns = None  # type: List[Pattern]

    def __init__(self, patterns: List[Pattern]):
        super().__init__()
        self.patterns = patterns

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_sequence_pattern(self)


# TODO: A StarredPattern is only valid within a SequencePattern. This is not guaranteed by our
# type hierarchy. Should it be?
class StarredPattern(Pattern):
    name = None  # type: str

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_starred_pattern(self)


MappingKeyPattern = Union[LiteralPattern, ValuePattern]


class MappingPattern(Pattern):
    keys = None  # type: List[MappingKeyPattern]
    values = None  # type: List[Pattern]
    rest = None  # type: Optional[CapturePattern]

    def __init__(self, keys: List[MappingKeyPattern], values: List[Pattern],
                 rest: Optional[CapturePattern]):
        super().__init__()
        self.keys = keys
        self.values = values
        self.rest = rest

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_mapping_pattern(self)


class ClassPattern(Pattern):
    class_ref = None  # type: RefExpr
    positionals = None  # type: List[Pattern]
    keyword_keys = None  # type: List[str]
    keyword_values = None  # type: List[Pattern]

    def __init__(self, class_ref: RefExpr, positionals: List[Pattern], keyword_keys: List[str],
                 keyword_values: List[Pattern]):
        super().__init__()
        self.class_ref = class_ref
        self.positionals = positionals
        self.keyword_keys = keyword_keys
        self.keyword_values = keyword_values

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_class_pattern(self)
