"""Ensure the argparse parser and Options class are in sync.

In particular, verify that the argparse defaults are the same as the Options
defaults, and that argparse doesn't assign any new members to the Options
object it creates.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest import mock

from mypy.config_parser import parse_num_workers
from mypy.main import infer_python_executable, main, process_options
from mypy.options import Options
from mypy.test.helpers import Suite


class ArgSuite(Suite):
    def test_parse_num_workers(self) -> None:
        with mock.patch("mypy.config_parser.get_available_threads", return_value=4):
            assert parse_num_workers("auto") == 4
        with mock.patch("mypy.config_parser.get_available_threads", return_value=32):
            assert parse_num_workers("auto") == 8

        assert parse_num_workers(12) == 12
        assert parse_num_workers("12") == 12

        assert parse_num_workers("0") == 0
        assert parse_num_workers("1") == 1

        assert parse_num_workers("-1") == -1
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_num_workers("automatic")

    def test_num_workers_auto_from_command_line_and_environment(self) -> None:
        with mock.patch("mypy.config_parser.get_available_threads", return_value=6):
            with mock.patch.dict(os.environ, {"MYPY_NUM_WORKERS": ""}):
                _, cli_options = process_options(
                    ["--config-file=", "--num-workers=auto"], require_targets=False
                )
            with mock.patch.dict(os.environ, {"MYPY_NUM_WORKERS": "auto"}):
                _, env_options = process_options(["--config-file="], require_targets=False)

        assert cli_options.num_workers == 6
        assert env_options.num_workers == 6

    def test_invalid_num_workers_environment(self) -> None:
        stderr = StringIO()
        with mock.patch.dict(os.environ, {"MYPY_NUM_WORKERS": "automatic"}):
            with self.assertRaises(SystemExit) as context:
                process_options(
                    ["--config-file="], require_targets=False, stdout=StringIO(), stderr=stderr
                )

        assert context.exception.code == 2
        assert "MYPY_NUM_WORKERS: Invalid number of workers 'automatic'" in stderr.getvalue()

    def test_num_workers_auto_from_config(self) -> None:
        configs = (
            ("mypy.ini", "[mypy]\nnum_workers = auto\n"),
            ("pyproject.toml", '[tool.mypy]\nnum_workers = "auto"\n'),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch("mypy.config_parser.get_available_threads", return_value=6):
                for filename, contents in configs:
                    config = Path(temp_dir) / filename
                    config.write_text(contents, encoding="utf-8")
                    with mock.patch.dict(os.environ, {"MYPY_NUM_WORKERS": ""}):
                        _, options = process_options(
                            ["--config-file", str(config)], require_targets=False
                        )
                    assert options.num_workers == 6, filename

    def test_num_workers_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "mypy.ini"
            config.write_text("[mypy]\nnum_workers = 2\n", encoding="utf-8")

            with mock.patch("mypy.config_parser.get_available_threads", return_value=4):
                with mock.patch.dict(os.environ, {"MYPY_NUM_WORKERS": ""}):
                    _, config_options = process_options(
                        ["--config-file", str(config)], require_targets=False
                    )

                with mock.patch.dict(os.environ, {"MYPY_NUM_WORKERS": "7"}):
                    _, env_options = process_options(
                        ["--config-file", str(config)], require_targets=False
                    )

                    _, cli_options = process_options(
                        ["--config-file", str(config), "--num-workers=auto"], require_targets=False
                    )

        assert config_options.num_workers == 2
        assert env_options.num_workers == 7
        assert cli_options.num_workers == 4

    def test_parallel_mode_forces_incremental(self) -> None:
        def incremental_with_workers(num_workers: int) -> bool:
            with mock.patch("mypy.main.run_build", return_value=(None, [], False)) as run_build:
                main(
                    args=[
                        "--config-file=",
                        f"--num-workers={num_workers}",
                        "--no-incremental",
                        "--no-site-packages",
                        "--no-error-summary",
                        "-c",
                        "pass",
                    ],
                    stdout=StringIO(),
                    stderr=StringIO(),
                    clean_exit=True,
                )

                options = cast(Options, run_build.call_args.args[1])
            return options.incremental

        assert incremental_with_workers(1)
        assert not incremental_with_workers(0)

    def test_coherence(self) -> None:
        options = Options()
        _, parsed_options = process_options([], require_targets=False)
        # FIX: test this too. Requires changing working dir to avoid finding 'setup.cfg'
        options.config_file = parsed_options.config_file
        assert options.snapshot() == parsed_options.snapshot()

    def test_executable_inference(self) -> None:
        """Test the --python-executable flag with --python-version"""
        sys_ver_str = "{ver.major}.{ver.minor}".format(ver=sys.version_info)

        base = ["file.py"]  # dummy file

        # test inference given one (infer the other)
        matching_version = base + [f"--python-version={sys_ver_str}"]
        _, options = process_options(matching_version)
        assert options.python_version == sys.version_info[:2]
        assert options.python_executable == sys.executable

        matching_version = base + [f"--python-executable={sys.executable}"]
        _, options = process_options(matching_version)
        assert options.python_version == sys.version_info[:2]
        assert options.python_executable == sys.executable

        # test inference given both
        matching_version = base + [
            f"--python-version={sys_ver_str}",
            f"--python-executable={sys.executable}",
        ]
        _, options = process_options(matching_version)
        assert options.python_version == sys.version_info[:2]
        assert options.python_executable == sys.executable

        # test that --no-site-packages will disable executable inference
        matching_version = base + [f"--python-version={sys_ver_str}", "--no-site-packages"]
        _, options = process_options(matching_version)
        assert options.python_version == sys.version_info[:2]
        assert options.python_executable is None

        # Test setting python_version/executable from config file
        special_opts = argparse.Namespace()
        special_opts.python_executable = None
        special_opts.python_version = None
        special_opts.no_executable = None

        # first test inferring executable from version
        options = Options()
        options.python_executable = cast(Any, None)
        options.python_version = sys.version_info[:2]
        infer_python_executable(options, special_opts)
        assert options.python_version == sys.version_info[:2]
        assert options.python_executable == sys.executable

        # then test inferring version from executable
        options = Options()
        options.python_executable = sys.executable
        infer_python_executable(options, special_opts)
        assert options.python_version == sys.version_info[:2]
        assert options.python_executable == sys.executable
