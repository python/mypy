from typing import TypeVar, Any

_T = TypeVar('_T')

class _SpecialForm:
    def __getitem__(self, typeargs: Any) -> Any:
        pass

Protocol: _SpecialForm = ...
def runtime(x: _T) -> _T: pass

Final: _SpecialForm = ...
def final(x: _T) -> _T: pass

Literal: _SpecialForm = ...
