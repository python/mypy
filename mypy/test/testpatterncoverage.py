"""Independent coverage oracles and checker regressions with bounded narrowing."""

from __future__ import annotations

import itertools
import random
from unittest import TestCase

import pytest

from mypy.patterncoverage import build_domain, compile_patterns, covers_product, full_row
from mypy.patterns import AsPattern, OrPattern, SequencePattern, SingletonPattern
from mypy.test import testcheck
from mypy.test.data import DataDrivenTestCase
from mypy.test.typefixture import TypeFixture
from mypy.types import TupleType

# Importing checkpattern before testcheck causes a circular import.
from mypy import checkpattern  # ruff: isort: skip


class PatternCoverageSuite(TestCase):
    def test_nested_compilation_and_budget_exhaustion(self) -> None:
        fx = TypeFixture()
        subject = TupleType(
            [
                fx.bool_type,
                TupleType([fx.nonet, fx.bool_type], fx.std_tuple),
                TupleType([], fx.std_tuple),
            ],
            fx.std_tuple,
        )
        domain = build_domain(subject, work_limit=100)
        assert domain is not None
        assert full_row(domain) == (3, 1, 3)
        patterns = [
            OrPattern(
                [
                    SequencePattern(
                        [
                            SingletonPattern(value),
                            SequencePattern([SingletonPattern(None), AsPattern(None, None)]),
                            SequencePattern([]),
                        ]
                    )
                    for value in (False, True)
                ]
            )
        ]
        compiled = compile_patterns(patterns, domain, {}, work_limit=100)
        assert compiled is not None
        rows, remaining = compiled
        assert rows == ((1, 1, 3), (2, 1, 3))
        assert covers_product(full_row(domain), rows, work_limit=remaining)
        spent = 100 - remaining
        assert compile_patterns(patterns, domain, {}, work_limit=spent) == (rows, 0)
        assert compile_patterns(patterns, domain, {}, work_limit=spent - 1) is None
        # The wrong tuple length must discard the whole row, even if earlier components match.
        wrong_shape = SequencePattern(
            [
                SingletonPattern(False),
                AsPattern(None, None),
                SequencePattern([AsPattern(None, None)]),
            ]
        )
        skipped = compile_patterns([wrong_shape], domain, {}, work_limit=100)
        assert skipped is not None and skipped[0] == ()

    def test_deep_domains_and_patterns(self) -> None:
        fx = TypeFixture()
        subject = TupleType([], fx.std_tuple)
        pattern = SequencePattern([])
        for _ in range(1500):
            subject = TupleType([subject], fx.std_tuple)
            pattern = SequencePattern([pattern])
        assert build_domain(subject, work_limit=100) is None
        domain = build_domain(subject, work_limit=10_000)
        assert domain is not None
        assert full_row(domain) == ()
        assert compile_patterns([pattern], domain, {}, work_limit=100) is None
        compiled = compile_patterns([pattern], domain, {}, work_limit=10_000)
        assert compiled is not None
        rows, remaining = compiled
        assert rows == ((),)
        assert covers_product((), rows, work_limit=remaining)

    def test_coverage_matches_enumeration(self) -> None:
        rng = random.Random(21968)
        for sizes in [(), (2,), (2, 2), (2, 2, 2), (3, 2, 3), (2,) * 5]:
            domains = tuple((1 << size) - 1 for size in sizes)
            points = list(itertools.product(*(range(size) for size in sizes)))
            for _ in range(1000):
                rows = tuple(
                    tuple(rng.randrange(domain + 1) for domain in domains)
                    for _ in range(rng.randrange(15))
                )
                expected = all(
                    any(
                        all(mask & (1 << value) for mask, value in zip(row, point)) for row in rows
                    )
                    for point in points
                )
                assert covers_product(domains, rows, work_limit=1_000_000) == expected
                assert not covers_product(domains, rows, work_limit=0)

    def test_large_product_and_missing_case(self) -> None:
        domains = (3,) * 256
        rows = []
        for pair in range(128):
            row = list(domains)
            row[2 * pair] = row[2 * pair + 1] = 2
            rows.append(tuple(row))
        for column in (254, 255):
            row = list(domains)
            row[column] = 1
            rows.append(tuple(row))
        assert covers_product(domains, tuple(rows), work_limit=1024 * len(domains))
        assert not covers_product(domains, tuple(rows), work_limit=100)
        assert not covers_product(domains, tuple(rows[:-1]), work_limit=1_000_000)


class PatternCoverageCheckSuite(testcheck.TypeCheckSuite):
    files = ["patterncoverage.test"]

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        # Lower the narrowing limit so these small examples reach the coverage fallback.
        # Keep the coverage budget at its normal value.
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(checkpattern, "MAX_TUPLE_PATTERN_REST_ITEMS", 2)
            super().run_case(testcase)
