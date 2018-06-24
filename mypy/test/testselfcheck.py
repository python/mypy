"""Self check mypy package"""

import pytest  # type: ignore  # no pytest in typeshed
from flake8.api import legacy as flake8  # type: ignore  # no falke8 in typeshed

from mypy.test.helpers import Suite, run_mypy


class SelfCheckSuite(Suite):
    def test_mypy_package(self) -> None:
        run_mypy(['-p', 'mypy'])

    def test_testrunner(self) -> None:
        run_mypy(['runtests.py', 'waiter.py'])


class LintSuite(Suite):
    def test_flake8(self) -> None:
        style_guide = flake8.get_style_guide()
        report = style_guide.check_files('.')
        if report.total_errors != 0:
            pytest.fail('Lint error', pytrace=False)
