# Stubs for decimal (Python 3.4)

from typing import (
    Any, Undefined, Union, SupportsInt, SupportsFloat, SupportsAbs, SupportsRound, Sequence,
    Tuple, NamedTuple, Dict
)

_Decimal = Union[Decimal, int]

BasicContext = Undefined(Context)
DefaultContext = Undefined(Context)
ExtendedContext = Undefined(Context)
HAVE_THREADS = Undefined(bool)
MAX_EMAX = Undefined(int)
MAX_PREC = Undefined(int)
MIN_EMIN = Undefined(int)
MIN_ETINY = Undefined(int)
ROUND_05UP = Undefined(str)
ROUND_CEILING = Undefined(str)
ROUND_DOWN = Undefined(str)
ROUND_FLOOR = Undefined(str)
ROUND_HALF_DOWN = Undefined(str)
ROUND_HALF_EVEN = Undefined(str)
ROUND_HALF_UP = Undefined(str)
ROUND_UP = Undefined(str)

def getcontext() -> Context: pass
def localcontext(ctx: Context = None) -> _ContextManager: pass
def setcontext(c: Context) -> None: pass

DecimalTuple = NamedTuple('DecimalTuple',
                          [('sign', int),
                           ('digits', Sequence[int]), # TODO: Use Tuple[int, ...]
                           ('exponent', int)])

class _ContextManager:
    def __enter__(self) -> Context: pass
    def __exit__(self, t, v, tb) -> None: pass

class Context:
    Emax = Undefined(int)
    Emin = Undefined(int)
    capitals = Undefined(int)
    clamp = Undefined(int)
    prec = Undefined(int)
    rounding = Undefined(str)
    traps = Undefined(Dict[type, bool])
    def __init__(self, prec: int = None, rounding: str = None, Emin: int = None, Emax: int = None,
                 capitals: int = None, clamp: int = None, flags=None, traps=None,
                 _ignored_flags=None) -> None: pass
    def Etiny(self): pass
    def Etop(self): pass
    def abs(self, x: _Decimal) -> Decimal: pass
    def add(self, x: _Decimal, y: _Decimal) -> Decimal: pass
    def canonical(self, x): pass
    def clear_flags(self): pass
    def clear_traps(self): pass
    def compare(self, x, y): pass
    def compare_signal(self, x, y): pass
    def compare_total(self, x, y): pass
    def compare_total_mag(self, x, y): pass
    def copy(self): pass
    def copy_abs(self, x): pass
    def copy_decimal(self, x): pass
    def copy_negate(self, x): pass
    def copy_sign(self, x, y): pass
    def create_decimal(self, x): pass
    def create_decimal_from_float(self, f): pass
    def divide(self, x, y): pass
    def divide_int(self, x, y): pass
    def divmod(self, x, y): pass
    def exp(self, x): pass
    def fma(self, x, y, z): pass
    def is_canonical(self, x): pass
    def is_finite(self, x): pass
    def is_infinite(self, x): pass
    def is_nan(self, x): pass
    def is_normal(self, x): pass
    def is_qnan(self, x): pass
    def is_signed(self, x): pass
    def is_snan(self): pass
    def is_subnormal(self, x): pass
    def is_zero(self, x): pass
    def ln(self, x): pass
    def log10(self, x): pass
    def logb(self, x): pass
    def logical_and(self, x, y): pass
    def logical_invert(self, x): pass
    def logical_or(self, x, y): pass
    def logical_xor(self, x, y): pass
    def max(self, x, y): pass
    def max_mag(self, x, y): pass
    def min(self, x, y): pass
    def min_mag(self, x, y): pass
    def minus(self, x): pass
    def multiply(self, x, y): pass
    def next_minus(self, x): pass
    def next_plus(self, x): pass
    def next_toward(self, x): pass
    def normalize(self, x): pass
    def number_class(self, x): pass
    def plus(self, x): pass
    def power(self, x, y): pass
    def quantize(self, x, y): pass
    def radix(self): pass
    def remainder(self, x, y): pass
    def remainder_near(self, x, y): pass
    def rotate(self, x, y): pass
    def same_quantum(self, x, y): pass
    def scaleb(self, x, y): pass
    def shift(self, x, y): pass
    def sqrt(self, x): pass
    def subtract(self, x, y): pass
    def to_eng_string(self, x): pass
    def to_integral(self, x): pass
    def to_integral_exact(self, x): pass
    def to_integral_value(self, x): pass
    def to_sci_string(self, x): pass
    def __copy__(self) -> Context: pass
    def __delattr__(self, name): pass
    def __reduce__(self): pass

class ConversionSyntax(InvalidOperation): pass

