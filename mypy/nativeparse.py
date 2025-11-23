"""Python parser that directly constructs a native AST (when compiled).

Use a Rust extension to generate a serialized AST, and deserialize the AST directly
to a mypy AST.

NOTE: This is heavily work in progress.

Expected benefits over mypy.fastparse:
 * No intermediate non-mypyc AST created, to improve performance
 * Parsing doesn't need GIL => use multithreading to construct serialized ASTs in parallel
 * Produce import dependencies without having to build an AST => helps parallel type checking
 * Support all Python syntax even if running mypy on an older Python version
 * Generate an AST even if there are syntax errors
 * Potential to support incremental parsing (quickly process modified sections in a file)
 * Stripping function bodies in third-party code can happen earlier, for extra performance
"""

from __future__ import annotations

import os
import subprocess

from mypy import nodes
from mypy.cache import (
    END_TAG,
    LIST_GEN,
    LOCATION,
    ReadBuffer,
    Tag,
    read_int,
    read_int_bare,
    read_str,
    read_tag,
)
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


def expect_end_tag(data: ReadBuffer) -> None:
    assert read_tag(data) == END_TAG


def expect_tag(data: ReadBuffer, tag: Tag) -> None:
    assert read_tag(data) == tag


def native_parse(filename: str) -> MypyFile:
    b = parse_to_binary_ast(filename)
    data = ReadBuffer(b)
    n = read_int(data)
    defs = []
    for i in range(n):
        defs.append(read_statement(data))
    return MypyFile(defs, [])


def parse_to_binary_ast(filename: str) -> bytes:
    binpath = os.path.expanduser("~/src/ruff/target/release/mypy_parser")
    result = subprocess.run([binpath, "serialize-ast", filename], capture_output=True, check=True)
    return result.stdout


def read_statement(data: ReadBuffer) -> Statement:
    tag = read_tag(data)
    if tag == nodes.EXPR_STMT:
        es = ExpressionStmt(read_expression(data))
        es.line = es.expr.line
        es.column = es.expr.column
        es.end_line = es.expr.end_line
        es.end_column = es.expr.end_column
        expect_end_tag(data)
        return es
    else:
        assert False, tag


def read_expression(data: ReadBuffer) -> Expression:
    tag = read_tag(data)
    if tag == nodes.CALL_EXPR:
        callee = read_expression(data)
        args = read_expression_list(data)
        n = len(args)
        ce = CallExpr(callee, args, [ARG_POS] * n, [None] * n)
        read_loc(data, ce)
        expect_end_tag(data)
        return ce
    elif tag == nodes.NAME_EXPR:
        s = read_str(data)
        ne = NameExpr(s)
        read_loc(data, ne)
        expect_end_tag(data)
        return ne
    elif tag == nodes.STR_EXPR:
        se = StrExpr(read_str(data))
        read_loc(data, se)
        expect_end_tag(data)
        return se
    else:
        assert False


def read_expression_list(data: ReadBuffer) -> list[Expression]:
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    return [read_expression(data) for i in range(n)]


def read_loc(data: ReadBuffer, node: Node) -> None:
    expect_tag(data, LOCATION)
    line = read_int_bare(data)
    node.line = line
    column = read_int_bare(data)
    node.column = column
    node.end_line = line + read_int_bare(data)
    node.end_column = column + read_int_bare(data)
