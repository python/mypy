# Stubs for pprint

# Based on http://docs.python.org/3.2/library/pprint.html

from typing import Any, Dict, Tuple, TextIO

def pformat(o: object, indent: int = 1, width: int = 80,
            depth: int = None) -> str: pass
def pprint(o: object, stream: TextIO = None, indent: int = 1, width: int = 80,
           depth: int = None) -> None: pass
def isreadable(o: object) -> bool: pass
def isrecursive(o: object) -> bool: pass
def saferepr(o: object) -> str: pass

class PrettyPrinter:
    def __init__(self, indent: int = 1, width: int = 80, depth: int = None,
                 stream: TextIO = None) -> None: pass
    def pformat(self, o: object) -> str: pass
    def pprint(self, o: object) -> None: pass
    def isreadable(self, o: object) -> bool: pass
    def isrecursive(self, o: object) -> bool: pass
    def format(self, o: object, context: Dict[int, Any], maxlevels: int,
               level: int) -> Tuple[str, bool, bool]: pass
