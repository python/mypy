from __future__ import annotations

import json
import os
from typing import Any

from mypy.plugin import Plugin, ReportConfigContext


class ConfigDataPlugin(Plugin):
    def report_config_data(self, ctx: ReportConfigContext) -> Any:
        path = os.path.join("tmp/test.json")
        with open(path) as f:
            data = json.load(f)
        return data.get(ctx.id)


def plugin(version: str) -> type[ConfigDataPlugin]:
    return ConfigDataPlugin
