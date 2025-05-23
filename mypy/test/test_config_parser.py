from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path

from mypy.config_parser import _find_config_file, parse_config_file
from mypy.defaults import CONFIG_NAMES, SHARED_CONFIG_NAMES
from mypy.options import Options


@contextlib.contextmanager
def chdir(target: Path) -> Iterator[None]:
    # Replace with contextlib.chdir in Python 3.11
    dir = os.getcwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(dir)


def write_config(path: Path, content: str | None = None) -> None:
    if path.suffix == ".toml":
        if content is None:
            content = "[tool.mypy]\nstrict = true"
        path.write_text(content)
    else:
        if content is None:
            content = "[mypy]\nstrict = True"
        path.write_text(content)


class FindConfigFileSuite(unittest.TestCase):

    def test_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as _tmpdir:
            tmpdir = Path(_tmpdir)
            (tmpdir / ".git").touch()
            with chdir(tmpdir):
                result = _find_config_file()
                assert result is None

    def test_parent_config_with_and_without_git(self) -> None:
        for name in CONFIG_NAMES + SHARED_CONFIG_NAMES:
            with tempfile.TemporaryDirectory() as _tmpdir:
                tmpdir = Path(_tmpdir)

                config = tmpdir / name
                write_config(config)

                child = tmpdir / "child"
                child.mkdir()

                with chdir(child):
                    result = _find_config_file()
                    assert result is not None
                    assert Path(result[2]).resolve() == config.resolve()

                    git = child / ".git"
                    git.touch()

                    result = _find_config_file()
                    assert result is None

                    git.unlink()
                    result = _find_config_file()
                    assert result is not None
                    hg = child / ".hg"
                    hg.touch()

                    result = _find_config_file()
                    assert result is None

    def test_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as _tmpdir:
            tmpdir = Path(_tmpdir)

            pyproject = tmpdir / "pyproject.toml"
            setup_cfg = tmpdir / "setup.cfg"
            mypy_ini = tmpdir / "mypy.ini"
            dot_mypy = tmpdir / ".mypy.ini"

            child = tmpdir / "child"
            child.mkdir()

            for cwd in [tmpdir, child]:
                write_config(pyproject)
                write_config(setup_cfg)
                write_config(mypy_ini)
                write_config(dot_mypy)

                with chdir(cwd):
                    result = _find_config_file()
                    assert result is not None
                    assert os.path.basename(result[2]) == "mypy.ini"

                    mypy_ini.unlink()
                    result = _find_config_file()
                    assert result is not None
                    assert os.path.basename(result[2]) == ".mypy.ini"

                    dot_mypy.unlink()
                    result = _find_config_file()
                    assert result is not None
                    assert os.path.basename(result[2]) == "pyproject.toml"

                    pyproject.unlink()
                    result = _find_config_file()
                    assert result is not None
                    assert os.path.basename(result[2]) == "setup.cfg"

    def test_precedence_missing_section(self) -> None:
        with tempfile.TemporaryDirectory() as _tmpdir:
            tmpdir = Path(_tmpdir)

            child = tmpdir / "child"
            child.mkdir()

            parent_mypy = tmpdir / "mypy.ini"
            child_pyproject = child / "pyproject.toml"
            write_config(parent_mypy)
            write_config(child_pyproject, content="")

            with chdir(child):
                result = _find_config_file()
                assert result is not None
                assert Path(result[2]).resolve() == parent_mypy.resolve()


class ExtendConfigFileSuite(unittest.TestCase):

    def test_extend_success(self) -> None:
        with tempfile.TemporaryDirectory() as _tmpdir:
            tmpdir = Path(_tmpdir)
            with chdir(tmpdir):
                pyproject = tmpdir / "pyproject.toml"
                write_config(
                    pyproject,
                    "[tool.mypy]\n"
                    'extend = "./folder/mypy.ini"\n'
                    "strict = false\n"
                    "[[tool.mypy.overrides]]\n"
                    'module = "c"\n'
                    'enable_error_code = ["explicit-override"]\n'
                    "disallow_untyped_defs = true",
                )
                folder = tmpdir / "folder"
                folder.mkdir()
                write_config(
                    folder / "mypy.ini",
                    "[mypy]\n"
                    "strict = True\n"
                    "ignore_missing_imports_per_module = True\n"
                    "[mypy-c]\n"
                    "disallow_incomplete_defs = True",
                )

                options = Options()
                strict_option_set = False

                def set_strict_flags() -> None:
                    nonlocal strict_option_set
                    strict_option_set = True

                stdout = io.StringIO()
                stderr = io.StringIO()
                parse_config_file(options, set_strict_flags, None, stdout, stderr)

                assert strict_option_set is True
                assert options.ignore_missing_imports_per_module is True
                assert options.config_file == str(pyproject.name)
                os.environ["MYPY_CONFIG_FILE_DIR"] = str(pyproject.parent)

                assert options.per_module_options["c"] == {
                    "disable_error_code": [],
                    "enable_error_code": ["explicit-override"],
                    "disallow_untyped_defs": True,
                    "disallow_incomplete_defs": True,
                }

                assert stdout.getvalue() == ""
                assert stderr.getvalue() == ""

    def test_extend_cyclic(self) -> None:
        with tempfile.TemporaryDirectory() as _tmpdir:
            tmpdir = Path(_tmpdir)
            with chdir(tmpdir):
                pyproject = tmpdir / "pyproject.toml"
                write_config(pyproject, '[tool.mypy]\nextend = "./folder/mypy.ini"\n')

                folder = tmpdir / "folder"
                folder.mkdir()
                ini = folder / "mypy.ini"
                write_config(ini, "[mypy]\nextend = ../pyproject.toml\n")

                options = Options()

                stdout = io.StringIO()
                stderr = io.StringIO()
                parse_config_file(options, lambda: None, None, stdout, stderr)

                assert stdout.getvalue() == ""
                assert stderr.getvalue() == (
                    f"Circular extend detected: /private{pyproject}\n"
                    f"../pyproject.toml is not a valid path to extend from /private{ini}\n"
                )
