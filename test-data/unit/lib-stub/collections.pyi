from typing import Any, Iterable, Union, Optional, Dict, TypeVar

def namedtuple(
    typename: str,
    field_names: Union[str, Iterable[str]],
    *,
    # really bool but many tests don't have bool available
    rename: int = ...,
    module: Optional[str] = ...,
    defaults: Optional[Iterable[Any]] = ...
) -> Any: ...

K = TypeVar('K')
V = TypeVar('V')

class OrderedDict(Dict[K, V]):
    def __setitem__(self, k: K, v: V) -> None: ...
