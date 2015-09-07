from typing import Dict, Generic, Mapping, TypeVar

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

class UserDict(Dict[_KT, _VT], Generic[_KT, _VT]):
    data = ... # type: Mapping[_KT, _VT]

    def __init__(self, initialdata: Mapping[_KT, _VT] = None) -> None: ...

    # TODO: DictMixin
