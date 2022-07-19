"""Classes for representing match statement patterns."""
from typing import TypeVar, List, Optional, Union

from mypy_extensions import trait

from mypy.nodes import Node, RefExpr, NameExpr, Expression
from mypy.visitor import PatternVisitor


T = TypeVar('T')


@trait
class Pattern(Node):
    """A pattern node."""

    __slots__ = ()

    def accept(self, visitor: PatternVisitor[T]) -> T:
        raise RuntimeError('Not implemented')


class AsPattern(Pattern):
    """The pattern <pattern> as <name>"""
    # The python ast, and therefore also our ast merges capture, wildcard and as patterns into one
    # for easier handling.
    # If pattern is None this is a capture pattern. If name and pattern are both none this is a
    # wildcard pattern.
    # Only name being None should not happen but also won't break anything.
    pattern: Optional[Pattern]
    name: Optional[NameExpr]

    def __init__(self, pattern: Optional[Pattern], name: Optional[NameExpr]) -> None:
        super().__init__()
        self.pattern = pattern
        self.name = name

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_as_pattern(self)


class OrPattern(Pattern):
    """The pattern <pattern> | <pattern> | ..."""
    patterns: List[Pattern]

    def __init__(self, patterns: List[Pattern]) -> None:
        super().__init__()
        self.patterns = patterns

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_or_pattern(self)


class ValuePattern(Pattern):
    """The pattern x.y (or x.y.z, ...)"""
    expr: Expression

    def __init__(self, expr: Expression):
        super().__init__()
        self.expr = expr

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_value_pattern(self)


class SingletonPattern(Pattern):
    # This can be exactly True, False or None
    value: Union[bool, None]

    def __init__(self, value: Union[bool, None]):
        super().__init__()
        self.value = value

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_singleton_pattern(self)


class SequencePattern(Pattern):
    """The pattern [<pattern>, ...]"""
    patterns: List[Pattern]

    def __init__(self, patterns: List[Pattern]):
        super().__init__()
        self.patterns = patterns

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_sequence_pattern(self)


class StarredPattern(Pattern):
    # None corresponds to *_ in a list pattern. It will match multiple items but won't bind them to
    # a name.
    capture: Optional[NameExpr]

    def __init__(self, capture: Optional[NameExpr]):
        super().__init__()
        self.capture = capture

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_starred_pattern(self)


class MappingPattern(Pattern):
    keys: List[Expression]
    values: List[Pattern]
    rest: Optional[NameExpr]

    def __init__(self, keys: List[Expression], values: List[Pattern],
                 rest: Optional[NameExpr]):
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
    positionals: List[Pattern]
    keyword_keys: List[str]
    keyword_values: List[Pattern]

    def __init__(self, class_ref: RefExpr, positionals: List[Pattern], keyword_keys: List[str],
                 keyword_values: List[Pattern]):
        super().__init__()
        assert len(keyword_keys) == len(keyword_values)
        self.class_ref = class_ref
        self.positionals = positionals
        self.keyword_keys = keyword_keys
        self.keyword_values = keyword_values

    def accept(self, visitor: PatternVisitor[T]) -> T:
        return visitor.visit_class_pattern(self)
