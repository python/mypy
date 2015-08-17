# Stubs for copy

# NOTE: These are incomplete!

from typing import TypeVar

_T = TypeVar('_T')

def deepcopy(x: _T) -> _T: ...
def copy(x: _T) -> _T: ...
