"""Ensure the argparse parser and Options class are in sync.

In particular, verify that the argparse defaults are the same as the Options
defaults, and that argparse doesn't assign any new members to the Options
object it creates.
"""

from mypy.test.helpers import Suite, assert_equal
from mypy.options import Options
from mypy.main import process_options


class ArgSuite(Suite):
    def test_coherence(self) -> None:
        options = Options()
        _, parsed_options = process_options([], require_targets=False)
        # FIX: test this too. Requires changing working dir to avoid finding 'setup.cfg'
        options.config_file = parsed_options.config_file
        assert_equal(dir(options), dir(parsed_options))
