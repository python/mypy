"""Bounded coverage proofs for fixed tuple products.

Input types and AST nodes are treated as read-only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias

from mypy.nodes import (
    BytesExpr,
    Expression,
    IntExpr,
    MemberExpr,
    RefExpr,
    StrExpr,
    TypeInfo,
    UnaryExpr,
)
from mypy.patterns import (
    AsPattern,
    ClassPattern,
    OrPattern,
    Pattern,
    SequencePattern,
    SingletonPattern,
    ValuePattern,
)
from mypy.typeops import literal_values
from mypy.types import (
    Instance,
    LiteralType,
    NoneType,
    ProperType,
    TupleType,
    Type,
    TypeAliasType,
    UnionType,
    find_unpack_in_list,
    get_proper_type,
)


@dataclass(frozen=True)
class ValueDomain:
    """Type alternatives represented by one coverage-matrix column."""

    alternatives: tuple[ProperType, ...]


@dataclass(frozen=True)
class TupleDomain:
    """The component domains of a fixed-length tuple."""

    items: tuple[ValueDomain | TupleDomain, ...]


Domain: TypeAlias = ValueDomain | TupleDomain
Row: TypeAlias = tuple[int, ...]
Matrix: TypeAlias = tuple[Row, ...]


@dataclass(frozen=True)
class _VisitType:
    typ: Type


@dataclass(frozen=True)
class _FinishTuple:
    typ: TupleType


def build_domain(subject: Type, *, work_limit: int) -> Domain | None:
    """Build a domain for the subject type.

    Return None if the type is unsupported or the budget runs out.
    """
    # Use a stack to handle deeply nested tuple aliases without Python recursion.
    pending: list[_VisitType | _FinishTuple] = [_VisitType(subject)]
    built: list[Domain] = []
    while pending:
        task = pending.pop()
        if isinstance(task, _FinishTuple):
            start = len(built) - len(task.typ.items)
            built[start:] = [TupleDomain(tuple(built[start:]))]
            continue
        typ = task.typ
        work_limit -= 1
        if work_limit < 0:
            return None
        if isinstance(typ, TypeAliasType) and (typ.alias is None or typ.is_recursive):
            return None
        proper = get_proper_type(typ)
        match proper:
            case TupleType(items=items, partial_fallback=fallback):
                if (
                    fallback.type.fullname != "builtins.tuple"
                    or find_unpack_in_list(items) is not None
                ):
                    return None
                work_limit -= len(items)
                if work_limit < 0:
                    return None
                pending.append(_FinishTuple(proper))
                pending.extend(_VisitType(item) for item in reversed(items))
                continue
            case UnionType(items=variants):
                pass
            case _:
                variants = [proper]
        alternatives: list[ProperType] = []
        for variant in variants:
            work_limit -= 1
            if work_limit < 0:
                return None
            if isinstance(variant, TypeAliasType) and (
                variant.alias is None or variant.is_recursive
            ):
                return None
            value = get_proper_type(variant)
            match value:
                case Instance(last_known_value=LiteralType() as literal):
                    alternatives.append(literal)
                case Instance():
                    values = literal_values(value)
                    if values is not None and len(values) <= work_limit:
                        work_limit -= len(values)
                        alternatives.extend(LiteralType(item, value) for item in values)
                    else:
                        # Keep unavailable or oversized expansions opaque, never partial.
                        alternatives.append(value)
                case _:
                    alternatives.append(value)
        if not alternatives:
            return None
        built.append(ValueDomain(tuple(alternatives)))
    return built[0]


def full_row(domain: Domain) -> Row:
    """Flatten a bounded domain into a full-coverage bitset for each column."""
    pending = [domain]
    masks = []
    while pending:
        match pending.pop():
            case ValueDomain(alternatives=alternatives):
                masks.append((1 << len(alternatives)) - 1)
            case TupleDomain(items=items):
                pending.extend(reversed(items))
    return tuple(masks)


def _resolve_literals(
    patterns: Sequence[Pattern],
    lookup_type: Callable[[Expression], Type | None],
    *,
    work_limit: int,
) -> tuple[Mapping[Expression, LiteralType], int] | None:
    """Read cached types for literal and enum-member patterns.

    The result includes the remaining budget. Return None if it runs out.
    """
    work_limit -= len(patterns)
    if work_limit < 0:
        return None
    pending = list(reversed(patterns))
    literals: dict[Expression, LiteralType] = {}
    while pending:
        work_limit -= 1
        if work_limit < 0:
            return None
        match pending.pop():
            case AsPattern(pattern=inner) if inner is not None:
                pending.append(inner)
            case OrPattern(patterns=children) | SequencePattern(patterns=children):
                work_limit -= len(children)
                if work_limit < 0:
                    return None
                pending.extend(reversed(children))
            case ValuePattern(expr=expr):
                # Other dotted values may change between cases.
                # Only literals and statically resolved enum members are safe to use here.
                match expr:
                    case IntExpr() | StrExpr() | BytesExpr():
                        pass
                    case UnaryExpr(op="+" | "-", expr=IntExpr()):
                        pass
                    case MemberExpr(expr=RefExpr(node=TypeInfo(is_enum=True))):
                        pass
                    case _:
                        continue
                match get_proper_type(lookup_type(expr)):
                    case (LiteralType() as literal) | Instance(
                        last_known_value=LiteralType() as literal
                    ):
                        literals[expr] = literal
    return MappingProxyType(literals), work_limit


def _covers_alternative(
    pattern: Pattern,
    alternative: ProperType,
    literals: Mapping[Expression, LiteralType],
    *,
    work_limit: int,
) -> tuple[bool, int] | None:
    """Check whether the pattern matches every value in this alternative.

    Return the answer and unused budget, or None if the budget runs out.
    """
    pending = [pattern]
    while pending:
        work_limit -= 1
        if work_limit < 0:
            return None
        match pending.pop(), alternative:
            case AsPattern(pattern=None), _:
                return True, work_limit
            case AsPattern(pattern=inner), _ if inner is not None:
                pending.append(inner)
            case OrPattern(patterns=alternatives), _:
                work_limit -= len(alternatives)
                if work_limit < 0:
                    return None
                pending.extend(reversed(alternatives))
            case SingletonPattern(value=None), NoneType():
                return True, work_limit
            case SingletonPattern(value=expected), LiteralType(value=actual, fallback=fallback):
                if fallback.type.fullname == "builtins.bool" and actual is expected:
                    return True, work_limit
            case (
                ClassPattern(class_ref=ref, positionals=[], keyword_values=[]),
                (Instance() as instance) | LiteralType(fallback=instance),
            ):
                target = ref.node
                if (
                    isinstance(target, TypeInfo)
                    and not target.is_protocol
                    and target in instance.type.mro
                ):
                    return True, work_limit
            case ValuePattern(expr=expr), LiteralType():
                if literals.get(expr) == alternative:
                    return True, work_limit
    return False, work_limit


def _compile_row(
    pattern: Pattern,
    domain: Domain,
    literals: Mapping[Expression, LiteralType],
    *,
    work_limit: int,
) -> tuple[Matrix, int] | None:
    """Compile a pattern into a coverage row.

    Unsupported patterns produce no rows; running out of budget returns None.
    """
    pending: list[tuple[Pattern | None, Domain]] = [(pattern, domain)]
    masks: list[int] = []
    while pending:
        work_limit -= 1
        if work_limit < 0:
            return None
        current, node = pending.pop()
        match current:
            case AsPattern(pattern=inner):
                pending.append((inner, node))
                continue
        match node:
            case TupleDomain(items=items):
                work_limit -= len(items)
                if work_limit < 0:
                    return None
                match current:
                    case None:
                        pending.extend((None, child) for child in reversed(items))
                    case SequencePattern(patterns=children) if len(children) == len(items):
                        pending.extend(zip(reversed(children), reversed(items)))
                    case _:
                        return (), work_limit
            case ValueDomain(alternatives=alternatives):
                if current is None:
                    masks.append((1 << len(alternatives)) - 1)
                    continue
                mask = 0
                for i, alternative in enumerate(alternatives):
                    result = _covers_alternative(
                        current, alternative, literals, work_limit=work_limit
                    )
                    if result is None:
                        return None
                    covered, work_limit = result
                    if covered:
                        mask |= 1 << i
                masks.append(mask)
    return (tuple(masks),), work_limit


def compile_patterns(
    patterns: Sequence[Pattern],
    domain: Domain,
    literals: Mapping[Expression, LiteralType],
    *,
    work_limit: int,
) -> tuple[Matrix, int] | None:
    """Compile patterns into coverage rows, skipping patterns we can't handle.

    Return the rows and unused budget, or None if the budget runs out.
    """
    work_limit -= len(patterns)
    if work_limit < 0:
        return None
    pending = list(reversed(patterns))
    rows: list[Row] = []
    while pending:
        work_limit -= 1
        if work_limit < 0:
            return None
        pattern = pending.pop()
        match pattern:
            case AsPattern(pattern=inner) if inner is not None:
                pending.append(inner)
            case OrPattern(patterns=alternatives):
                work_limit -= len(alternatives)
                if work_limit < 0:
                    return None
                pending.extend(reversed(alternatives))
            case _:
                compiled = _compile_row(pattern, domain, literals, work_limit=work_limit)
                if compiled is None:
                    return None
                compiled_rows, work_limit = compiled
                rows.extend(compiled_rows)
    return tuple(rows), work_limit


def covers_product(domains: Row, rows: Matrix, *, work_limit: int) -> bool:
    """Check whether the rows cover every combination of column values.

    Each bit represents a type alternative.
    Alternatives matched by the same rows are checked together.
    Each step removes a column; a row covering all remaining columns finishes that branch.

    False can mean there's an uncovered value or that the work budget ran out.
    """
    pending = [(domains, rows)]
    seen: set[tuple[Row, Matrix]] = set()
    while pending:
        domain, matrix = pending.pop()
        work_limit -= max(1, len(matrix) * len(domain))
        if work_limit < 0:
            return False
        matrix = tuple(dict.fromkeys(row for row in matrix if all(row)))
        if domain in matrix:
            continue
        if not matrix:
            return False
        key = domain, matrix
        if key in seen:
            continue
        seen.add(key)

        shortest = min(matrix, key=lambda row: sum(a != b for a, b in zip(row, domain)))
        column = next(i for i, (a, b) in enumerate(zip(shortest, domain)) if a != b)
        groups = [domain[column]]
        for mask in dict.fromkeys(row[column] for row in matrix):
            work_limit -= len(groups)
            if work_limit < 0:
                return False
            split = []
            for group in groups:
                yes, no = group & mask, group & ~mask
                if yes:
                    split.append(yes)
                if no:
                    split.append(no)
            groups = split
        reduced_domain = domain[:column] + domain[column + 1 :]
        for group in groups:
            if (
                shortest[column] & group
                and shortest[:column] + shortest[column + 1 :] == reduced_domain
            ):
                continue
            work_limit -= len(matrix) * max(1, len(domain))
            if work_limit < 0:
                return False
            reduced_rows = tuple(
                row[:column] + row[column + 1 :] for row in matrix if row[column] & group
            )
            if not reduced_rows:
                return False
            pending.append((reduced_domain, reduced_rows))
    return True


def is_product_exhaustive(
    subject: Type,
    patterns: Sequence[Pattern],
    lookup_type: Callable[[Expression], Type | None],
    *,
    limit: int = 1024,
) -> bool:
    """Check whether an unguarded tuple match is exhaustive.

    Alternatives can overlap, so a pattern must cover all values of an alternative for it to count.
    Guards must be excluded because they can change the values used by later patterns.
    False means we couldn't prove coverage.
    """
    if not isinstance(get_proper_type(subject), TupleType):
        return False
    domain = build_domain(subject, work_limit=limit)
    if domain is None:
        return False
    full = full_row(domain)
    resolved = _resolve_literals(patterns, lookup_type, work_limit=limit * max(1, len(full)))
    if resolved is None:
        return False
    literals, remaining = resolved
    compiled = compile_patterns(patterns, domain, literals, work_limit=remaining)
    if compiled is None:
        return False
    rows, remaining = compiled
    return covers_product(full, rows, work_limit=remaining)
