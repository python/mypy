import threading
from typing import NoReturn

_global_lock: threading.Lock

class _LoopBoundMixin:
    def __init__(self, *, loop: NoReturn = ...) -> None: ...
