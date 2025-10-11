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

from mypy import nodes
from mypy.cache import Buffer, read_int, read_str, read_tag
from mypy.nodes import (
    ARG_POS,
    CallExpr,
    Expression,
    ExpressionStmt,
    MypyFile,
    NameExpr,
    Statement,
    StrExpr,
)


def native_parse(filename: str) -> MypyFile:
    b = parse_to_binary_ast(filename)
    print(repr(b))
    data = Buffer(b)
    n = read_int(data)
    defs = []
    for i in range(n):
        defs.append(read_statement(data))
    return MypyFile(defs, [])


def parse_to_binary_ast(filename: str) -> bytes:
    binpath = os.path.expanduser("~/src/ruff/target/release/mypy_parser")
    result = subprocess.run([binpath, "serialize-ast", filename], capture_output=True, check=True)
    return result.stdout


def read_statement(data: Buffer) -> Statement:
    tag = read_tag(data)
    if tag == nodes.EXPR_STMT:
        return ExpressionStmt(read_expression(data))
    else:
        assert False


def read_expression(data: Buffer) -> Expression:
    tag = read_tag(data)
    if tag == nodes.CALL_EXPR:
        callee = read_expression(data)
        n = read_int(data)
        args = [read_expression(data) for i in range(n)]
        return CallExpr(callee, args, [ARG_POS] * n, [None] * n)
    elif tag == nodes.NAME_EXPR:
        n = read_str(data)
        return NameExpr(n)
    elif tag == nodes.STR_EXPR:
        return StrExpr(read_str(data))
    else:
        assert False
