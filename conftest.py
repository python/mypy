from mypy.test.helpers import PytestSuite
import inspect
import pytest

def pytest_addoption(parser):
    parser.addoption('--update-testcases', action='store_true',
                     dest='UPDATE_TESTCASES')

def pytest_pycollect_makeitem(collector, name, obj):
     if (inspect.isclass(obj) and issubclass(obj, PytestSuite) and
            obj is not PytestSuite):
        print(name)
        obj.collect_tests()
