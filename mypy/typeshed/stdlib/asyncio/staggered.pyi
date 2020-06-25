
import sys
from typing import Iterable, Callable, Awaitable, Optional, Tuple, Any, List
from . import events

if sys.version_info >= (3, 8):
    async def staggered_race(coro_fns: Iterable[Callable[[], Awaitable]], delay: Optional[float], *, loop: Optional[events.AbstractEventLoop] = ...) -> Tuple[Any, Optional[int], List[Optional[Exception]]]: ...
