from typing import Any, Iterable, Union, Optional

def namedtuple(
    typename: str,
    field_names: Union[str, Iterable[str]],
    *,
    # really bool but many tests don't have bool available
    rename: int = ...,
    module: Optional[str] = ...,
    defaults: Optional[Iterable[Any]] = ...
) -> Any: ...
