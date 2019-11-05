import os
import json

from typing import Any

from mypy.plugin import Plugin


class ConfigDataPlugin(Plugin):
    def report_config_data(self, id: str, path: str, is_check: bool) -> Any:
        path = os.path.join('tmp/test.json')
        with open(path) as f:
            data = json.load(f)
        return data.get(id)


def plugin(version):
    return ConfigDataPlugin
