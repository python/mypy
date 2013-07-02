# Stubs for locale

# NOTE: These are incomplete!

from typing import overload, Iterable

@overload
def setlocale(category: int, locale: str = None) -> str: pass
@overload
def setlocale(category: int, locale: Iterable[str]) -> str: pass