class Decimal(SupportsInt, SupportsFloat, SupportsAbs[Decimal], SupportsRound[int]):
    # TODO: SupportsCeil, SupportsFloor, SupportsTrunc?

    def __init__(cls, value: Union[_Decimal, float, str,
                                   Tuple[int, Sequence[int], int]] = '',
                 context: Context = None) -> None: pass

    @property
    def imag(self) -> Decimal: pass
    @property
    def real(self) -> Decimal: pass

    def adjusted(self) -> int: pass
    def as_tuple(self) -> DecimalTuple: pass
    def canonical(self) -> Decimal: pass
    def compare(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def compare_signal(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def compare_total(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def compare_total_mag(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def conjugate(self) -> Decimal: pass
    def copy_abs(self) -> Decimal: pass
    def copy_negate(self) -> Decimal: pass
    def copy_sign(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def exp(self, context: Context = None) -> Decimal: pass
    def fma(self, other: _Decimal, third: _Decimal, context: Context = None) -> Decimal: pass
    @classmethod
    def from_float(cls, f: float) -> Decimal: pass
    def is_canonical(self) -> bool: pass
    def is_finite(self) -> bool: pass
    def is_infinite(self) -> bool: pass
    def is_nan(self) -> bool: pass
    def is_normal(self, context: Context = None) -> bool: pass
    def is_qnan(self) -> bool: pass
    def is_signed(self) -> bool: pass
    def is_snan(self) -> bool: pass
    def is_subnormal(self, context: Context = None) -> bool: pass
    def is_zero(self) -> bool: pass
    def ln(self, context: Context = None) -> Decimal: pass
    def log10(self, context: Context = None) -> Decimal: pass
    def logb(self, context: Context = None) -> Decimal: pass
    def logical_and(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def logical_invert(self, context: Context = None) -> Decimal: pass
    def logical_or(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def logical_xor(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def max(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def max_mag(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def min(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def min_mag(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def next_minus(self, context: Context = None) -> Decimal: pass
    def next_plus(self, context: Context = None) -> Decimal: pass
    def next_toward(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def normalize(self, context: Context = None) -> Decimal: pass
    def number_class(self, context: Context = None) -> str: pass
    def quantize(self, exp: _Decimal, rounding: str = None,
                 context: Context = None) -> Decimal: pass
    def radix(self) -> Decimal: pass
    def remainder_near(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def rotate(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def same_quantum(self, other: _Decimal, context: Context = None) -> bool: pass
    def scaleb(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def shift(self, other: _Decimal, context: Context = None) -> Decimal: pass
    def sqrt(self, context: Context = None) -> Decimal: pass
    def to_eng_string(self, context: Context = None) -> str: pass
    def to_integral(self, rounding: str = None, context: Context = None) -> Decimal: pass
    def to_integral_exact(self, rounding: str = None, context: Context = None) -> Decimal: pass
    def to_integral_value(self, rounding: str = None, context: Context = None) -> Decimal: pass
    def __abs__(self) -> Decimal: pass
    def __add__(self, other: _Decimal) -> Decimal: pass
    def __bool__(self) -> bool: pass
    def __ceil__(self) -> int: pass
    def __complex__(self) -> complex: pass
    def __copy__(self) -> Decimal: pass
    def __deepcopy__(self) -> Decimal: pass
    def __divmod__(self, other: _Decimal) -> Tuple[Decimal, Decimal]: pass
    def __eq__(self, other: object) -> bool: pass
    def __float__(self) -> float: pass
    def __floor__(self) -> int: pass
    def __floordiv__(self, other: _Decimal) -> Decimal: pass
    def __format__(self, specifier, context=None, _localeconv=None) -> str: pass
    def __ge__(self, other: _Decimal) -> bool: pass
    def __gt__(self, other: _Decimal) -> bool: pass
    def __hash__(self) -> int: pass
    def __int__(self) -> int: pass
    def __le__(self, other: _Decimal) -> bool: pass
    def __lt__(self, other: _Decimal) -> bool: pass
    def __mod__(self, other: _Decimal) -> Decimal: pass
    def __mul__(self, other: _Decimal) -> Decimal: pass
    def __ne__(self, other: object) -> bool: pass
    def __neg__(self) -> Decimal: pass
    def __pos__(self) -> Decimal: pass
    def __pow__(self, other: _Decimal) -> Decimal: pass
    def __radd__(self, other: int) -> Decimal: pass
    def __rdivmod__(self, other: int) -> Tuple[Decimal, Decimal]: pass
    def __reduce__(self): pass
    def __rfloordiv__(self, other: int) -> Decimal: pass
    def __rmod__(self, other: int) -> Decimal: pass
    def __rmul__(self, other: int) -> Decimal: pass
    def __round__(self, n=None) -> int: pass
    def __rpow__(self, other: int) -> Decimal: pass
    def __rsub__(self, other: int) -> Decimal: pass
    def __rtruediv__(self, other: int) -> Decimal: pass
    def __sizeof__(self) -> int: pass
    def __sub__(self, other: _Decimal) -> Decimal: pass
    def __truediv__(self, other: _Decimal) -> Decimal: pass
    def __trunc__(self) -> int: pass

class DecimalException(ArithmeticError): pass

class Clamped(DecimalException): pass

class DivisionByZero(DecimalException, ZeroDivisionError): pass

class DivisionImpossible(InvalidOperation): pass

class DivisionUndefined(InvalidOperation, ZeroDivisionError): pass

class FloatOperation(DecimalException, TypeError): pass

class Inexact(DecimalException): pass

class InvalidContext(InvalidOperation): pass

class InvalidOperation(DecimalException): pass

class Overflow(Inexact, Rounded): pass

class Rounded(DecimalException): pass

class Subnormal(DecimalException): pass

class Underflow(Inexact, Rounded, Subnormal): pass
