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
from typing import Final

from mypy import nodes
from mypy.cache import (
    END_TAG,
    LIST_GEN,
    LIST_INT,
    LOCATION,
    ReadBuffer,
    Tag,
    read_int,
    read_int_bare,
    read_str,
    read_tag,
    read_bool,
)
from mypy.nodes import (
    ARG_POS,
    ARG_OPT,
    ARG_STAR,
    ARG_NAMED,
    ARG_STAR2,
    ARG_NAMED_OPT,
    ARG_KINDS,
    Argument,
    AssignmentStmt,
    Block,
    CallExpr,
    ComparisonExpr,
    Expression,
    ExpressionStmt,
    FuncDef,
    IfStmt,
    IndexExpr,
    IntExpr,
    ListExpr,
    MemberExpr,
    MypyFile,
    NameExpr,
    Node,
    OpExpr,
    ReturnStmt,
    SetExpr,
    Statement,
    StrExpr,
    TupleExpr,
    Var,
    WhileStmt,
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
    node = MypyFile(defs, [])
    node.path = filename
    return node


def parse_to_binary_ast(filename: str) -> bytes:
    binpath = os.path.expanduser("~/src/ruff/target/release/mypy_parser")
    result = subprocess.run([binpath, "serialize-ast", filename], capture_output=True, check=True)
    return result.stdout


def read_statement(data: ReadBuffer) -> Statement:
    tag = read_tag(data)
    stmt: Statement
    if tag == nodes.FUNC_DEF_STMT:
        # Function name
        name = read_str(data)

        # Arguments
        expect_tag(data, LIST_GEN)
        n_args = read_int_bare(data)
        arguments = []
        for _ in range(n_args):
            arg_name = read_str(data)
            arg_kind_int = read_int(data)
            # Convert integer to ArgKind enum using ARG_KINDS tuple
            arg_kind = ARG_KINDS[arg_kind_int]
            # TODO: Read type annotation when implemented
            has_type = read_bool(data)
            assert not has_type, "Type annotations not yet supported"
            # TODO: Read default value when implemented
            has_default = read_bool(data)
            assert not has_default, "Default values not yet supported"
            pos_only = read_bool(data)

            var = Var(arg_name)
            arg = Argument(var, None, None, arg_kind, pos_only)
            arguments.append(arg)

        # Body
        body = read_block(data)

        # Decorators
        expect_tag(data, LIST_GEN)
        n_decorators = read_int_bare(data)
        assert n_decorators == 0, "Decorators not yet supported"

        # is_async
        is_async = read_bool(data)

        # TODO: type_params
        has_type_params = read_bool(data)
        assert not has_type_params, "Type params not yet supported"

        # TODO: Return type annotation
        has_return_type = read_bool(data)
        assert not has_return_type, "Return type annotations not yet supported"

        func_def = FuncDef(name, arguments, body)
        if is_async:
            func_def.is_coroutine = True
        read_loc(data, func_def)
        expect_end_tag(data)
        return func_def
    elif tag == nodes.EXPR_STMT:
        es = ExpressionStmt(read_expression(data))
        es.line = es.expr.line
        es.column = es.expr.column
        es.end_line = es.expr.end_line
        es.end_column = es.expr.end_column
        expect_end_tag(data)
        return es
    elif tag == nodes.ASSIGNMENT_STMT:
        lvalues = read_expression_list(data)
        rvalue = read_expression(data)
        a = AssignmentStmt(lvalues, rvalue)
        read_loc(data, a)
        expect_end_tag(data)
        return a
    elif tag == nodes.IF_STMT:
        expr = [read_expression(data)]
        body = [read_block(data)]
        num_elif = read_int(data)
        for i in range(num_elif):
            expr.append(read_expression(data))
            body.append(read_block(data))
        has_else = read_bool(data)
        if has_else:
            else_body = read_block(data)
        else:
            else_body = None
        if_stmt = IfStmt(expr, body, else_body)
        read_loc(data, if_stmt)
        expect_end_tag(data)
        return if_stmt
    elif tag == nodes.RETURN_STMT:
        has_value = read_bool(data)
        if has_value:
            value = read_expression(data)
        else:
            value = None
        stmt = ReturnStmt(value)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.WHILE_STMT:
        expr = read_expression(data)
        body = read_block(data)
        else_body = read_optional_block(data)
        stmt = WhileStmt(expr, body, else_body)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    else:
        assert False, tag


def read_block(data: ReadBuffer) -> Block:
    expect_tag(data, nodes.BLOCK)
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    assert n > 0
    a = [read_statement(data) for i in range(n)]
    expect_end_tag(data)
    b = Block(a)
    b.line = a[0].line
    b.column = a[0].column
    b.end_line = a[-1].end_line
    b.end_column = a[-1].end_column
    return b


def read_optional_block(data: ReadBuffer) -> Block | None:
    expect_tag(data, nodes.BLOCK)
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    if n == 0:
        b = None
    else:
        a = [read_statement(data) for i in range(n)]
        b = Block(a)
        b.line = a[0].line
        b.column = a[0].column
        b.end_line = a[-1].end_line
        b.end_column = a[-1].end_column
    expect_end_tag(data)
    return b


bin_ops: Final = ["+", "-", "*", "@", "/", "%", "**", "<<", ">>", "|", "^", "&", "//"]
bool_ops: Final = ["and", "or"]
cmp_ops: Final = ["==", "!=", "<", "<=", ">", ">=", "is", "is not", "in", "not in"]


def read_expression(data: ReadBuffer) -> Expression:
    tag = read_tag(data)
    expr: Expression
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
    elif tag == nodes.MEMBER_EXPR:
        e = read_expression(data)
        attr = read_str(data)
        m = MemberExpr(e, attr)
        read_loc(data, m)
        expect_end_tag(data)
        return m
    elif tag == nodes.STR_EXPR:
        se = StrExpr(read_str(data))
        read_loc(data, se)
        expect_end_tag(data)
        return se
    elif tag == nodes.INT_EXPR:
        ie = IntExpr(read_int(data))
        read_loc(data, ie)
        expect_end_tag(data)
        return ie
    elif tag == nodes.LIST_EXPR:
        items = read_expression_list(data)
        expr = ListExpr(items)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.TUPLE_EXPR:
        items = read_expression_list(data)
        t = TupleExpr(items)
        read_loc(data, t)
        expect_end_tag(data)
        return t
    elif tag == nodes.SET_EXPR:
        items = read_expression_list(data)
        expr = SetExpr(items)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.OP_EXPR:
        op = bin_ops[read_int(data)]
        left = read_expression(data)
        right = read_expression(data)
        o = OpExpr(op, left, right)
        # TODO: Store these explicitly?
        o.line = left.line
        o.column = left.column
        o.end_line = right.end_line
        o.end_column = right.end_column
        expect_end_tag(data)
        return o
    elif tag == nodes.INDEX_EXPR:
        base = read_expression(data)
        index = read_expression(data)
        expr = IndexExpr(base, index)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.BOOL_OP_EXPR:
        op = bool_ops[read_int(data)]
        values = read_expression_list(data)
        # Convert list of values to nested OpExpr nodes
        # E.g., [a, b, c] with "and" becomes OpExpr("and", OpExpr("and", a, b), c)
        assert len(values) >= 2
        result = values[0]
        for val in values[1:]:
            result = OpExpr(op, result, val)
            result.line = values[0].line
            result.column = values[0].column
            result.end_line = val.end_line
            result.end_column = val.end_column
        read_loc(data, result)
        expect_end_tag(data)
        return result
    elif tag == nodes.COMPARISON_EXPR:
        left = read_expression(data)
        # Read operators list
        expect_tag(data, LIST_INT)
        n_ops = read_int_bare(data)
        ops = [cmp_ops[read_int_bare(data)] for _ in range(n_ops)]
        # Read comparators list
        comparators = read_expression_list(data)
        assert len(ops) == len(comparators)
        expr = ComparisonExpr(ops, [left] + comparators)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    else:
        assert False, tag


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
