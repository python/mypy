# Stubs for calendar

# NOTE: These are incomplete!

from typing import overload, Tuple

# TODO actually, any number of items larger than 5 is fine
@overload
def timegm(t: Tuple[int, int, int, int, int, int]) -> int: pass
@overload
def timegm(t: Tuple[int, int, int, int, int, int, int]) -> int: pass
@overload
def timegm(t: Tuple[int, int, int, int, int, int, int, int]) -> int: pass
@overload
def timegm(t: Tuple[int, int, int, int, int, int, int, int, int]) -> int: pass
