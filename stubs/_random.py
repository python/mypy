# Stubs for _random

# NOTE: These are incomplete!

from typing import Any

class Random:
    def seed(self, x: Any = None) -> None: pass
    def getstate(self) -> tuple: pass
    def setstate(self, state: tuple) -> None: pass
    def random(self) -> float: pass
    def getrandbits(self, k: int) -> int: pass
