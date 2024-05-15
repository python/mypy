from __future__ import annotations

from typing import Any


# The following should pass without error (see #6661):
class Diagnostic:
    def __reduce__(self) -> str | tuple[Any, ...]:
        res = super().__reduce__()
        if isinstance(res, tuple) and len(res) >= 3:
            res[2]["_info"] = 42

        return res
