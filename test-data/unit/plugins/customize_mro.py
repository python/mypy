from __future__ import annotations

from typing import Callable

from mypy.plugin import ClassDefContext, Plugin


class DummyPlugin(Plugin):
    def get_customize_class_mro_hook(self, fullname: str) -> Callable[[ClassDefContext], None]:
        def analyze(classdef_ctx: ClassDefContext) -> None:
            pass

        return analyze


def plugin(version: str) -> type[DummyPlugin]:
    return DummyPlugin
