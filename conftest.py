import pytest

def pytest_addoption(parser):
    parser.addoption('--update-testcases', action='store_true',
                     dest='UPDATE_TESTCASES')
