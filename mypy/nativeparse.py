"""Python parser that directly constructs a native AST (when compiled).

Use a Rust extension to generate a serialized AST, and deserialize the AST directly
to a mypy AST.

NOTE: This is heavily work in progress.

Key planned features compared the mypy.fastparse:
 * No intermediate non-mypyc AST created, to improve performance
 * Support all Python syntax even if running mypy on older Python versions
 * Parsing doesn't need GIL => multithreading to produce serialized AST in parallel
 * Produce import dependencies without having to build an AST (helps parallel type checking)
"""

from __future__ import annotations

import os
import subprocess

from mypy.nodes import MypyFile


def native_parse(filename: str) -> MypyFile:
    assert False


def parse_to_binary_ast(filename: str) -> bytes:
    binpath = os.path.expanduser("~/src/ruff/target/release/mypy_parser")
    result = subprocess.run([binpath, "serialize-ast", filename], capture_output=True, check=True)
    return result.stdout
