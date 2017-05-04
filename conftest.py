import pytest

pytest_plugins = [
    'mypy.test.data',
]


def pytest_addoption(parser):
    parser.addoption("--casefile", action="store")
