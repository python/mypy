from __future__ import annotations

import os
import tempfile
import textwrap
import unittest

from mypy.installtypes import (
    make_runtime_constraints,
    read_locked_packages,
    resolve_stub_packages_from_lock,
)


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

    def test_resolve_stub_packages_from_lock(self) -> None:
        locked = {
            "requests": "2.32.3",
            "python-dateutil": "2.9.0",
            "types-requests": "2.32.0",
        }
        stubs = resolve_stub_packages_from_lock(locked)
        assert "types-requests" in stubs
        assert "types-python-dateutil" in stubs

    def test_make_runtime_constraints(self) -> None:
        locked = {
            "requests": "2.32.3",
            "python-dateutil": "2.9.0",
            "no-version": None,
        }
        constraints = make_runtime_constraints(locked)
        assert constraints == ["python-dateutil==2.9.0", "requests==2.32.3"]