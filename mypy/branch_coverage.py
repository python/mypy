"""Branch Coverage Tracking Module"""

from __future__ import annotations

from pathlib import Path
from typing import Final

BRANCH_COVERAGE: dict[str, set[int]] = {"check_return_stmt": set()}

BRANCH_DESCRIPTIONS: Final[dict[str, dict[int, str]]] = {
    "check_return_stmt": {
        1: "Function entry",
        2: "defn is not None - TRUE",
        3: "defn is not None - FALSE",
        4: "defn.is_generator - TRUE",
        5: "defn.is_generator - FALSE (else/elif)",
        6: "defn.is_coroutine - TRUE",
        7: "defn.is_coroutine - FALSE (else)",
        8: "isinstance(return_type, UninhabitedType) - TRUE",
        9: "isinstance(return_type, UninhabitedType) - FALSE",
        10: "not is_lambda and not return_type.ambiguous - TRUE",
        11: "not is_lambda and not return_type.ambiguous - FALSE",
        12: "s.expr - TRUE (has return value)",
        13: "s.expr - FALSE (empty return)",
        14: "isinstance(s.expr, (CallExpr, ...)) or isinstance(s.expr, AwaitExpr) - TRUE",
        15: "isinstance(s.expr, (CallExpr, ...)) or isinstance(s.expr, AwaitExpr) - FALSE",
        16: "isinstance(typ, Instance) and typ.type.fullname in NOT_IMPLEMENTED - TRUE",
        17: "isinstance(typ, Instance) and typ.type.fullname in NOT_IMPLEMENTED - FALSE",
        18: "defn.is_async_generator - TRUE",
        19: "defn.is_async_generator - FALSE",
        20: "isinstance(typ, AnyType) - TRUE",
        21: "isinstance(typ, AnyType) - FALSE",
        22: "warn_return_any conditions - TRUE (all conditions met)",
        23: "warn_return_any conditions - FALSE (at least one condition not met)",
        24: "declared_none_return - TRUE",
        25: "declared_none_return - FALSE",
        26: "is_lambda or isinstance(typ, NoneType) - TRUE",
        27: "is_lambda or isinstance(typ, NoneType) - FALSE",
        28: "defn.is_generator and not defn.is_coroutine and isinstance(return_type, AnyType) - TRUE",
        29: "defn.is_generator and not defn.is_coroutine and isinstance(return_type, AnyType) - FALSE",
        30: "isinstance(return_type, (NoneType, AnyType)) - TRUE",
        31: "isinstance(return_type, (NoneType, AnyType)) - FALSE",
        32: "self.in_checked_function() - TRUE",
        33: "self.in_checked_function() - FALSE",
    }
}


def record_branch(function_name: str, branch_id: int) -> None:
    """Record that a branch has been executed."""
    if function_name in BRANCH_COVERAGE:
        BRANCH_COVERAGE[function_name].add(branch_id)


def get_coverage_report() -> str:
    """Generate a coverage report as a string."""
    report: list[str] = []
    report.append("=" * 80)
    report.append("BRANCH COVERAGE REPORT")
    report.append("=" * 80)

    for func_name, covered_branches in BRANCH_COVERAGE.items():
        report.append(f"\n{'=' * 80}")
        report.append(f"Function: {func_name}")
        report.append(f"{'=' * 80}")

        descriptions = BRANCH_DESCRIPTIONS.get(func_name, {})
        total_branches = len(descriptions)
        covered_count = len(covered_branches)

        report.append(
            f"Coverage: {covered_count}/{total_branches} branches ({covered_count / total_branches * 100:.1f}%)"
        )
        report.append("")

        for branch_id in sorted(descriptions.keys()):
            status = "COVERED" if branch_id in covered_branches else "NOT COVERED"
            desc = descriptions[branch_id]
            report.append(f"  Branch {branch_id:2d}: {status:15s} | {desc}")

        uncovered = set(descriptions.keys()) - covered_branches
        if uncovered:
            report.append("\n" + "=" * 80)
            report.append("UNCOVERED BRANCHES:")
            report.append("=" * 80)
            for branch_id in sorted(uncovered):
                report.append(f"  Branch {branch_id:2d}: {descriptions[branch_id]}")

    report.append("\n" + "=" * 80)
    return "\n".join(report)


def save_coverage_report(filename: str = "branch_coverage_report.txt") -> None:
    """Save the coverage report to a file."""
    report = get_coverage_report()
    output_path = Path.cwd() / filename
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nCoverage report saved to: {output_path}")
