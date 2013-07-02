# Stubs for math
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/math.html

from typing import overload, Tuple, Iterable

# ----- variables and constants -----
e = 0.0
pi = 0.0

# ----- functions -----
@overload
def ceil(x: int) -> int: pass
@overload
def ceil(x: float) -> int: pass
@overload
def copysign(x: int, y: int) -> float: pass
@overload
def copysign(x: float, y: float) -> float: pass
@overload
def fabs(x: int) -> float: pass
@overload
def fabs(x: float) -> float: pass
def factorial(x: int) -> int: pass
@overload
def floor(x: int) -> int: pass
@overload
def floor(x: float) -> int: pass
@overload
def fmod(x: int, y: int) -> float: pass
@overload
def fmod(x: float, y: float) -> float: pass
@overload
def frexp(x: int) -> Tuple[float, int]: pass
@overload
def frexp(x: float) -> Tuple[float, int]: pass
def fsum(iterable: Iterable) -> float: pass
def isfinite(x: float) -> bool: pass
def isinf(x: float) -> bool: pass
def isnan(x: float) -> bool: pass
def ldexp(x: float, i: int) -> float: pass
def modf(x: float) -> Tuple[float, float]: pass
def trunc(x: float) -> float: pass
@overload
def exp(x: int) -> float: pass
@overload
def exp(x: float) -> float: pass
@overload
def expm1(x: int) -> float: pass
@overload
def expm1(x: float) -> float: pass
@overload
def log(x: int, base: float = e) -> float: pass
@overload
def log(x: float, base: float = e) -> float: pass
@overload
def log(x: int, base: int) -> float: pass
@overload
def log(x: float, base: int) -> float: pass
@overload
def log1p(x: int) -> float: pass
@overload
def log1p(x: float) -> float: pass
@overload
def log10(x: int) -> float: pass
@overload
def log10(x: float) -> float: pass
@overload
def pow(x: int, y: int) -> float: pass
@overload
def pow(x: int, y: float) -> float: pass
@overload
def pow(x: float, y: int) -> float: pass
@overload
def pow(x: float, y: float) -> float: pass
@overload
def sqrt(x: int) -> float: pass
@overload
def sqrt(x: float) -> float: pass
@overload
def acos(x: int) -> float: pass
@overload
def acos(x: float) -> float: pass
@overload
def asin(x: int) -> float: pass
@overload
def asin(x: float) -> float: pass
@overload
def atan(x: int) -> float: pass
@overload
def atan(x: float) -> float: pass
@overload
def atan2(y: int, x: int) -> float: pass
@overload
def atan2(y: int, x: float) -> float: pass
@overload
def atan2(y: float, x: int) -> float: pass
@overload
def atan2(y: float, x: float) -> float: pass
@overload
def cos(x: int) -> float: pass
@overload
def cos(x: float) -> float: pass
@overload
def hypot(x: int, y: int) -> float: pass
@overload
def hypot(x: int, y: float) -> float: pass
@overload
def hypot(x: float, y: int) -> float: pass
@overload
def hypot(x: float, y: float) -> float: pass
@overload
def sin(x: int) -> float: pass
@overload
def sin(x: float) -> float: pass
@overload
def tan(x: int) -> float: pass
@overload
def tan(x: float) -> float: pass
@overload
def degrees(x: int) -> float: pass
@overload
def degrees(x: float) -> float: pass
@overload
def radians(x: int) -> float: pass
@overload
def radians(x: float) -> float: pass
@overload
def acosh(x: int) -> float: pass
@overload
def acosh(x: float) -> float: pass
@overload
def asinh(x: int) -> float: pass
@overload
def asinh(x: float) -> float: pass
@overload
def atanh(x: int) -> float: pass
@overload
def atanh(x: float) -> float: pass
@overload
def cosh(x: int) -> float: pass
@overload
def cosh(x: float) -> float: pass
@overload
def sinh(x: int) -> float: pass
@overload
def sinh(x: float) -> float: pass
@overload
def tanh(x: int) -> float: pass
@overload
def tanh(x: float) -> float: pass
def erf(x: object) -> float: pass  # x is an arbitrary expression
def erfc(x: object) -> float: pass  # x is an arbitrary expression
def gamma(x: object) -> float: pass  # x is an arbitrary expression
def lgamma(x: object) -> float: pass  # x is an arbitrary expression
