"""Self check mypy package"""

from mypy.test.helpers import Suite, run_mypy


class SelfCheckSuite(Suite):
    def test_mypy_package(self) -> None:
        run_mypy(['--config-file', 'mypy_self_check.ini', '-p', 'mypy'])

    def test_testrunner(self) -> None:
        run_mypy(['--config-file', 'mypy_self_check.ini',
                  '--no-warn-unused-configs', 'runtests.py', 'waiter.py'])
