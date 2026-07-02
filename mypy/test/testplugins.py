from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from mypy import build
from mypy.errors import Errors
from mypy.options import Options
from mypy.test.helpers import Suite


class PluginSuite(Suite):
    def test_module_plugin_can_be_loaded_from_python_executable_search_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            plugin_dir = temp_path / "target-site-packages"
            plugin_dir.mkdir()
            plugin_file = plugin_dir / "target_only_plugin.py"
            plugin_file.write_text(
                """\
from mypy.plugin import Plugin


class TargetPlugin(Plugin):
    pass


def plugin(version: str) -> type[Plugin]:
    return TargetPlugin
""",
                encoding="utf8",
            )
            config_file = temp_path / "mypy.ini"
            config_file.write_text("[mypy]\nplugins = target_only_plugin\n", encoding="utf8")

            options = Options()
            options.config_file = str(config_file)
            options.plugins = ["target_only_plugin"]
            options.python_executable = str(temp_path / "target-python")
            errors = Errors(options)
            original_sys_path = sys.path[:]

            with patch.object(
                build, "get_search_dirs", lambda executable: ([], [str(plugin_dir)])
            ):
                sys.modules.pop("target_only_plugin", None)
                try:
                    plugins, snapshot = build.load_plugins_from_config(
                        options, errors, io.StringIO()
                    )
                finally:
                    sys.modules.pop("target_only_plugin", None)

            assert len(plugins) == 1
            assert "target_only_plugin" in snapshot
            assert sys.path == original_sys_path

    def test_python_executable_symlink_uses_own_search_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_link = temp_path / "python"
            python_link.symlink_to(sys.executable)
            plugin_dir = temp_path / "target-site-packages"

            options = Options()
            options.python_executable = str(python_link)

            with patch.object(
                build, "get_search_dirs", lambda executable: ([], [str(plugin_dir)])
            ):
                with build.plugin_import_path(options):
                    assert sys.path[0] == str(plugin_dir)
