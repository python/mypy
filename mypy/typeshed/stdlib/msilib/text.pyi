import sys
from typing import Tuple

if sys.platform == "win32":

    ActionText: list[Tuple[str, str, str | None]]
    UIText: list[Tuple[str, str | None]]

    tables: list[str]
