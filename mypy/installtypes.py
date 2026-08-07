from __future__ import annotations

import re
import sys
from collections.abc import Mapping

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from mypy.stubinfo import (
    non_bundled_packages_flat,
    non_bundled_packages_namespace,
    stub_distribution_name,
)

_DIST_NORMALIZE_RE = re.compile(r"[-_.]+")


def normalize_distribution_name(name: str) -> str:
    return _DIST_NORMALIZE_RE.sub("-", name).lower()


DIST_TO_MODULE_NAME: dict[str, str] = {
    "python-dateutil": "dateutil",
    "pyyaml": "yaml",
    "python-xlib": "Xlib",
}


def read_locked_packages(path: str) -> dict[str, str | None]:
    """Read package name/version pairs from a pylock-like TOML file.

    Supports common lockfile layouts that use either [[package]] or
    [[packages]] tables with "name" and optional "version" keys.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    entries: list[object] = []
    for key in ("package", "packages"):
        value = data.get(key)
        if isinstance(value, list):
            entries.extend(value)

    locked: dict[str, str | None] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        version_obj = entry.get("version")
        version = version_obj if isinstance(version_obj, str) and version_obj.strip() else None
        locked[normalize_distribution_name(name)] = version

    return locked


def resolve_stub_packages_from_lock(locked: Mapping[str, str | None]) -> list[str]:
    """Map runtime packages from a lock file to known stubs packages.

    This uses mypy's existing known typeshed mapping and intentionally skips
    heuristics that could cause accidental installation of unrelated packages.
    """
    known_stubs = set(non_bundled_packages_flat.values())
    for namespace_packages in non_bundled_packages_namespace.values():
        known_stubs.update(namespace_packages.values())

    stubs: set[str] = set()
    for dist_name in locked:
        if dist_name.startswith("types-"):
            continue

        candidates = {dist_name, dist_name.replace("-", "_")}

        mapped_module = DIST_TO_MODULE_NAME.get(dist_name)
        if mapped_module is not None:
            candidates.add(mapped_module)

        for module_name in candidates:
            stub = stub_distribution_name(module_name)
            if stub:
                stubs.add(stub)

        typeshed_name = f"types-{dist_name}"
        if typeshed_name in known_stubs:
            stubs.add(typeshed_name)
    return sorted(stubs)


def make_runtime_constraints(locked: Mapping[str, str | None]) -> list[str]:
    """Create pip constraints that pin runtime packages to locked versions."""
    constraints: list[str] = []
    for name, version in sorted(locked.items()):
        if version:
            constraints.append(f"{name}=={version}")
    return constraints
