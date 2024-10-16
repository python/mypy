from __future__ import annotations

import unittest

from mypy.stubinfo import (
    legacy_bundled_dist_from_module,
    legacy_bundled_packages,
    non_bundled_packages,
)


class TestStubInfo(unittest.TestCase):
    def test_is_legacy_bundled_packages(self) -> None:
        assert legacy_bundled_dist_from_module("foobar_asdf") is None
        assert legacy_bundled_dist_from_module("pycurl") == "types-pycurl"
        assert legacy_bundled_dist_from_module("dataclasses") == "types-dataclasses"

    def test_period_in_top_level(self) -> None:
        for packages in (non_bundled_packages, legacy_bundled_packages):
            for top_level_module in packages:
                assert "." not in top_level_module
