import os.path

import pytest

pytest_plugins = [
    'mypy.test.data',
]


def pytest_configure(config):
    mypy_source_root = os.path.dirname(os.path.abspath(__file__))
    if os.getcwd() != mypy_source_root:
        os.chdir(mypy_source_root)
