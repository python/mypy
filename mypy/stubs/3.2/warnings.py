# Stubs for warnings

# Based on http://docs.python.org/3.2/library/warnings.html

from typing import overload, Any, List, TextIO

@overload
def warn(message: str, category: type = None,
         stacklevel: int = 1) -> None: pass
@overload
def warn(message: Warning, category: type = None,
         stacklevel: int = 1) -> None: pass

@overload
def warn_explicit(message: str, category: type, filename: str, lineno: int,
                  module: str = None, registry: Any = None,
                  module_globals: Any = None) -> None: pass
@overload
def warn_explicit(message: Warning, category: type, filename: str, lineno: int,
                  module: str = None, registry: Any = None,
                  module_globals: Any = None) -> None: pass

# logging modifies showwarning => make it a variable.
def _showwarning(message: str, category: type, filename: str, lineno: int,
                 file: TextIO = None, line: str = None) -> None: pass
showwarning = _showwarning

def formatwarning(message: str, category: type, filename: str, lineno: int,
                  line: str = None) -> None: pass
def filterwarnings(action: str, message: str = '', category: type = Warning,
                   module: str = '', lineno: int = 0,
                   append: bool = False) -> None: pass
def simplefilter(action: str, category: type = Warning, lineno: int = 0,
                 append: bool = False) -> None: pass
def resetwarnings() -> None: pass

class catch_warnings:
    # TODO record and module must be keyword arguments!
    # TODO type of module?
    def __init__(self, record: bool = False, module: Any = None) -> None: pass
    def __enter__(self) -> List[Any]: pass
    def __exit__(self, type, value, traceback) -> bool: pass
