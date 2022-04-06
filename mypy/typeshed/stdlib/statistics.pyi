import sys
from _typeshed import Self, SupportsRichComparisonT
from decimal import Decimal
from fractions import Fraction
from typing import Any, Hashable, Iterable, NamedTuple, Sequence, SupportsFloat, TypeVar
from typing_extensions import Literal

if sys.version_info >= (3, 10):
    __all__ = [
        "NormalDist",
        "StatisticsError",
        "correlation",
        "covariance",
        "fmean",
        "geometric_mean",
        "harmonic_mean",
        "linear_regression",
        "mean",
        "median",
        "median_grouped",
        "median_high",
        "median_low",
        "mode",
        "multimode",
        "pstdev",
        "pvariance",
        "quantiles",
        "stdev",
        "variance",
    ]
elif sys.version_info >= (3, 8):
    __all__ = [
        "NormalDist",
        "StatisticsError",
        "fmean",
        "geometric_mean",
        "harmonic_mean",
        "mean",
        "median",
        "median_grouped",
        "median_high",
        "median_low",
        "mode",
        "multimode",
        "pstdev",
        "pvariance",
        "quantiles",
        "stdev",
        "variance",
    ]
else:
    __all__ = [
        "StatisticsError",
        "pstdev",
        "pvariance",
        "stdev",
        "variance",
        "median",
        "median_low",
        "median_high",
        "median_grouped",
        "mean",
        "mode",
        "harmonic_mean",
    ]

# Most functions in this module accept homogeneous collections of one of these types
_Number = float | Decimal | Fraction
_NumberT = TypeVar("_NumberT", float, Decimal, Fraction)

# Used in mode, multimode
_HashableT = TypeVar("_HashableT", bound=Hashable)

class StatisticsError(ValueError): ...

if sys.version_info >= (3, 11):
    def fmean(data: Iterable[SupportsFloat], weights: Iterable[SupportsFloat] | None = ...) -> float: ...

elif sys.version_info >= (3, 8):
    def fmean(data: Iterable[SupportsFloat]) -> float: ...

if sys.version_info >= (3, 8):
    def geometric_mean(data: Iterable[SupportsFloat]) -> float: ...

def mean(data: Iterable[_NumberT]) -> _NumberT: ...

if sys.version_info >= (3, 10):
    def harmonic_mean(data: Iterable[_NumberT], weights: Iterable[_Number] | None = ...) -> _NumberT: ...

else:
    def harmonic_mean(data: Iterable[_NumberT]) -> _NumberT: ...

def median(data: Iterable[_NumberT]) -> _NumberT: ...
def median_low(data: Iterable[SupportsRichComparisonT]) -> SupportsRichComparisonT: ...
def median_high(data: Iterable[SupportsRichComparisonT]) -> SupportsRichComparisonT: ...
def median_grouped(data: Iterable[_NumberT], interval: _NumberT = ...) -> _NumberT: ...
def mode(data: Iterable[_HashableT]) -> _HashableT: ...

if sys.version_info >= (3, 8):
    def multimode(data: Iterable[_HashableT]) -> list[_HashableT]: ...

def pstdev(data: Iterable[_NumberT], mu: _NumberT | None = ...) -> _NumberT: ...
def pvariance(data: Iterable[_NumberT], mu: _NumberT | None = ...) -> _NumberT: ...

if sys.version_info >= (3, 8):
    def quantiles(
        data: Iterable[_NumberT], *, n: int = ..., method: Literal["inclusive", "exclusive"] = ...
    ) -> list[_NumberT]: ...

def stdev(data: Iterable[_NumberT], xbar: _NumberT | None = ...) -> _NumberT: ...
def variance(data: Iterable[_NumberT], xbar: _NumberT | None = ...) -> _NumberT: ...

if sys.version_info >= (3, 8):
    class NormalDist:
        def __init__(self, mu: float = ..., sigma: float = ...) -> None: ...
        @property
        def mean(self) -> float: ...
        @property
        def median(self) -> float: ...
        @property
        def mode(self) -> float: ...
        @property
        def stdev(self) -> float: ...
        @property
        def variance(self) -> float: ...
        @classmethod
        def from_samples(cls: type[Self], data: Iterable[SupportsFloat]) -> Self: ...
        def samples(self, n: int, *, seed: Any | None = ...) -> list[float]: ...
        def pdf(self, x: float) -> float: ...
        def cdf(self, x: float) -> float: ...
        def inv_cdf(self, p: float) -> float: ...
        def overlap(self, other: NormalDist) -> float: ...
        def quantiles(self, n: int = ...) -> list[float]: ...
        if sys.version_info >= (3, 9):
            def zscore(self, x: float) -> float: ...

        def __eq__(self, x2: object) -> bool: ...
        def __add__(self, x2: float | NormalDist) -> NormalDist: ...
        def __sub__(self, x2: float | NormalDist) -> NormalDist: ...
        def __mul__(self, x2: float) -> NormalDist: ...
        def __truediv__(self, x2: float) -> NormalDist: ...
        def __pos__(self) -> NormalDist: ...
        def __neg__(self) -> NormalDist: ...
        __radd__ = __add__
        def __rsub__(self, x2: float | NormalDist) -> NormalDist: ...
        __rmul__ = __mul__
        def __hash__(self) -> int: ...

if sys.version_info >= (3, 10):
    def correlation(__x: Sequence[_Number], __y: Sequence[_Number]) -> float: ...
    def covariance(__x: Sequence[_Number], __y: Sequence[_Number]) -> float: ...

    class LinearRegression(NamedTuple):
        slope: float
        intercept: float

if sys.version_info >= (3, 11):
    def linear_regression(
        __regressor: Sequence[_Number], __dependent_variable: Sequence[_Number], *, proportional: bool = ...
    ) -> LinearRegression: ...

elif sys.version_info >= (3, 10):
    def linear_regression(__regressor: Sequence[_Number], __dependent_variable: Sequence[_Number]) -> LinearRegression: ...
