from typing import Dict, Generic, Mapping

class UserDict(Dict[_KT, _VT], Generic[_KT, _VT]):
    data = ... # type: Mapping[_KT, _VT]

    def __init__(self, initialdata: Mapping[_KT, _VT] = None) -> None: ...

    # TODO: DictMixin
