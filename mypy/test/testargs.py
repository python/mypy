"""Ensure the argparse parser and Options class are in sync.

In particular, verify that the argparse defaults are the same as the Options
defaults, and that argparse doesn't assign any new members to the Options
object it creates.
"""

from mypy.test.helpers import Suite
from mypy.options import Options
from mypy.main import process_options


class ArgSuite(Suite):
    def test_coherence(self) -> None:
        options = Options()
        _, parsed_options = process_options([], require_targets=False)
        assert options.__dict__.keys() == parsed_options.__dict__.keys()
        for k in options.__dict__:
            assert getattr(options, k) == getattr(parsed_options, k), k
