# pyright: reportWildcardImportFromLibrary=false
"""
This tests that star imports work when using "all += " syntax.
"""
from __future__ import annotations

import sys
from typing import *
from zipfile import *

if sys.version_info >= (3, 9):
    x: Annotated[int, 42]

p: Path
