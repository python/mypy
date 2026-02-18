"""
Pytest configuration for branch coverage collection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.main import Session


def pytest_sessionfinish(session: Session, exitstatus: int) -> None:
    """
    Hook that runs after all tests complete
    """
    try:
        from mypy.branch_coverage import BRANCH_COVERAGE, get_coverage_report, save_coverage_report

        total_covered = sum(len(branches) for branches in BRANCH_COVERAGE.values())

        if total_covered > 0:
            print("\n" + "=" * 80)
            print("BRANCH COVERAGE COLLECTION COMPLETED")
            print("=" * 80)
            print(f"Total branches covered: {total_covered}")

            save_coverage_report()

            print("\n" + get_coverage_report())

            print("\n" + "=" * 80)
            print("Coverage reports saved!")
            print("=" * 80)
        else:
            print("\nWarning: No branch coverage data collected")

    except ImportError:
        print("\nBranch coverage module not found - skipping coverage report")
    except Exception as e:
        print(f"\nError saving coverage report: {e}")
        import traceback

        traceback.print_exc()
