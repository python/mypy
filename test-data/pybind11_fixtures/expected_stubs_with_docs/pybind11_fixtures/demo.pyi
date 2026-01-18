import typing
from typing import ClassVar, overload

PI: float
__version__: str

class Point:
    class AngleUnit:
        """Members:

          radian

          degree"""
        __members__: ClassVar[dict] = ...  # read-only
        __entries: ClassVar[dict] = ...
        degree: ClassVar[Point.AngleUnit] = ...
        radian: ClassVar[Point.AngleUnit] = ...
        def __init__(self, value: typing.SupportsInt) -> None:
            """__init__(self: pybind11_fixtures.demo.Point.AngleUnit, value: typing.SupportsInt) -> None"""
        def __eq__(self, other: object) -> bool:
            """__eq__(self: object, other: object, /) -> bool"""
        def __hash__(self) -> int:
            """__hash__(self: object, /) -> int"""
        def __index__(self) -> int:
            """__index__(self: pybind11_fixtures.demo.Point.AngleUnit, /) -> int"""
        def __int__(self) -> int:
            """__int__(self: pybind11_fixtures.demo.Point.AngleUnit, /) -> int"""
        def __ne__(self, other: object) -> bool:
            """__ne__(self: object, other: object, /) -> bool"""
        @property
        def name(self) -> str:
            """name(self: object, /) -> str

            name(self: object, /) -> str
            """
        @property
        def value(self) -> int:
            """(arg0: pybind11_fixtures.demo.Point.AngleUnit) -> int"""

    class LengthUnit:
        """Members:

          mm

          pixel

          inch"""
        __members__: ClassVar[dict] = ...  # read-only
        __entries: ClassVar[dict] = ...
        inch: ClassVar[Point.LengthUnit] = ...
        mm: ClassVar[Point.LengthUnit] = ...
        pixel: ClassVar[Point.LengthUnit] = ...
        def __init__(self, value: typing.SupportsInt) -> None:
            """__init__(self: pybind11_fixtures.demo.Point.LengthUnit, value: typing.SupportsInt) -> None"""
        def __eq__(self, other: object) -> bool:
            """__eq__(self: object, other: object, /) -> bool"""
        def __hash__(self) -> int:
            """__hash__(self: object, /) -> int"""
        def __index__(self) -> int:
            """__index__(self: pybind11_fixtures.demo.Point.LengthUnit, /) -> int"""
        def __int__(self) -> int:
            """__int__(self: pybind11_fixtures.demo.Point.LengthUnit, /) -> int"""
        def __ne__(self, other: object) -> bool:
            """__ne__(self: object, other: object, /) -> bool"""
        @property
        def name(self) -> str:
            """name(self: object, /) -> str

            name(self: object, /) -> str
            """
        @property
        def value(self) -> int:
            """(arg0: pybind11_fixtures.demo.Point.LengthUnit) -> int"""
    angle_unit: ClassVar[Point.AngleUnit] = ...
    length_unit: ClassVar[Point.LengthUnit] = ...
    x_axis: ClassVar[Point] = ...  # read-only
    y_axis: ClassVar[Point] = ...  # read-only
    origin: ClassVar[Point] = ...
    x: float
    y: float
    @overload
    def __init__(self) -> None:
        """__init__(*args, **kwargs)
        Overloaded function.

        1. __init__(self: pybind11_fixtures.demo.Point) -> None

        2. __init__(self: pybind11_fixtures.demo.Point, x: typing.SupportsFloat, y: typing.SupportsFloat) -> None
        """
    @overload
    def __init__(self, x: typing.SupportsFloat, y: typing.SupportsFloat) -> None:
        """__init__(*args, **kwargs)
        Overloaded function.

        1. __init__(self: pybind11_fixtures.demo.Point) -> None

        2. __init__(self: pybind11_fixtures.demo.Point, x: typing.SupportsFloat, y: typing.SupportsFloat) -> None
        """
    def as_list(self) -> list[float]:
        """as_list(self: pybind11_fixtures.demo.Point) -> list[float]"""
    @overload
    def distance_to(self, x: typing.SupportsFloat, y: typing.SupportsFloat) -> float:
        """distance_to(*args, **kwargs)
        Overloaded function.

        1. distance_to(self: pybind11_fixtures.demo.Point, x: typing.SupportsFloat, y: typing.SupportsFloat) -> float

        2. distance_to(self: pybind11_fixtures.demo.Point, other: pybind11_fixtures.demo.Point) -> float
        """
    @overload
    def distance_to(self, other: Point) -> float:
        """distance_to(*args, **kwargs)
        Overloaded function.

        1. distance_to(self: pybind11_fixtures.demo.Point, x: typing.SupportsFloat, y: typing.SupportsFloat) -> float

        2. distance_to(self: pybind11_fixtures.demo.Point, other: pybind11_fixtures.demo.Point) -> float
        """
    @property
    def length(self) -> float:
        """(arg0: pybind11_fixtures.demo.Point) -> float"""

def answer() -> int:
    '''answer() -> int

    answer docstring, with end quote"
    '''
def midpoint(left: typing.SupportsFloat, right: typing.SupportsFloat) -> float:
    """midpoint(left: typing.SupportsFloat, right: typing.SupportsFloat) -> float"""
def sum(arg0: typing.SupportsInt, arg1: typing.SupportsInt) -> int:
    '''sum(arg0: typing.SupportsInt, arg1: typing.SupportsInt) -> int

    multiline docstring test, edge case quotes """\'\'\'
    '''
def weighted_midpoint(left: typing.SupportsFloat, right: typing.SupportsFloat, alpha: typing.SupportsFloat = ...) -> float:
    """weighted_midpoint(left: typing.SupportsFloat, right: typing.SupportsFloat, alpha: typing.SupportsFloat = 0.5) -> float"""
