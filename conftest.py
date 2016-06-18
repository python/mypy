import pytest

def pytest_addoption(parser):
    parser.addoption('--update-testcases', action='store_true',
                     dest='UPDATE_TESTCASES')

# mypy.test.helpers defines several top-level utility functions that
# pytest will pick up as tests. This removes them.
def pytest_collection_modifyitems(items):
    to_remove = []

    for i, item in enumerate(items):
        if (isinstance(item, pytest.Function) and
                item.function.__module__ == 'mypy.test.helpers' and
                # This is to prevent removing data-driven tests, which are
                # defined by mypy.test.helpers.PytestSuite.
                not getattr(item.function, 'is_test_attr', False)):
            to_remove.append(i)

    # reversed is to prevent changing indexes that haven't been removed yet.
    for index in reversed(to_remove):
        items.pop(index)
