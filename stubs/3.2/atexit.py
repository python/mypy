from typing import typevar, Any

_FT = typevar('_FT')

def register(func: _FT, *args: Any, **kargs: Any) -> _FT: pass
