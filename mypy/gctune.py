"""Tuning cyclic garbage collector (GC) parameters for better performance.

Since this is called very early, before most imports, don't add new import
dependencies!
"""

import gc
import platform


def tune_gc() -> None:
    if platform.python_implementation() == "CPython":
        # Run gc less frequently, as otherwise we can spent a large fraction of
        # cpu in gc.
        gc.set_threshold(200 * 1000, 30, 30)
