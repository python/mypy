from typing import typevar, Any

FT = typevar('FT')

def register(func: FT, *args: Any, **kargs: Any) -> FT: pass
