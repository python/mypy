# Stubs for math
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/math.html

from typing import overload, Tuple, Iterable

# ----- variables and constants -----
e = 0.0
pi = 0.0

# ----- functions -----
def ceil(x: float) -> int: pass
def copysign(x: float, y: float) -> float: pass
def fabs(x: float) -> float: pass
def factorial(x: int) -> int: pass
def floor(x: float) -> int: pass
def fmod(x: float, y: float) -> float: pass
def frexp(x: float) -> Tuple[float, int]: pass
def fsum(iterable: Iterable) -> float: pass
def isfinite(x: float) -> bool: pass
def isinf(x: float) -> bool: pass
def isnan(x: float) -> bool: pass
def ldexp(x: float, i: int) -> float: pass
def modf(x: float) -> Tuple[float, float]: pass
def trunc(x: float) -> float: pass
def exp(x: float) -> float: pass
def expm1(x: float) -> float: pass
def log(x: float, base: float = e) -> float: pass
def log1p(x: float) -> float: pass
def log10(x: float) -> float: pass
def pow(x: float, y: float) -> float: pass
def sqrt(x: float) -> float: pass
def acos(x: float) -> float: pass
def asin(x: float) -> float: pass
def atan(x: float) -> float: pass
def atan2(y: float, x: float) -> float: pass
def cos(x: float) -> float: pass
def hypot(x: float, y: float) -> float: pass
def sin(x: float) -> float: pass
def tan(x: float) -> float: pass
def degrees(x: float) -> float: pass
def radians(x: float) -> float: pass
def acosh(x: float) -> float: pass
def asinh(x: float) -> float: pass
def atanh(x: float) -> float: pass
def cosh(x: float) -> float: pass
def sinh(x: float) -> float: pass
def tanh(x: float) -> float: pass
def erf(x: object) -> float: pass
def erfc(x: object) -> float: pass
def gamma(x: object) -> float: pass
def lgamma(x: object) -> float: pass
