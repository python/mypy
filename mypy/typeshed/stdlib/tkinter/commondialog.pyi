import sys
from collections.abc import Mapping
from typing import Any, ClassVar

if sys.version_info >= (3, 9):
    __all__ = ["Dialog"]

class Dialog:
    command: ClassVar[str | None]
    master: Any | None
    options: Mapping[str, Any]
    def __init__(self, master: Any | None = ..., **options) -> None: ...
    def show(self, **options) -> Any: ...
