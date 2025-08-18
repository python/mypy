from subprocess import run, PIPE
from functools import partial
from typing import Any

# TODO Would like help with this test, how do I make it runnable?

def test(expect_color: bool, *args: Any, **kwargs: Any) -> None:
    res = run(*args, stdout=PIPE, stderr=PIPE, **kwargs)
    if expect_color: # Expect color control chars
        assert "<string>:1: error:" not in res.stdout
        assert "\nFound" not in res.stdout
    else: # Expect no color control chars
        assert "<string>:1: error:" in res.stdout
        assert "\nFound" in res.stdout

colored = partial(test, True)
not_colored = partial(test, False)

def test_color_output() -> None:
    # Note: Though we don't check stderr, capturing it is useful
    # because it provides traceback if mypy crashes due to exception
    # and pytest reveals it upon failure (?)
    not_colored("mypy -c \"1+'a'\"")
    colored("mypy -c \"1+'a'\"", env={"MYPY_FORCE_COLOR": "1"})
    colored("mypy -c \"1+'a'\" --color-output")
    not_colored("mypy -c \"1+'a'\" --no-color-output")
    colored("mypy -c \"1+'a'\" --no-color-output", env={"MYPY_FORCE_COLOR": "1"}) #TODO

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