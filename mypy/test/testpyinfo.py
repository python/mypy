from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mypy import pyinfo


class TestPyInfo(unittest.TestCase):
    def test_getsyspath_excludes_symlinked_stdlib(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_stdlib = root / "real" / "lib" / "python3.13"
            real_stdlib.mkdir(parents=True)
            symlinked_stdlib = root / "link" / "lib" / "python3.13"
            symlinked_stdlib.parent.parent.symlink_to(root / "real", target_is_directory=True)
            site_packages = root / "site-packages"
            site_packages.mkdir()

            with (
                patch.object(pyinfo.sys, "base_exec_prefix", str(root)),
                patch.object(
                    pyinfo.sysconfig, "get_path", autospec=True, return_value=str(symlinked_stdlib)
                ),
                patch.object(
                    pyinfo.sys, "path", [str(root), str(real_stdlib), str(site_packages)]
                ),
            ):
                search_path = pyinfo.getsyspath()

        assert os.path.abspath(real_stdlib) not in search_path
        assert os.path.abspath(site_packages) in search_path


if __name__ == "__main__":
    unittest.main()
