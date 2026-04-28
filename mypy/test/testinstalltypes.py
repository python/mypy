from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from types import SimpleNamespace #ADDED
from unittest.mock import patch #ADDED

from mypy.installtypes import (
    make_runtime_constraints,
    read_locked_packages,
    resolve_stub_packages_from_lock,
)
from mypy.main import install_types #ADDED


class TestInstallTypesFromPylock(unittest.TestCase):
    def test_read_locked_packages(self) -> None:
        content = textwrap.dedent(
            """
            [[package]]
            name = "requests"
            version = "2.32.3"

            [[packages]]
            name = "python-dateutil"
            version = "2.9.0"

            [[package]]
            name = "types-requests"
            version = "2.32.0"
            """
        )
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            locked = read_locked_packages(path)
        finally:
            os.unlink(path)

        assert locked["requests"] == "2.32.3"
        assert locked["python-dateutil"] == "2.9.0"
        assert locked["types-requests"] == "2.32.0"

    def test_read_locked_packages_missing_version(self) -> None:
        content = textwrap.dedent("""
            [[package]]
            name = "requests"
        """)
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            locked = read_locked_packages(path)
        finally:
            os.unlink(path)
        assert "requests" in locked
        assert locked["requests"] is None

    def test_read_locked_packages_normalizes_names(self) -> None:
        content = textwrap.dedent("""
            [[package]]
            name = "My_Package"
            version = "1.0.0"
        """)
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            locked = read_locked_packages(path)
        finally:
            os.unlink(path)
        # Should be normalized to "my-package"
        assert "my-package" in locked
        assert locked["my-package"] == "1.0.0"

    def test_read_locked_packages_empty_file(self) -> None:
        content = ""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            locked = read_locked_packages(path)
        finally:
            os.unlink(path)
        assert locked == {}

    def test_resolve_stub_packages_from_lock(self) -> None:
        locked = {
            "requests": "2.32.3",
            "python-dateutil": "2.9.0",
            "types-requests": "2.32.0",
        }
        stubs = resolve_stub_packages_from_lock(locked)
        # requests already worked before fix because distribution name == module name.
        assert "types-requests" in stubs

        # FIX: Before my fix, this failed because the lock file used the distribution name
        # "python-dateutil" but stubinfo.py knows the module/import name "dateutil".
        # After adding the explicit distribution->module mapping, it should resolve.
        assert "types-python-dateutil" in stubs #FIX

    #TEST: checks explicit distribution->module mapping
    def test_resolve_stub_packages_from_lock_handles_distribution_module_mismatch(self) -> None:
        locked = {
            "python-dateutil": "2.9.0",
        }
        stubs = resolve_stub_packages_from_lock(locked)
        assert "types-python-dateutil" in stubs
    
    def test_resolve_stub_packages_skips_types_packages(self) -> None:
        locked = {
            "types-requests": "2.32.0",
        }
        stubs = resolve_stub_packages_from_lock(locked)
        # Should not produce "types-types-requests"
        assert "types-types-requests" not in stubs

    def test_resolve_stub_packages_empty_lock(self) -> None:
        stubs = resolve_stub_packages_from_lock({})
        assert stubs == []

    def test_resolve_stub_packages_unknown_package(self) -> None:
        locked = {"some-totally-unknown-lib-xyz": "1.0.0"}
        stubs = resolve_stub_packages_from_lock(locked)
        assert stubs == []

    def test_resolve_stub_packages_pyyaml_mapping(self) -> None:
        locked = {"pyyaml": "6.0.1"}
        stubs = resolve_stub_packages_from_lock(locked)
        assert "types-PyYAML" in stubs

    def test_make_runtime_constraints(self) -> None:
        locked = {
            "requests": "2.32.3",
            "python-dateutil": "2.9.0",
            "no-version": None,
        }
        constraints = make_runtime_constraints(locked)
        assert constraints == ["python-dateutil==2.9.0", "requests==2.32.3"]

    def test_make_runtime_constraints_skips_none_versions(self) -> None:
        locked = {"requests": None, "python-dateutil": "2.9.0"}
        constraints = make_runtime_constraints(locked)
        assert "requests" not in " ".join(constraints)
        assert "python-dateutil==2.9.0" in constraints

    def test_make_runtime_constraints_empty(self) -> None:
        locked = {}
        assert make_runtime_constraints(locked) == []

    def test_make_runtime_constraints_is_sorted(self) -> None:
        locked = {"zebra-lib": "1.0", "alpha-lib": "2.0"}
        constraints = make_runtime_constraints(locked)
        assert constraints == sorted(constraints)

