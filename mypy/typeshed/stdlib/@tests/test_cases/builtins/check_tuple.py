from __future__ import annotations

from typing import Tuple
from typing_extensions import assert_type


# Empty tuples, see #8275
class TupleSub(Tuple[int, ...]):
    pass


assert_type(TupleSub(), TupleSub)
assert_type(TupleSub([1, 2, 3]), TupleSub)
