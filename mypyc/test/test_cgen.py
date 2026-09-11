"""End-to-end tests for the mypyc cgen CLI.

These spawn real C compilations, so they are slow-ish; they verify that the
JSON build info is actually sufficient to build working extension modules
with a build system other than setuptools.
"""

from __future__ import annotations

import importlib.util
import json
import os
import os.path
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from typing import Any

from mypyc.common import EXT_SUFFIX

base_path = os.path.join(os.path.dirname(__file__), "..", "..")

# Injected via sitecustomize to make importing setuptools/distutils fail,
# proving that cgen doesn't need them.
_BLOCK_SITEPACKAGES = """\
import sys

_BLOCKED = {"setuptools", "distutils"}


class _Blocker:
    def find_spec(self, fullname, path=None, target=None):  # type: ignore[no-untyped-def]
        if fullname.split(".")[0] in _BLOCKED:
            raise ImportError(f"{fullname} is blocked for this test")
        return None


sys.meta_path.insert(0, _Blocker())
"""


def run_cgen(cwd: str, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = base_path + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "mypyc", "cgen", *args], capture_output=True, cwd=cwd, env=env
    )
    assert proc.returncode == 0, proc.stderr.decode()
    info: dict[str, Any] = json.loads(proc.stdout)
    return info


def compile_extension(target_dir: str, ext: dict[str, Any], out_path: str) -> None:
    # Build in a single compiler invocation, like distutils does for simple
    # unix-style extensions. The caller is responsible for the Python.h
    # include directory. Windows needs a different link setup.
    ldshared = sysconfig.get_config_var("LDSHARED")
    assert ldshared
    cmd = ldshared.split() + (sysconfig.get_config_var("CFLAGS") or "").split()
    cmd += ext["cflags"]
    cmd += ["-I" + sysconfig.get_path("include"), "-I" + sysconfig.get_path("platinclude")]
    cmd += ["-I" + d for d in ext["include_dirs"]]
    cmd += [os.path.join(target_dir, source) for source in ext["sources"]]
    cmd += ["-o", out_path]
    subprocess.run(cmd, check=True)


def import_compiled(path: str, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCgen(unittest.TestCase):
    def test_works_without_setuptools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w") as f:
                f.write("def f(x: int) -> int:\n    return x + 1\n")
            with tempfile.TemporaryDirectory() as blocker_dir:
                with open(os.path.join(blocker_dir, "sitecustomize.py"), "w") as f:
                    f.write(_BLOCK_SITEPACKAGES)
                env = os.environ.copy()
                env["PYTHONPATH"] = blocker_dir + os.pathsep + base_path
                proc = subprocess.run(
                    [sys.executable, "-m", "mypyc", "cgen", "--output-file", "info.json", "a.py"],
                    capture_output=True,
                    cwd=tmp,
                    env=env,
                )
            assert proc.returncode == 0, proc.stderr.decode()
            with open(os.path.join(tmp, "info.json")) as f:
                info: dict[str, Any] = json.load(f)
            assert info["schema_version"] == 1
            assert [ext["module"] for ext in info["extensions"]] == ["a"]

    def test_single_module_json_and_build(self) -> None:
        if sys.platform == "win32":
            self.skipTest("requires a unix-style compiler")
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w") as f:
                f.write("def f(x: int) -> int:\n    return x + 1\n")
            info = run_cgen(tmp, "--target-dir", os.path.join("build", "mypyc"), "a.py")

            assert info["schema_version"] == 1
            target = info["target_dir"]
            assert os.path.isabs(target)
            exts = info["extensions"]
            assert isinstance(exts, list) and len(exts) == 1
            ext = exts[0]
            assert ext["module"] == "a"
            assert ext["out_path"] == "a" + EXT_SUFFIX
            assert ext["cflags"]
            # Optimization/debug levels are the caller's business.
            assert not any(c.startswith(("-O", "-g")) for c in ext["cflags"])
            assert all(os.path.isfile(os.path.join(target, s)) for s in ext["sources"])
            assert all(os.path.isfile(os.path.join(target, d)) for d in ext["depends"])
            assert all(os.path.isdir(d) for d in ext["include_dirs"])

            out_path = os.path.join(target, ext["out_path"])
            compile_extension(target, ext, out_path)
            mod = import_compiled(out_path, "a")
            assert mod.f(1) == 2

    def test_package_shared_lib_and_shims_build(self) -> None:
        if sys.platform == "win32":
            self.skipTest("requires a unix-style compiler")
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "pkg")
            os.makedirs(pkg)
            with open(os.path.join(pkg, "__init__.py"), "w") as f:
                f.write("from pkg.mod import add\n")
            with open(os.path.join(pkg, "mod.py"), "w") as f:
                f.write("def add(x: int, y: int) -> int:\n    return x + y\n")

            info = run_cgen(tmp, "pkg")
            exts = {ext["module"]: ext for ext in info["extensions"]}
            lib_exts = [m for m in exts if m.endswith("__mypyc")]
            assert len(lib_exts) == 1
            assert {"pkg.__init__", "pkg.mod"} <= set(exts)

            target = info["target_dir"]
            # Built files go relative to the installation root, which here is
            # the source tree itself.
            for ext in exts.values():
                compile_extension(target, ext, os.path.join(tmp, ext["out_path"]))

            script = "import pkg\nassert pkg.add(1, 2) == 3\nprint('ok')\n"
            proc = subprocess.run([sys.executable, "-c", script], cwd=tmp, capture_output=True)
            assert proc.returncode == 0, proc.stderr.decode()
            assert proc.stdout.strip() == b"ok"


if __name__ == "__main__":
    unittest.main()
