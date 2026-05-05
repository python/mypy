#!/usr/bin/env python3
"""
Analyze TypeForm parsing efficiency from mypy build stats.

Usage:
    python3 analyze_typeform_stats.py '<mypy_output_with_stats>'
    python3 -m mypy --dump-build-stats file.py 2>&1 | python3 analyze_typeform_stats.py

Example output:
    TypeForm Expression Parsing Statistics:
    ==================================================
    Total calls to SA.try_parse_as_type_expression: 14,555
    Quick rejections (no full parse): 14,255
    Full parses attempted: 300
    - Successful: 248
    - Failed: 52

    Efficiency Metrics:
    - Quick rejection rate: 97.9%
    - Full parse rate: 2.1%
    - Full parse success rate: 82.7%
    - Overall success rate: 1.7%

    Performance Implications:
    - Expensive failed full parses: 52 (0.4% of all calls)

See also:
    - mypy/semanal.py: SemanticAnalyzer.try_parse_as_type_expression()
    - mypy/semanal.py: DEBUG_TYPE_EXPRESSION_FULL_PARSE_FAILURES
"""

import re
import sys


def analyze_stats(output: str) -> None:
    """Parse mypy stats output and calculate TypeForm parsing efficiency."""

    # Extract the three counters
    total_match = re.search(r"type_expression_parse_count:\s*(\d+)", output)
    success_match = re.search(r"type_expression_full_parse_success_count:\s*(\d+)", output)
    failure_match = re.search(r"type_expression_full_parse_failure_count:\s*(\d+)", output)

    if not (total_match and success_match and failure_match):
        print("Error: Could not find all required counters in output")
        return

    total = int(total_match.group(1))
    successes = int(success_match.group(1))
    failures = int(failure_match.group(1))

    full_parses = successes + failures

    print("TypeForm Expression Parsing Statistics:")
    print("=" * 50)
    print(f"Total calls to SA.try_parse_as_type_expression: {total:,}")
    print(f"Quick rejections (no full parse): {total - full_parses:,}")
    print(f"Full parses attempted: {full_parses:,}")
    print(f"  - Successful: {successes:,}")
    print(f"  - Failed: {failures:,}")
    if total > 0:
        print()
        print("Efficiency Metrics:")
        print(f"  - Quick rejection rate: {((total - full_parses) / total * 100):.1f}%")
        print(f"  - Full parse rate: {(full_parses / total * 100):.1f}%")
        print(f"  - Full parse success rate: {(successes / full_parses * 100):.1f}%")
        print(f"  - Overall success rate: {(successes / total * 100):.1f}%")
        print()
        print("Performance Implications:")
        print(
            f"  - Expensive failed full parses: {failures:,} ({(failures / total * 100):.1f}% of all calls)"
        )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Read from stdin
        output = sys.stdin.read()
    elif len(sys.argv) == 2:
        # Read from command line argument
        output = sys.argv[1]
    else:
        print("Usage: python3 analyze_typeform_stats.py [mypy_output_with_stats]")
        print("Examples:")
        print(
            "  python3 -m mypy --dump-build-stats file.py 2>&1 | python3 analyze_typeform_stats.py"
        )
        print("  python3 analyze_typeform_stats.py 'output_string'")
        sys.exit(1)

    analyze_stats(output)
