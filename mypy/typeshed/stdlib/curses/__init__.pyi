import sys
from typing import Any, Callable, TypeVar

if sys.platform != "win32":
    from _curses import *
    from _curses import _CursesWindow as _CursesWindow

    _T = TypeVar("_T")

    # available after calling `curses.initscr()`
    LINES: int
    COLS: int

    # available after calling `curses.start_color()`
    COLORS: int
    COLOR_PAIRS: int
    # TODO: wait for `Concatenate` support
    # def wrapper(__func: Callable[Concatenate[_CursesWindow, _P], _T], *arg: _P.args, **kwds: _P.kwargs) -> _T: ...
    def wrapper(__func: Callable[..., _T], *arg: Any, **kwds: Any) -> _T: ...
