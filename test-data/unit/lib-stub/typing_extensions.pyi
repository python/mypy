from typing import TypeVar

_T = TypeVar('_T')

class Protocol: pass
def runtime(x: _T) -> _T: pass

class Final: pass
def final(x: _T) -> _T: pass