#FIX: stub/mock object that pretends to be a formatter so tests don’t crash.
class DummyFormatter:
    def style(self, text: str, *args: object, **kwargs: object) -> str:
        return text

#TEST: integrations tests
class TestInstallTypesFromPylockIntegration(unittest.TestCase):
    def make_options(self) -> SimpleNamespace:
        return SimpleNamespace(
            python_executable="python",
            cache_dir="unused",
        )

    @patch("mypy.main.subprocess.run")
    def test_install_types_builds_correct_pip_command(self, mock_run) -> None:
        content = textwrap.dedent(
            """
            [[package]]
            name = "requests"
            version = "2.32.3"

            [[package]]
            name = "python-dateutil"
            version = "2.9.0"
            """
        )

        with tempfile.NamedTemporaryFile(
            "w", suffix=".toml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            options = self.make_options()
            formatter = DummyFormatter() #FIX

            result = install_types(
                # formatter=None,
                formatter=formatter, # FIX
                options=options,
                non_interactive=True,
                pylock_path=path,
            )

            self.assertTrue(result)
            mock_run.assert_called_once()

            cmd = mock_run.call_args[0][0]

            # Check pip command structure
            self.assertEqual(cmd[:4], ["python", "-m", "pip", "install"])

            # Critical behavior
            self.assertIn("--no-deps", cmd)
            self.assertIn("--constraint", cmd)

            # Stub packages should be installed
            # requests already resolved before the fix.
            self.assertIn("types-requests", cmd)

            # FIX: Before the fix, this was missing from the pip command because
            # resolve_stub_packages_from_lock only tried "python-dateutil" and
            # "python_dateutil", but stubinfo.py maps "dateutil" -> "types-python-dateutil".
            # After adding the explicit distribution->module mapping, install_types()
            # should include the correct stub package in the pip command.
            self.assertIn("types-python-dateutil", cmd)

        finally:
            os.unlink(path)

    @patch("mypy.main.subprocess.run")
    def test_no_stubs_found_skips_install(self, mock_run) -> None:
        content = textwrap.dedent(
            """
            [[package]]
            name = "unknown-lib"
            version = "1.0.0"
            """
        )

        with tempfile.NamedTemporaryFile(
            "w", suffix=".toml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            options = self.make_options()
            formatter = DummyFormatter() #FIX

            result = install_types(
                # formatter=None,
                formatter=formatter, #FIX
                options=options,
                non_interactive=True,
                pylock_path=path,
            )

            self.assertFalse(result)
            mock_run.assert_not_called()

        finally:
            os.unlink(path)

    @patch("mypy.main.subprocess.run")
    def test_constraint_file_cleaned_up_after_success(self, mock_run) -> None:
        content = textwrap.dedent(
            """
            [[package]]
            name = "requests"
            version = "2.32.3"
            """
        )
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        captured: list[str] = []

        def capture_cmd(cmd: list[str], **kwargs: object) -> None:
            if "--constraint" in cmd:
                captured.append(cmd[cmd.index("--constraint") + 1])

        mock_run.side_effect = capture_cmd

        try:
            install_types(
                formatter=DummyFormatter(),
                options=self.make_options(),
                non_interactive=True,
                pylock_path=path,
            )
        finally:
            os.unlink(path)

        self.assertEqual(len(captured), 1)
        self.assertFalse(
            os.path.exists(captured[0]),
            "Temp constraint file should be deleted after successful run",
        )

    @patch("mypy.main.subprocess.run")
    def test_constraint_file_cleaned_up_even_if_subprocess_fails(self, mock_run) -> None:
        content = textwrap.dedent(
            """
            [[package]]
            name = "requests"
            version = "2.32.3"
            """
        )
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        captured: list[str] = []

        def capture_and_raise(cmd: list[str], **kwargs: object) -> None:
            if "--constraint" in cmd:
                captured.append(cmd[cmd.index("--constraint") + 1])
            raise RuntimeError("pip exploded")

        mock_run.side_effect = capture_and_raise

        try:
            with self.assertRaises(RuntimeError):
                install_types(
                    formatter=DummyFormatter(),
                    options=self.make_options(),
                    non_interactive=True,
                    pylock_path=path,
                )
        finally:
            os.unlink(path)

        self.assertEqual(len(captured), 1)
        self.assertFalse(
            os.path.exists(captured[0]),
            "Temp constraint file should be deleted even when subprocess raises",
        )