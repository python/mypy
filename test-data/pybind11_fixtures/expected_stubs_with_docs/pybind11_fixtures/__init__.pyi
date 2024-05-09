import os
from . import demo as demo
from typing import overload

class StaticMethods:
    def __init__(self, *args, **kwargs) -> None:
        """Initialize self.  See help(type(self)) for accurate signature."""
    @overload
    @staticmethod
    def overloaded_static_method(value: int) -> int:
        """overloaded_static_method(*args, **kwargs)
        Overloaded function.

        1. overloaded_static_method(value: int) -> int

        2. overloaded_static_method(value: float) -> float
        """
    @overload
    @staticmethod
    def overloaded_static_method(value: float) -> float:
        """overloaded_static_method(*args, **kwargs)
        Overloaded function.

        1. overloaded_static_method(value: int) -> int

        2. overloaded_static_method(value: float) -> float
        """
    @staticmethod
    def some_static_method(a: int, b: int) -> int:
        """some_static_method(a: int, b: int) -> int

        None
        """

class TestStruct:
    field_readwrite: int
    field_readwrite_docstring: int
    def __init__(self, *args, **kwargs) -> None:
        """Initialize self.  See help(type(self)) for accurate signature."""
    @property
    def field_readonly(self) -> int: ...

def func_incomplete_signature(*args, **kwargs):
    """func_incomplete_signature() -> dummy_sub_namespace::HasNoBinding"""
def func_returning_optional() -> int | None:
    """func_returning_optional() -> Optional[int]"""
def func_returning_pair() -> tuple[int, float]:
    """func_returning_pair() -> Tuple[int, float]"""
def func_returning_path() -> os.PathLike:
    """func_returning_path() -> os.PathLike"""
def func_returning_vector() -> list[float]:
    """func_returning_vector() -> List[float]"""
