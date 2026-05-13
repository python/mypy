from __future__ import annotations

import os
import sys
import sysconfig
import tempfile
import unittest

from mypy import pyinfo


class GetSysPathSuite(unittest.TestCase):
    """Regression tests for mypy.pyinfo.getsyspath()."""

    @unittest.skipIf(sys.platform == "win32", "os.symlink requires elevated privileges on Windows")
    def test_excludes_stdlib_when_install_path_is_symlinked(self) -> None:
        """Regression test for python/mypy#21474.

        On Homebrew/pyenv/python-build-standalone, the Python install path is
        reached via a symlink (e.g. ``/opt/homebrew/opt/python@3.13`` ->
        ``/opt/homebrew/Cellar/python@3.13/3.13.7``). ``sys.base_exec_prefix``
        and ``sysconfig.get_path("stdlib")`` retain the symlink form, while
        entries of ``sys.path`` arrive pre-resolved by Python. ``getsyspath()``
        normalised both sides with ``os.path.abspath`` (which does not resolve
        symlinks), so the stdlib entry was never excluded and leaked into
        ``SearchPaths.package_path``.
        """
        ver = f"python{sys.version_info.major}.{sys.version_info.minor}"

        with tempfile.TemporaryDirectory() as tmp:
            real_prefix = os.path.join(tmp, "cellar")
            real_stdlib = os.path.join(real_prefix, "lib", ver)
            real_dynload = os.path.join(real_stdlib, "lib-dynload")
            os.makedirs(real_dynload)

            symlink_prefix = os.path.join(tmp, "opt")
            os.symlink(real_prefix, symlink_prefix)
            symlink_stdlib = os.path.join(symlink_prefix, "lib", ver)

            # Sanity check that the two paths really do differ textually but
            # resolve to the same directory — otherwise the bug isn't being
            # exercised at all.
            assert symlink_stdlib != real_stdlib
            assert os.path.samefile(symlink_stdlib, real_stdlib)

            original_base_exec_prefix = sys.base_exec_prefix
            original_path = sys.path[:]
            original_get_path = sysconfig.get_path

            def fake_get_path(name: str) -> str:
                assert name == "stdlib", f"unexpected get_path({name!r})"
                return symlink_stdlib

            try:
                sys.base_exec_prefix = symlink_prefix
                sysconfig.get_path = fake_get_path  # type: ignore[assignment]
                # First entry is dropped by getsyspath() unless safe_path is
                # on, so use a sentinel there.
                sys.path = ["<sentinel>", real_stdlib, real_dynload]

                result = pyinfo.getsyspath()
            finally:
                sys.base_exec_prefix = original_base_exec_prefix
                sysconfig.get_path = original_get_path
                sys.path = original_path

            leaked = [
                p
                for p in result
                if os.path.exists(p)
                and (os.path.samefile(p, real_stdlib) or os.path.samefile(p, real_dynload))
            ]
            self.assertEqual(
                leaked,
                [],
                f"stdlib leaked into getsyspath() result: {leaked!r} "
                f"(full result: {result!r})",
            )


if __name__ == "__main__":
    unittest.main()
