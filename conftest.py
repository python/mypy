pytest_plugins = [
    'mypy.test.data',
]
# This function name is special to pytest.  See
# http://doc.pytest.org/en/latest/writing_plugins.html#initialization-command-line-and-configuration-hooks
def pytest_addoption(parser)-> None:
    parser.addoption('--bench', action='store_true', default=False,
                     help='Enable the benchmark test runs')
