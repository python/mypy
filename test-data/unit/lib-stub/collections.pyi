from typing import Any, Iterable, Union, Optional, TypeVar, Dict, Generic

def namedtuple(
    typename: str,
    field_names: Union[str, Iterable[str]],
    *,
    # really bool but many tests don't have bool available
    rename: int = ...,
    module: Optional[str] = ...,
    defaults: Optional[Iterable[Any]] = ...
) -> Any: ...

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

class defaultdict(Dict[_KT, _VT], Generic[_KT, _VT]):
    pass
