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
    Node,
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
        es = ExpressionStmt(read_expression(data))
        es.line = es.expr.line
        es.column = es.expr.column
        es.end_line = es.expr.end_line
        es.end_column = es.expr.end_column
        return es
    else:
        assert False


def read_expression(data: Buffer) -> Expression:
    tag = read_tag(data)
    if tag == nodes.CALL_EXPR:
        callee = read_expression(data)
        n = read_int(data)
        args = [read_expression(data) for i in range(n)]
        ce = CallExpr(callee, args, [ARG_POS] * n, [None] * n)
        read_loc(data, ce)
        return ce
    elif tag == nodes.NAME_EXPR:
        n = read_str(data)
        ne = NameExpr(n)
        read_loc(data, ne)
        return ne
    elif tag == nodes.STR_EXPR:
        se = StrExpr(read_str(data))
        read_loc(data, se)
        return se
    else:
        assert False


def read_loc(data: Buffer, node: Node) -> None:
    line = read_int(data)
    node.line = line
    node.column = read_int(data)
    node.end_line = line + read_int(data)
    node.end_column = read_int(data)
