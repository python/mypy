from __future__ import annotations

import contextlib
import os
import tempfile
import unittest
from collections.abc import Iterator
from io import StringIO
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


class ParseConfigFileSuite(unittest.TestCase):
    def test_output_option_with_none_default(self) -> None:
        with tempfile.TemporaryDirectory() as _tmpdir:
            config = Path(_tmpdir) / "mypy.ini"
            write_config(config, content="[mypy]\noutput = json\n")

            options = Options()
            stderr = StringIO()
            parse_config_file(options, lambda: None, str(config), stderr=stderr)

            assert options.output == "json"
            assert stderr.getvalue() == ""
