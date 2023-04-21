from __future__ import annotations

import os.path

pytest_plugins = ["mypy.test.data"]


def pytest_configure(config):
    mypy_source_root = os.path.dirname(os.path.abspath(__file__))
    if os.getcwd() != mypy_source_root:
        os.chdir(mypy_source_root)


# This function name is special to pytest.  See
# https://doc.pytest.org/en/latest/how-to/writing_plugins.html#initialization-command-line-and-configuration-hooks
def pytest_addoption(parser) -> None:
    parser.addoption(
        "--bench", action="store_true", default=False, help="Enable the benchmark test runs"
    )
