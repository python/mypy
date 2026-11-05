"""Test that SAFE_STUB_BASE_CLASSES matches how mypy resolves the classes in typeshed.

The allowlist contains the full names mypy uses for base classes, which are those of the
modules where typeshed defines the classes (e.g. asyncio.protocols.Protocol). If typeshed
moves a class, its full name changes and native subclasses would be rejected, so check
the names after semantic analysis and type checking.

This only checks the current Python version and platform, since CI runs the tests on all
supported versions and the main platforms.
"""

from __future__ import annotations

import sys
import unittest

from mypy import build
from mypy.modulefinder import BuildSource
from mypy.nodes import TypeInfo
from mypy.options import Options
from mypyc.irbuild.safe_bases import SAFE_STUB_BASE_CLASSES


def resolve_bases(names: list[str]) -> dict[str, str]:
    """Type check a subclass of each class and return {allowlist name: base full name}.

    This targets the current Python version and platform. Classes that don't exist on
    the target (e.g. added in a later Python version) are left out.
    """
    lines = []
    for i, name in enumerate(names):
        module, short = name.rsplit(".", 1)
        # Import the class by name, since a module attribute may shadow a submodule
        # (unittest.main is a function as well as a module)
        lines.append(f"from {module} import {short} as _B{i}")
    for i in range(len(names)):
        lines.append(f"class C{i}(_B{i}): pass")
    options = Options()
    options.incremental = False
    result = build.build([BuildSource("main.py", "main", "\n".join(lines) + "\n")], options)
    tree = result.files["main"]
    resolved = {}
    for i, name in enumerate(names):
        info = tree.names[f"C{i}"].node
        assert isinstance(info, TypeInfo)
        if info.fallback_to_any or not info.bases:
            continue
        base = info.bases[0].type.fullname
        if base != "builtins.object":
            resolved[name] = base
    return resolved


class TestSafeBases(unittest.TestCase):
    def test_allowlist_matches_typeshed(self) -> None:
        target = f"Python {sys.version_info[0]}.{sys.version_info[1]} on {sys.platform}"
        resolved = resolve_bases(sorted(SAFE_STUB_BASE_CLASSES))
        assert resolved, "No allowlisted classes were found"
        for name, fullname in resolved.items():
            # A name may resolve to another entry on some Python versions (e.g.
            # typing.ContextManager is contextlib.AbstractContextManager on 3.13+), but
            # the result must always be in the list.
            assert fullname in SAFE_STUB_BASE_CLASSES, (
                f"{name} resolves to {fullname} for {target}, which isn't in "
                "SAFE_STUB_BASE_CLASSES (did typeshed move the class?)"
            )
