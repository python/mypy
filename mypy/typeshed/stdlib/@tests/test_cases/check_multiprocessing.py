from __future__ import annotations

from ctypes import c_char, c_float
from multiprocessing import Array, Value
from multiprocessing.sharedctypes import Synchronized, SynchronizedString
from typing_extensions import assert_type

string = Array(c_char, 12)
assert_type(string, SynchronizedString)
assert_type(string.value, bytes)

field = Value(c_float, 0.0)
assert_type(field, Synchronized[float])
field.value = 1.2
