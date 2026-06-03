#!/usr/bin/env python3
"""
Aggregate the full-parse profile log produced by mypy's
SemanticAnalyzer.try_parse_as_type_expression() when run with
MYPY_TYPEFORM_PROFILE_FULL_PARSE set.

Usage:
    # 1. Run mypy with the profile env var set; per-PID log files are
    #    written as "<path>.<pid>":
    MYPY_TYPEFORM_PROFILE_FULL_PARSE=/tmp/tf.log \\
        python3 -m mypy --no-incremental -p your_package

    # 2. Aggregate one or more per-PID files:
    python3 misc/analyze_typeform_full_parse_profile.py /tmp/tf.log.*

    # Optional: limit per-descriptor breakdown to top N rows per class.
    python3 misc/analyze_typeform_full_parse_profile.py --top 20 /tmp/tf.log.*

The script summarizes which (outcome, kind, subkind) classes account for
the most full-parse time, and lists the top descriptors within each
FAIL class -- the populations worth targeting with cheaper pre-filters
upstream in try_parse_as_type_expression.

See also:
    - mypy/semanal.py: SemanticAnalyzer.try_parse_as_type_expression()
    - mypy/semanal.py: _log_typeform_full_parse() (TSV schema docstring)
    - misc/analyze_typeform_stats.py (aggregate counters via --dump-build-stats)
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable


def read_rows(paths: Iterable[str]) -> list[tuple[str, str, str, str, int]]:
    rows: list[tuple[str, str, str, str, int]] = []
    for path in paths:
        with open(path) as f:
            for line in f:
                # Skip header lines (each per-PID file starts with one).
                if line.startswith("outcome\t"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                outcome, kind, subkind, desc, dur_ns_str = parts[:5]
                try:
                    dur_ns = int(dur_ns_str)
                except ValueError:
                    continue
                rows.append((outcome, kind, subkind, desc, dur_ns))
    return rows


def print_class_summary(rows: list[tuple[str, str, str, str, int]]) -> None:
    buckets: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    total_ns = 0
    for outcome, kind, subkind, _desc, dur_ns in rows:
        buckets[(outcome, kind, subkind)].append(dur_ns)
        total_ns += dur_ns

    print("Class summary (by total time):")
    print("=" * 80)
    print(f"{'count':>7} {'total_ms':>10} {'mean_us':>9} {'med_us':>9} {'pct':>6}  class")
    print("-" * 80)
    ordered = sorted(
        (
            (sum(d), len(d), statistics.mean(d), statistics.median(d), key)
            for key, d in buckets.items()
        ),
        reverse=True,
    )
    for total, n, mean, med, key in ordered:
        pct = (100 * total / total_ns) if total_ns else 0
        outcome, kind, subkind = key
        print(
            f"{n:>7} {total/1e6:>10.2f} {mean/1e3:>9.1f} {med/1e3:>9.1f} "
            f"{pct:>5.1f}%  {outcome} {kind} {subkind}"
        )
    print("-" * 80)
    print(f"TOTAL: {len(rows):,} events, {total_ns/1e6:.2f} ms")


def print_fail_descriptors(rows: list[tuple[str, str, str, str, int]], top_n: int) -> None:
    # Group FAIL rows by (kind, subkind) class, then by descriptor within each.
    by_class: dict[tuple[str, str, str], dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for outcome, kind, subkind, desc, dur_ns in rows:
        if outcome != "FAIL":
            continue
        by_class[(outcome, kind, subkind)][desc].append(dur_ns)

    # Order classes by total FAIL time, descending.
    class_totals = sorted(
        ((sum(sum(d) for d in descs.values()), key, descs) for key, descs in by_class.items()),
        reverse=True,
    )
    for total_ns, key, descs in class_totals:
        outcome, kind, subkind = key
        print()
        print(
            f"Top {top_n} descriptors in {outcome} {kind} {subkind} "
            f"(class total {total_ns/1e6:.2f} ms):"
        )
        print("-" * 80)
        print(f"{'count':>6} {'total_ms':>10} {'mean_us':>9}  descriptor")
        rows_d = sorted(
            ((sum(d), len(d), statistics.mean(d), desc) for desc, d in descs.items()), reverse=True
        )
        for tot, n, mean, desc in rows_d[:top_n]:
            print(f"{n:>6} {tot/1e6:>10.3f} {mean/1e3:>9.1f}  {desc!r}")
        if len(rows_d) > top_n:
            print(f"... {len(rows_d) - top_n} more descriptors")


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__
    )
    parser.add_argument(
        "files", nargs="+", help="One or more per-PID profile files (e.g. /tmp/tf.log.*)"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Max number of descriptors to list per FAIL class (default: 20)",
    )
    args = parser.parse_args()

    rows = read_rows(args.files)
    if not rows:
        print("No data rows found in input files.", file=sys.stderr)
        sys.exit(1)

    print_class_summary(rows)
    print_fail_descriptors(rows, args.top)


if __name__ == "__main__":
    main()
