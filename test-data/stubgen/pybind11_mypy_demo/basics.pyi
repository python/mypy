from typing import ClassVar

from typing import overload
PI: float

class Point:
    class AngleUnit:
        __doc__: ClassVar[str] = ...  # read-only
        __members__: ClassVar[dict] = ...  # read-only
        __entries: ClassVar[dict] = ...
        degree: ClassVar[Point.AngleUnit] = ...
        radian: ClassVar[Point.AngleUnit] = ...
        def __init__(self, value: int) -> None: ...
        def __eq__(self, other: object) -> bool: ...
        def __getstate__(self) -> int: ...
        def __hash__(self) -> int: ...
        def __index__(self) -> int: ...
        def __int__(self) -> int: ...
        def __ne__(self, other: object) -> bool: ...
        def __setstate__(self, state: int) -> None: ...
        @property
        def name(self) -> str: ...

    class LengthUnit:
        __doc__: ClassVar[str] = ...  # read-only
        __members__: ClassVar[dict] = ...  # read-only
        __entries: ClassVar[dict] = ...
        inch: ClassVar[Point.LengthUnit] = ...
        mm: ClassVar[Point.LengthUnit] = ...
        pixel: ClassVar[Point.LengthUnit] = ...
        def __init__(self, value: int) -> None: ...
        def __eq__(self, other: object) -> bool: ...
        def __getstate__(self) -> int: ...
        def __hash__(self) -> int: ...
        def __index__(self) -> int: ...
        def __int__(self) -> int: ...
        def __ne__(self, other: object) -> bool: ...
        def __setstate__(self, state: int) -> None: ...
        @property
        def name(self) -> str: ...
    angle_unit: ClassVar[Point.AngleUnit] = ...
    length_unit: ClassVar[Point.LengthUnit] = ...
    x_axis: ClassVar[Point] = ...  # read-only
    y_axis: ClassVar[Point] = ...  # read-only
    origin: ClassVar[Point] = ...
    x: float
    y: float
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, x: float, y: float) -> None: ...
    @overload
    def distance_to(self, x: float, y: float) -> float: ...
    @overload
    def distance_to(self, other: Point) -> float: ...
    @property
    def length(self) -> float: ...

def answer() -> int: ...
def midpoint(left: float, right: float) -> float: ...
def sum(arg0: int, arg1: int) -> int: ...
def weighted_midpoint(left: float, right: float, alpha: float = ...) -> float: ...
