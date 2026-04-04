import pathlib
import typing
from . import demo as demo
from typing import overload

class StaticMethods:
    def __init__(self, *args, **kwargs) -> None:
        """Initialize self.  See help(type(self)) for accurate signature."""
    @overload
    @staticmethod
    def overloaded_static_method(value: typing.SupportsInt) -> int:
        """overloaded_static_method(*args, **kwargs)
        Overloaded function.

        1. overloaded_static_method(value: typing.SupportsInt) -> int

        2. overloaded_static_method(value: typing.SupportsFloat) -> float
        """
    @overload
    @staticmethod
    def overloaded_static_method(value: typing.SupportsFloat) -> float:
        """overloaded_static_method(*args, **kwargs)
        Overloaded function.

        1. overloaded_static_method(value: typing.SupportsInt) -> int

        2. overloaded_static_method(value: typing.SupportsFloat) -> float
        """
    @staticmethod
    def some_static_method(a: typing.SupportsInt, b: typing.SupportsInt) -> int:
        """some_static_method(a: typing.SupportsInt, b: typing.SupportsInt) -> int

        None
        """

class TestStruct:
    field_readwrite: int
    field_readwrite_docstring: int
    def __init__(self, *args, **kwargs) -> None:
        """Initialize self.  See help(type(self)) for accurate signature."""
    @property
    def field_readonly(self) -> int:
        """some docstring
        (arg0: pybind11_fixtures.TestStruct) -> int
        """

def func_incomplete_signature(*args, **kwargs):
    """func_incomplete_signature() -> dummy_sub_namespace::HasNoBinding"""
def func_returning_optional() -> int | None:
    """func_returning_optional() -> int | None"""
def func_returning_pair() -> tuple[int, float]:
    """func_returning_pair() -> tuple[int, float]"""
def func_returning_path() -> pathlib.Path:
    """func_returning_path() -> pathlib.Path"""
def func_returning_vector() -> list[float]:
    """func_returning_vector() -> list[float]"""
