from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Any, Literal
from typing_extensions import assert_type

# See #7163
assert_type(pow(1, 0), Literal[1])
assert_type(1**0, Literal[1])
assert_type(pow(1, 0, None), Literal[1])

# TODO: We don't have a good way of expressing the fact
# that passing 0 for the third argument will lead to an exception being raised
# (see discussion in #8566)
#
# assert_type(pow(2, 4, 0), NoReturn)

assert_type(pow(2, 4), int)
assert_type(2**4, int)
assert_type(pow(4, 6, None), int)

assert_type(pow(5, -7), float)
assert_type(5**-7, float)

assert_type(pow(2, 4, 5), int)  # pow(<smallint>, <smallint>, <smallint>)
assert_type(pow(2, 35, 3), int)  # pow(<smallint>, <bigint>, <smallint>)

assert_type(pow(2, 8.5), float)
assert_type(2**8.6, float)
assert_type(pow(2, 8.6, None), float)

# TODO: Why does this pass pyright but not mypy??
# assert_type((-2) ** 0.5, complex)

assert_type(pow((-5), 8.42, None), complex)

assert_type(pow(4.6, 8), float)
assert_type(4.6**8, float)
assert_type(pow(5.1, 4, None), float)

assert_type(pow(complex(6), 6.2), complex)
assert_type(complex(6) ** 6.2, complex)
assert_type(pow(complex(9), 7.3, None), complex)

assert_type(pow(Fraction(), 4, None), Fraction)
assert_type(Fraction() ** 4, Fraction)

assert_type(pow(Fraction(3, 7), complex(1, 8)), complex)
assert_type(Fraction(3, 7) ** complex(1, 8), complex)

assert_type(pow(complex(4, -8), Fraction(2, 3)), complex)
assert_type(complex(4, -8) ** Fraction(2, 3), complex)

assert_type(pow(Decimal("1.0"), Decimal("1.6")), Decimal)
assert_type(Decimal("1.0") ** Decimal("1.6"), Decimal)

assert_type(pow(Decimal("1.0"), Decimal("1.0"), Decimal("1.0")), Decimal)
assert_type(pow(Decimal("4.6"), 7, None), Decimal)
assert_type(Decimal("4.6") ** 7, Decimal)

# These would ideally be more precise, but `Any` is acceptable
# They have to be `Any` due to the fact that type-checkers can't distinguish
# between positive and negative numbers for the second argument to `pow()`
#
# int for positive 2nd-arg, float otherwise
assert_type(pow(4, 65), Any)
assert_type(pow(2, -45), Any)
assert_type(pow(3, 57, None), Any)
assert_type(pow(67, 0.98, None), Any)
assert_type(87**7.32, Any)
# pow(<pos-float>, <pos-or-neg-float>) -> float
# pow(<neg-float>, <pos-or-neg-float>) -> complex
assert_type(pow(4.7, 7.4), Any)
assert_type(pow(-9.8, 8.3), Any)
assert_type(pow(-9.3, -88.2), Any)
assert_type(pow(8.2, -9.8), Any)
assert_type(pow(4.7, 9.2, None), Any)
# See #7046 -- float for a positive 1st arg, complex otherwise
assert_type((-95) ** 8.42, Any)

# All of the following cases should fail a type-checker.
pow(1.9, 4, 6)  # type: ignore
pow(4, 7, 4.32)  # type: ignore
pow(6.2, 5.9, 73)  # type: ignore
pow(complex(6), 6.2, 7)  # type: ignore
pow(Fraction(), 5, 8)  # type: ignore
Decimal("8.7") ** 3.14  # type: ignore

# TODO: This fails at runtime, but currently passes mypy and pyright:
pow(Decimal("8.5"), 3.21)
