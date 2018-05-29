"""Self check mypy package"""
import sys
from typing import List

import pytest  # type: ignore

from mypy.test.helpers import Suite
from mypy.api import run


class SelfCheckSuite(Suite):
    def test_mypy_package(self) -> None:
        run_mypy(['-p', 'mypy'])

    def test_testrunner(self) -> None:
        run_mypy(['runtests.py', 'waiter.py'])


def run_mypy(args: List[str]) -> None:
    __tracebackhide__ = True
    outval, errval, status = run(args + ['--config-file', 'mypy_self_check.ini',
                                         '--show-traceback',
                                         '--no-site-packages'])
    if status != 0:
        sys.stdout.write(outval)
        errval = '\n'.join(line for line in errval.split('\n')
                           if 'mypy_self_check.ini' not in line)
        sys.stderr.write(errval)
        pytest.fail(msg="Self check failed", pytrace=False)
