from typing import Any, TypeVar, Union

class Enum:
    def __new__(cls, value: Any) -> None: pass
    def __repr__(self) -> str: pass
    def __str__(self) -> str: pass
    def __format__(self, format_spec: str) -> str: pass
    def __hash__(self) -> Any: pass
    def __reduce_ex__(self, proto: Any) -> Any: pass

    name = ''  # type: str
    value = None  # type: Any

class IntEnum(int, Enum):
    value = 0  # type: int

_T = TypeVar('_T')

def unique(enumeration: _T) -> _T: pass

# In reality Flag and IntFlag are 3.6 only

class Flag(Enum):
    def __or__(self: _T, other: Union[int, _T]) -> _T: pass


class IntFlag(int, Flag):
    def __and__(self: _T, other: Union[int, _T]) -> _T: pass
