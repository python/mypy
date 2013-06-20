# Stubs for imp

# NOTE: These are incomplete!

from typing import typevar

T = typevar('T')

def cache_from_source(path: str, debug_override: bool = None) -> str: pass
def reload(module: T) -> T: pass # TODO imprecise signature
