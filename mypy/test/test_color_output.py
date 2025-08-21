from functools import partial
import subprocess
from typing import TYPE_CHECKING, Any
import sys
import pytest

#XXX Would like help with this test, how do I make it runnable?

# Haven't run this test yet

PTY_SIZE = (80, 40)

if sys.platform == "win32":
    if TYPE_CHECKING:
        from winpty.winpty import PTY
    else:
        from winpty import PTY

    def run_pty(cmd: str, env: dict[str, str] = {}) -> tuple[str, str]:
        pty = PTY(*PTY_SIZE)
        # For the purposes of this test, str.split() is enough
        appname, cmdline = cmd.split(maxsplit=1)
        pty.spawn(appname, cmdline, "\0".join(map(lambda kv: f"{kv[0]}={kv[1]}", env.items())))
        while pty.isalive():
            pass
        return pty.read(), pty.read_stderr()
elif sys.platform == "unix":
    from pty import openpty

    def run_pty(cmd: str, env: dict[str, str] = {}) -> tuple[str, str]:
        # TODO Would like help checking quality of this function,
        # it's partially written by Copilot because I'm not familiar with Unix openpty
        master_fd, slave_fd = openpty()
        try:
            p = subprocess.run(cmd, stdout=slave_fd, stderr=subprocess.PIPE, env=env, text=True)
            os.close(slave_fd)
            return os.read(slave_fd, 10000).decode(), p.stderr
        finally:
            os.close(master_fd)
def test(expect_color: bool, pty: bool, cmd: str, env: dict[str, str] = {}) -> None:
    if pty:
        stdout, stderr = run_pty(cmd, env=env)
    else:
        proc = subprocess.run(cmd, capture_output=True, env=env, text=True)
        stdout = proc.stdout
        stderr = proc.stderr
    if "Found" not in stdout:  # ??
        pytest.fail("Command failed to complete or did not detect type error")
    if expect_color:  # Expect color control chars
        assert "<string>:1: error:" not in stdout
        assert "\nFound" not in stdout
    else:  # Expect no color control chars
        assert "<string>:1: error:" in stdout
        assert "\nFound" in stdout


def test_pty(expect_color: bool, cmd: str, env: dict[str, str] = {}) -> None:
    test(expect_color, True, cmd, env)

def test_not_pty(expect_color: bool, cmd: str, env: dict[str, str] = {}) -> None:
    test(expect_color, False, cmd, env)


@pytest.mark.parametrize("command", ["mypy", "dmypy run --"])
def test_it(command: str) -> None:
    # Note: Though we don't check stderr, capturing it is useful
    # because it provides traceback if mypy crashes due to exception
    # and pytest reveals it upon failure (?)
    test_pty(True, "mypy -c \"1+'a'\" --color-output=force")
    test_pty(False, "mypy -c \"1+'a'\" --no-color-output")
    test_not_pty(False, "mypy -c \"1+'a'\" --color-output")
    test_not_pty(True, "mypy -c \"1+'a'\" --color-output=force")
    test_not_pty(False, "mypy -c \"1+'a'\" --color-output", {"MYPY_FORCE_COLOR": "1"})
    test_not_pty(True, "mypy -c \"1+'a'\" --color-output=force", {"MYPY_FORCE_COLOR": "1"})
    test_not_pty(False, "mypy -c \"1+'a'\" --no-color-output", {"MYPY_FORCE_COLOR": "1"})
    test_not_pty(False, "mypy -c \"1+'a'\" --no-color-output", {"FORCE_COLOR": "1"})
    test_not_pty(False, "mypy -c \"1+'a'\" --color-output", {"MYPY_FORCE_COLOR": "0"})


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
