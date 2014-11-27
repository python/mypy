# Stubs for imp

# NOTE: These are incomplete!

from typing import typevar

_T = typevar('_T')

def cache_from_source(path: str, debug_override: bool = None) -> str: pass
def reload(module: _T) -> _T: pass # TODO imprecise signature
