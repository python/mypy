from __future__ import annotations


class MyPlugin:
    pass


def plugin(version: str) -> type[MyPlugin]:
    return MyPlugin
