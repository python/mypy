import selectors
import sys

from . import base_events

if sys.version_info >= (3, 7):
    __all__ = ("BaseSelectorEventLoop",)
else:
    __all__ = ["BaseSelectorEventLoop"]

class BaseSelectorEventLoop(base_events.BaseEventLoop):
    def __init__(self, selector: selectors.BaseSelector | None = ...) -> None: ...
