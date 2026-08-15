"""Python parser that directly constructs a native AST (when compiled).

Use a Rust extension to generate a serialized AST, and deserialize the AST directly
to a mypy AST.

NOTE: This is work in progress. To use this, you need to manually build the
      ast_serialize Rust extension. See the README at https://github.com/mypyc/ast_serialize.

Expected benefits over mypy.fastparse:
 * No intermediate non-mypyc Python-level AST created, to improve performance
 * Parsing doesn't need GIL => use multithreading to construct serialized ASTs in parallel
 * Produce import dependencies without having to build an AST => helps parallel type checking
 * Support all Python syntax even if mypy is running on an older Python version
 * Generate an AST even if there are syntax errors
 * Potential to support incremental parsing (quickly process modified sections in a file)
 * Stripping function bodies in third-party code can happen earlier, for extra performance
"""

from __future__ import annotations

import os
import time
import importlib
from typing import Final, cast

try:
    import ast_serialize
    from librt.internal import (
        read_float as read_float_bare,
        read_int as read_int_bare,
        read_str as read_str_bare,
    )
except ImportError:
    pass

from mypy import message_registry, nodes, types
from mypy.cache import (
    DICT_STR_GEN,
    END_TAG,
    LIST_GEN,
    LIST_INT,
    LITERAL_FLOAT,
    LITERAL_NONE,
    LITERAL_STR,
    LOCATION,
    ReadBuffer,
    Tag,
    read_bool,
    read_int,
    read_str,
    read_str_opt,
    read_tag,
)
