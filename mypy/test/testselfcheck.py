"""Self check mypy package"""

from mypy.test.helpers import Suite, run_mypy


class SelfCheckSuite(Suite):
    def test_mypy_package(self) -> None:
        run_mypy(['-p', 'mypy'])

    def test_testrunner(self) -> None:
        run_mypy(['runtests.py', 'waiter.py'])
