from typing import Callable, TypeVar
from typing_extensions import ParamSpec

_P = ParamSpec("_P")
_R = TypeVar("_R")

async def to_thread(__func: Callable[_P, _R], *args: _P.args, **kwargs: _P.kwargs) -> _R: ...
