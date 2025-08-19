from functools import partial
from subprocess import PIPE, run
from typing import Any

import pytest

# TODO Would like help with this test, how do I make it runnable?


def test(expect_color: bool, *args: Any, **kwargs: Any) -> None:
    res = run(*args, capture_output=True, **kwargs)
    if "Found" not in res.stdout:  # ??
        pytest.fail("Command failed to complete or did not detect type error")
    if expect_color:  # Expect color control chars
        assert "<string>:1: error:" not in res.stdout
        assert "\nFound" not in res.stdout
    else:  # Expect no color control chars
        assert "<string>:1: error:" in res.stdout
        assert "\nFound" in res.stdout


colored = partial(test, True)
not_colored = partial(test, False)


@pytest.mark.parametrize("command", ["mypy", "dmypy run --"])
def test_color_output(command: str) -> None:
    # Note: Though we don't check stderr, capturing it is useful
    # because it provides traceback if mypy crashes due to exception
    # and pytest reveals it upon failure (?)
    not_colored(f"{command} -c \"1+'a'\"")
    colored(f"{command} -c \"1+'a'\"", env={"MYPY_FORCE_COLOR": "1"})
    colored(f"{command} -c \"1+'a'\" --color-output")
    not_colored(f"{command} -c \"1+'a'\" --no-color-output")
    colored(f"{command} -c \"1+'a'\" --no-color-output", env={"MYPY_FORCE_COLOR": "1"})  # TODO


# TODO: Tests in the terminal (require manual testing?)
"""
In the terminal:
    colored: mypy -c "1+'a'"
    colored: mypy -c "1+'a'" --color-output
not colored: mypy -c "1+'a'" --no-color-output
    colored: mypy -c "1+'a'" --color-output (with MYPY_FORCE_COLOR=1)
    colored: mypy -c "1+'a'" --no-color-output (with MYPY_FORCE_COLOR=1)

To test, save this as a .bat and run in a Windows terminal (I don't know the Unix equivalent):

set MYPY_FORCE_COLOR=
mypy -c "1+'a'"
mypy -c "1+'a'" --color-output
mypy -c "1+'a'" --no-color-output
set MYPY_FORCE_COLOR=1
mypy -c "1+'a'" --color-output
mypy -c "1+'a'" --no-color-output
set MYPY_FORCE_COLOR=
"""
