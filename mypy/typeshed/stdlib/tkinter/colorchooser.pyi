import sys
from tkinter.commondialog import Dialog
from typing import Any, ClassVar

if sys.version_info >= (3, 9):
    __all__ = ["Chooser", "askcolor"]

class Chooser(Dialog):
    command: ClassVar[str]

def askcolor(color: str | bytes | None = ..., **options: Any) -> tuple[None, None] | tuple[tuple[float, float, float], str]: ...
