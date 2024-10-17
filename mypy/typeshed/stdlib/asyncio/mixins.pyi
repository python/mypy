import sys
import threading
from typing import NoReturn

_global_lock: threading.Lock

class _LoopBoundMixin:
    if sys.version_info < (3, 11):
        def __init__(self, *, loop: NoReturn = ...) -> None: ...
