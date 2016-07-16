"""Ensure the argparse parser and Options class are in sync.

In particular, verify that the argparse defaults are the same as the Options
defaults, and that argparse doesn't assign any new members to the Options
object it creates.
"""

import typing

from mypy.myunit import Suite, assert_equal
from mypy.options import Options, BuildType
from mypy.main import process_options


class ArgSuite(Suite):
    def test_coherence(self):
        # We have to special case Options.BuildType because we're required to
        # set a target
        options = Options()
        options.build_type = BuildType.PROGRAM_TEXT
        _, parsed_options = process_options(['-c', 'cmd'])
        assert_equal(options, parsed_options)
