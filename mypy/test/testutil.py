import os
from unittest import mock, TestCase

from mypy.util import get_terminal_width


class TestGetTerminalSize(TestCase):
    def test_get_terminal_size_in_pty_defaults_to_80(self) -> None:
        # when run using a pty, `os.get_terminal_size()` returns `0, 0`
        ret = os.terminal_size((0, 0))
        with mock.patch.object(os, 'get_terminal_size', return_value=ret):
            assert get_terminal_width() == 80
