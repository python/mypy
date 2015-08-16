# Stubs for functools

# NOTE: These are incomplete!

from typing import Callable, Any, Optional

# TODO implement as class; more precise typing
# TODO cache_info and __wrapped__ attributes
def lru_cache(maxsize: Optional[int] = 100) -> Callable[[Any], Any]: ...

# TODO more precise typing?
def wraps(func: Any) -> Any: ...
