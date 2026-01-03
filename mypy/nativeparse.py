# mypy: allow-redefinition-new, local-partial-types
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

from typing import Final, cast, Any

import ast_serialize  # type: ignore[import-untyped]

from mypy import nodes, types
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
    read_int,
    read_str,
    read_tag,
    read_bool,
)
from librt.internal import read_str as read_str_bare, read_float as read_float_bare, read_int as read_int_bare
from mypy.nodes import (
    ARG_POS,
    ARG_OPT,
    ARG_STAR,
    ARG_NAMED,
    ARG_STAR2,
    ARG_NAMED_OPT,
    ARG_KINDS,
    Argument,
    AssertStmt,
    AssignmentExpr,
    AwaitExpr,
    AssignmentStmt,
    Block,
    BreakStmt,
    BytesExpr,
    CallExpr,
    ClassDef,
    ComparisonExpr,
    ConditionalExpr,
    ContinueStmt,
    ComplexExpr,
    Context,
    Decorator,
    DelStmt,
    DictExpr,
    DictionaryComprehension,
    EllipsisExpr,
    Expression,
    ExpressionStmt,
    FloatExpr,
    ForStmt,
    FuncDef,
    GeneratorExpr,
    GlobalDecl,
    IfStmt,
    Import,
    ImportFrom,
    ListComprehension,
    SetComprehension,
    IndexExpr,
    IntExpr,
    LambdaExpr,
    ListExpr,
    MemberExpr,
    MypyFile,
    NameExpr,
    Node,
    NonlocalDecl,
    OpExpr,
    OperatorAssignmentStmt,
    OverloadedFuncDef,
    PassStmt,
    RaiseStmt,
    ReturnStmt,
    SetExpr,
    SliceExpr,
    StarExpr,
    Statement,
    StrExpr,
    TempNode,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    Var,
    WhileStmt,
    WithStmt,
    YieldExpr,
    YieldFromExpr,
    MISSING_FALLBACK,
)
from mypy.types import CallableType, UnboundType, NoneType, UnionType, AnyType, TypeOfAny, Instance, Type, TypeList, EllipsisType, RawExpressionType


TypeIgnores = list[tuple[int, list[str]]]


# There is no way to create reasonable fallbacks at this stage,
# they must be patched later.
_dummy_fallback: Final = Instance(MISSING_FALLBACK, [], -1)


def expect_end_tag(data: ReadBuffer) -> None:
    assert read_tag(data) == END_TAG


def expect_tag(data: ReadBuffer, tag: Tag) -> None:
    assert read_tag(data) == tag


def native_parse(filename: str) -> tuple[MypyFile, list[dict[str, Any]], TypeIgnores]:
    b, errors, ignores = parse_to_binary_ast(filename)
    data = ReadBuffer(b)
    n = read_int(data)
    defs = read_statements(data, n)
    node = MypyFile(defs, [])
    node.path = filename
    return node, errors, ignores


def read_statements(data: ReadBuffer, n: int) -> list[Statement]:
    defs = []
    prev_func = False
    prev_name = ""
    for _ in range(n):
        stmt = read_statement(data)
        if isinstance(stmt, (FuncDef, Decorator)):
            if prev_func and stmt.name == prev_name:
                # Merge into overloaded function definition
                prev = defs[-1]
                if isinstance(prev, OverloadedFuncDef):
                    prev.items.append(stmt)
                else:
                    defs[-1] = OverloadedFuncDef([prev, stmt])
            else:
                defs.append(stmt)
                prev_name = stmt.name
            prev_func = True
        else:
            defs.append(stmt)
            prev_func = False
    return defs


def parse_to_binary_ast(filename: str) -> tuple[bytes, list[dict[str, Any]], TypeIgnores]:
    return ast_serialize.parse(filename)  # type: ignore[no-any-return]


def read_statement(data: ReadBuffer) -> Statement:
    tag = read_tag(data)
    stmt: Statement
    if tag == nodes.FUNC_DEF_STMT:
        return read_func_def(data)
    elif tag == nodes.DECORATOR:
        expect_tag(data, LIST_GEN)
        n_decorators = read_int_bare(data)
        decorators = [read_expression(data) for i in range(n_decorators)]
        line = read_int(data)
        column = read_int(data)
        fdef = read_statement(data)
        assert isinstance(fdef, FuncDef)
        var = Var(fdef.name)
        var.line = fdef.line
        var.is_ready = False
        # Create Decorator wrapping the FuncDef
        stmt = Decorator(fdef, decorators, var)
        stmt.line = line
        stmt.column = column
        stmt.end_line = fdef.end_line
        stmt.end_column = fdef.end_column
        # TODO: Adjust funcdef location to start after decorator?
        expect_end_tag(data)
        return stmt
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
        # Read type annotation
        has_type = read_bool(data)
        if has_type:
            type_annotation = read_type(data)
        else:
            type_annotation = None
        # Read new_syntax flag
        new_syntax = read_bool(data)
        a = AssignmentStmt(lvalues, rvalue, type=type_annotation, new_syntax=new_syntax)
        read_loc(data, a)
        # If rvalue is TempNode, copy location from AssignmentStmt
        if isinstance(rvalue, TempNode):
            rvalue.line = a.line
            rvalue.column = a.column
            rvalue.end_line = a.end_line
            rvalue.end_column = a.end_column
        expect_end_tag(data)
        return a
    elif tag == nodes.OPERATOR_ASSIGNMENT_STMT:
        # Read operator string
        op = read_str(data)
        # Read lvalue (target)
        lvalue = read_expression(data)
        # Read rvalue (value)
        rvalue = read_expression(data)
        stmt = OperatorAssignmentStmt(op, lvalue, rvalue)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
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
    elif tag == nodes.RAISE_STMT:
        # Read exception expression (optional)
        has_exc = read_bool(data)
        if has_exc:
            exc = read_expression(data)
        else:
            exc = None
        # Read from expression (optional)
        has_from = read_bool(data)
        if has_from:
            from_expr = read_expression(data)
        else:
            from_expr = None
        stmt = RaiseStmt(exc, from_expr)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.ASSERT_STMT:
        # Read test expression
        test = read_expression(data)
        # Read optional message expression
        has_msg = read_bool(data)
        if has_msg:
            msg = read_expression(data)
        else:
            msg = None
        stmt = AssertStmt(test, msg)
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
    elif tag == nodes.FOR_STMT:
        # Read index (target)
        index = read_expression(data)
        # Read iterator expression
        expr = read_expression(data)
        # Read body
        body = read_block(data)
        # Read else clause
        else_body = read_optional_block(data)
        stmt = ForStmt(index, expr, body, else_body)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.WITH_STMT:
        # Read number of items
        n = read_int(data)
        expr_list = []
        target_list: list[Expression | None] = []
        # Read each item
        for _ in range(n):
            # Read context expression
            context_expr = read_expression(data)
            expr_list.append(context_expr)
            # Read optional target
            has_target = read_bool(data)
            if has_target:
                target = read_expression(data)
                target_list.append(target)
            else:
                target_list.append(None)
        # Read body
        body = read_block(data)
        stmt = WithStmt(expr_list, target_list, body)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.PASS_STMT:
        stmt = PassStmt()
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.BREAK_STMT:
        stmt = BreakStmt()
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.CONTINUE_STMT:
        stmt = ContinueStmt()
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.IMPORT:
        # Read number of imports
        n = read_int(data)
        ids = []
        for _ in range(n):
            # Read import name
            name = read_str(data)
            # Read as_name (optional)
            has_asname = read_bool(data)
            if has_asname:
                asname = read_str(data)
            else:
                asname = None
            ids.append((name, asname))
        stmt = Import(ids)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.IMPORT_FROM:
        # Read relative import level
        relative = read_int(data)

        # Read module name (empty string for "from . import x")
        module_id = read_str(data)

        # Read number of imported names
        n = read_int(data)
        names = []
        for _ in range(n):
            # Read imported name
            name = read_str(data)
            # Read optional alias
            has_asname = read_bool(data)
            if has_asname:
                asname = read_str(data)
            else:
                asname = None
            names.append((name, asname))

        stmt = ImportFrom(module_id, relative, names)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.CLASS_DEF:
        return read_class_def(data)
    elif tag == nodes.TRY_STMT:
        return read_try_stmt(data)
    elif tag == nodes.DEL_STMT:
        # Read the target expression
        expr = read_expression(data)
        stmt = DelStmt(expr)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.GLOBAL_DECL:
        # Read number of names
        n = read_int(data)
        names = []
        for _ in range(n):
            names.append(read_str(data))
        stmt = GlobalDecl(names)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.NONLOCAL_DECL:
        # Read number of names
        n = read_int(data)
        names = []
        for _ in range(n):
            names.append(read_str(data))
        stmt = NonlocalDecl(names)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    else:
        assert False, tag


def read_parameters(data: ReadBuffer) -> tuple[list[Argument], bool]:
    """Read function/lambda parameters from the buffer.

    Returns:
        A tuple of (arguments list, has_annotations flag)
    """
    expect_tag(data, LIST_GEN)
    n_args = read_int_bare(data)
    arguments = []
    has_ann = False
    for _ in range(n_args):
        arg_name = read_str(data)
        arg_kind_int = read_int(data)
        # Convert integer to ArgKind enum using ARG_KINDS tuple
        arg_kind = ARG_KINDS[arg_kind_int]
        # Read type annotation
        has_type = read_bool(data)
        if has_type:
            ann = read_type(data)
            has_ann = True
        else:
            ann = None
        # Read default value
        has_default = read_bool(data)
        if has_default:
            default = read_expression(data)
        else:
            default = None
        pos_only = read_bool(data)

        var = Var(arg_name)
        arg = Argument(var, ann, default, arg_kind, pos_only)
        read_loc(data, arg)
        var.line = arg.line
        var.column = arg.column
        var.end_line = arg.end_line
        var.end_column = arg.end_column
        arguments.append(arg)

    return arguments, has_ann


def read_func_def(data: ReadBuffer) -> FuncDef:
    # Function name
    name = read_str(data)

    # Parameters
    arguments, has_ann = read_parameters(data)

    body = read_block(data)

    is_async = read_bool(data)

    # TODO: type_params
    has_type_params = read_bool(data)
    assert not has_type_params, "Type params not yet supported"

    # TODO: Return type annotation
    has_return_type = read_bool(data)
    if has_return_type:
        return_type = read_type(data)
        has_ann = True
    else:
        return_type = None

    if has_ann:
        typ = CallableType(
            [arg.type_annotation if arg.type_annotation else AnyType(TypeOfAny.unannotated)
                for arg in arguments],
            [arg.kind for arg in arguments],
            [arg.variable.name for arg in arguments],
            return_type if return_type else AnyType(TypeOfAny.unannotated),
            _dummy_fallback
            )
    else:
        typ = None

    func_def = FuncDef(name, arguments, body, typ=typ)
    if is_async:
        func_def.is_coroutine = True
    read_loc(data, func_def)
    expect_end_tag(data)
    return func_def


def read_class_def(data: ReadBuffer) -> ClassDef:
    # Class name
    name = read_str(data)

    # Body
    body = read_block(data)

    # Base classes
    base_type_exprs = read_expression_list(data)

    # TODO: Decorators (skip for now)
    expect_tag(data, LIST_GEN)
    n_decorators = read_int_bare(data)
    assert n_decorators == 0, "Decorators not yet supported"

    # TODO: Type parameters (skip for now)
    has_type_params = read_bool(data)
    assert not has_type_params, "Type parameters not yet supported"

    # TODO: Metaclass (skip for now)
    has_metaclass = read_bool(data)
    assert not has_metaclass, "Metaclass not yet supported"

    # TODO: Keywords (skip for now)
    expect_tag(data, DICT_STR_GEN)
    n_keywords = read_int_bare(data)
    assert n_keywords == 0, "Keywords not yet supported"

    class_def = ClassDef(name, body, base_type_exprs=base_type_exprs if base_type_exprs else None)
    read_loc(data, class_def)
    expect_end_tag(data)
    return class_def


def read_try_stmt(data: ReadBuffer) -> TryStmt:
    # Read try body
    body = read_block(data)

    # Read number of except handlers
    num_handlers = read_int(data)

    # Read exception types for each handler
    types_list = []
    for _ in range(num_handlers):
        has_type = read_bool(data)
        if has_type:
            exc_type = read_expression(data)
            types_list.append(exc_type)
        else:
            types_list.append(None)

    # Read variable names for each handler
    vars_list = []
    for _ in range(num_handlers):
        has_name = read_bool(data)
        if has_name:
            var_name = read_str(data)
            var_expr = NameExpr(var_name)
            vars_list.append(var_expr)
        else:
            vars_list.append(None)

    # Read handler bodies
    handlers = []
    for _ in range(num_handlers):
        handler_body = read_block(data)
        handlers.append(handler_body)

    # Read else body (optional)
    has_else = read_bool(data)
    if has_else:
        else_body = read_block(data)
    else:
        else_body = None

    # Read finally body (optional)
    has_finally = read_bool(data)
    if has_finally:
        finally_body = read_block(data)
    else:
        finally_body = None

    stmt = TryStmt(body, vars_list, types_list, handlers, else_body, finally_body)
    read_loc(data, stmt)
    expect_end_tag(data)
    return stmt


def read_type(data: ReadBuffer) -> Type:
    tag = read_tag(data)
    if tag == types.UNBOUND_TYPE:
        name = read_str(data)
        expect_tag(data, LIST_GEN)
        n = read_int_bare(data)
        args = tuple(read_type(data) for i in range(n))
        expect_tag(data, LITERAL_NONE)  # TODO
        expect_tag(data, LITERAL_NONE)  # TODO
        unbound = UnboundType(name, args)
        read_loc(data, unbound)
        expect_end_tag(data)
        return unbound
    elif tag == types.UNION_TYPE:
        # Read items list
        expect_tag(data, LIST_GEN)
        n = read_int_bare(data)
        items = [read_type(data) for i in range(n)]
        # Read uses_pep604_syntax flag
        uses_pep604_syntax = read_bool(data)
        union = UnionType(items, uses_pep604_syntax=uses_pep604_syntax)
        read_loc(data, union)
        expect_end_tag(data)
        return union
    elif tag == types.LIST_TYPE:
        # Read items list
        expect_tag(data, LIST_GEN)
        n = read_int_bare(data)
        items = [read_type(data) for i in range(n)]
        type_list = TypeList(items)
        read_loc(data, type_list)
        expect_end_tag(data)
        return type_list
    elif tag == types.ELLIPSIS_TYPE:
        # EllipsisType has no attributes
        ellipsis_type = EllipsisType()
        read_loc(data, ellipsis_type)
        expect_end_tag(data)
        return ellipsis_type
    elif tag == types.RAW_EXPRESSION_TYPE:
        type_name = read_str(data)
        value: types.LiteralValue
        if type_name == "builtins.bool":
            value = read_bool(data)
        else:
            assert False  # TODO
        raw_type = RawExpressionType(value, type_name)
        read_loc(data, raw_type)
        expect_end_tag(data)
        return raw_type
    else:
        assert False, tag


def read_block(data: ReadBuffer) -> Block:
    expect_tag(data, nodes.BLOCK)
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    assert n > 0
    a = read_statements(data, n)
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
unary_ops: Final = ["~", "not", "+", "-"]


def read_expression(data: ReadBuffer) -> Expression:
    tag = read_tag(data)
    expr: Expression
    if tag == nodes.CALL_EXPR:
        callee = read_expression(data)
        args = read_expression_list(data)
        # Read argument kinds
        expect_tag(data, LIST_INT)
        n_kinds = read_int_bare(data)
        arg_kinds = [ARG_KINDS[read_int_bare(data)] for _ in range(n_kinds)]
        # Read argument names
        expect_tag(data, LIST_GEN)
        n_names = read_int_bare(data)
        arg_names: list[str | None] = []
        for _ in range(n_names):
            tag = read_tag(data)
            if tag == LITERAL_NONE:
                arg_names.append(None)
            elif tag == LITERAL_STR:
                arg_names.append(read_str_bare(data))
            else:
                assert False, f"Unexpected tag for arg_name: {tag}"
        ce = CallExpr(callee, args, arg_kinds, arg_names)
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
    elif tag == nodes.FLOAT_EXPR:
        expect_tag(data, LITERAL_FLOAT)
        value = read_float_bare(data)
        fe = FloatExpr(value)
        read_loc(data, fe)
        expect_end_tag(data)
        return fe
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
    elif tag == nodes.GENERATOR_EXPR:
        expr = read_generator_expr(data)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.LIST_COMPREHENSION:
        generator = read_generator_expr(data)
        expr = ListComprehension(generator)
        read_loc(data, expr)
        # Also copy location to the inner generator
        generator.line = expr.line
        generator.column = expr.column
        generator.end_line = expr.end_line
        generator.end_column = expr.end_column
        expect_end_tag(data)
        return expr
    elif tag == nodes.SET_COMPREHENSION:
        generator = read_generator_expr(data)
        expr = SetComprehension(generator)
        read_loc(data, expr)
        # Also copy location to the inner generator
        generator.line = expr.line
        generator.column = expr.column
        generator.end_line = expr.end_line
        generator.end_column = expr.end_column
        expect_end_tag(data)
        return expr
    elif tag == nodes.DICT_COMPREHENSION:
        # Read key expression
        key = read_expression(data)
        # Read value expression
        value = read_expression(data)
        # Read number of generators
        n_generators = read_int(data)
        # Read all indices (targets)
        indices = [read_expression(data) for _ in range(n_generators)]
        # Read all sequences (iters)
        sequences = [read_expression(data) for _ in range(n_generators)]
        # Read all condlists (ifs for each generator)
        condlists = [read_expression_list(data) for _ in range(n_generators)]
        # Read all is_async flags
        is_async = [read_bool(data) for _ in range(n_generators)]
        expr = DictionaryComprehension(key, value, indices, sequences, condlists, is_async)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.YIELD_EXPR:
        # Read optional value expression
        has_value = read_bool(data)
        if has_value:
            value = read_expression(data)
        else:
            value = None
        expr = YieldExpr(value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.YIELD_FROM_EXPR:
        # Read value expression (required for yield from)
        value = read_expression(data)
        expr = YieldFromExpr(value)
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
    elif tag == nodes.UNARY_EXPR:
        op = unary_ops[read_int(data)]
        operand = read_expression(data)
        expr = UnaryExpr(op, operand)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.DICT_EXPR:
        # Read keys
        expect_tag(data, LIST_GEN)
        n_keys = read_int_bare(data)
        keys: list[Expression | None] = []
        for _ in range(n_keys):
            has_key = read_bool(data)
            if has_key:
                keys.append(read_expression(data))
            else:
                keys.append(None)
        # Read values
        values = read_expression_list(data)
        # Zip keys and values into items
        items = list(zip(keys, values))
        expr = DictExpr(items)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.COMPLEX_EXPR:
        # Read real part
        expect_tag(data, LITERAL_FLOAT)
        real = read_float_bare(data)
        # Read imaginary part
        expect_tag(data, LITERAL_FLOAT)
        imag = read_float_bare(data)
        # Create complex value
        value = complex(real, imag)
        expr = ComplexExpr(value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.SLICE_EXPR:
        # Read begin_index (lower in Ruff)
        has_begin = read_bool(data)
        begin_index = read_expression(data) if has_begin else None
        # Read end_index (upper in Ruff)
        has_end = read_bool(data)
        end_index = read_expression(data) if has_end else None
        # Read stride (step in Ruff)
        has_stride = read_bool(data)
        stride = read_expression(data) if has_stride else None
        expr = SliceExpr(begin_index, end_index, stride)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.TEMP_NODE:
        # TempNode with no attributes
        temp = TempNode(AnyType(TypeOfAny.special_form), no_rhs=True)
        expect_end_tag(data)
        return temp
    elif tag == nodes.ELLIPSIS_EXPR:
        expr = EllipsisExpr()
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.CONDITIONAL_EXPR:
        # Read if_expr (value when condition is true)
        if_expr = read_expression(data)
        # Read cond (the condition)
        cond = read_expression(data)
        # Read else_expr (value when condition is false)
        else_expr = read_expression(data)
        expr = ConditionalExpr(cond, if_expr, else_expr)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.FSTRING_EXPR:
        # F-strings are converted into nodes representing "".join([...]), to match
        # pre-existing behavior.
        nparts = read_int(data)
        items = []
        for _ in range(nparts):
            b = read_bool(data)
            if b:
                n = read_int(data)
                for i in range(n):
                    items.append(read_fstring_item(data))
            else:
                s = StrExpr(read_str(data))
                read_loc(data, s)
                items.append(s)
        expr = build_fstring_join(data, items)
        expect_end_tag(data)
        return expr
    elif tag == nodes.LAMBDA_EXPR:
        # Read parameters
        arguments, has_ann = read_parameters(data)

        # Read body block
        body = read_block(data)

        # Create lambda expression
        if has_ann:
            typ = CallableType(
                [arg.type_annotation if arg.type_annotation else AnyType(TypeOfAny.unannotated)
                 for arg in arguments],
                [arg.kind for arg in arguments],
                [arg.variable.name for arg in arguments],
                AnyType(TypeOfAny.unannotated),
                _dummy_fallback,
            )
        else:
            typ = None

        expr = LambdaExpr(arguments, body)
        expr.type = typ
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.NAMED_EXPR:
        # Read target expression
        target = read_expression(data)
        # Read value expression
        value = read_expression(data)
        # AssignmentExpr expects target to be a NameExpr
        if not isinstance(target, NameExpr):
            # In case target is not a NameExpr, we need to handle this
            # For now, we'll assert since the grammar should ensure it's a NameExpr
            assert isinstance(target, NameExpr), f"Expected NameExpr for target, got {type(target)}"
        expr = AssignmentExpr(target, value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.STAR_EXPR:
        # Read the wrapped expression
        wrapped_expr = read_expression(data)
        expr = StarExpr(wrapped_expr)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.BYTES_EXPR:
        # Read bytes literal as string
        value = read_str(data)
        expr = BytesExpr(value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.AWAIT_EXPR:
        # Read awaited expression
        value = read_expression(data)
        expr = AwaitExpr(value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    else:
        assert False, tag


def read_fstring_items(data: ReadBuffer) -> Expression:
    items = []
    n = read_int(data)
    items = [read_fstring_item(data) for i in range(n)]
    return build_fstring_join(data, items)


def build_fstring_join(data: ReadBuffer, items: list[Expression]) -> Expression:
    if len(items) == 1:
        expr = items[0]
        read_loc(data, expr)
        return expr
    if all(isinstance(item, StrExpr) for item in items):
        s = "".join([cast(StrExpr, item).value for item in items])
        expr = StrExpr(s)
        read_loc(data, expr)
        return expr
    args = ListExpr(items)
    str_expr = StrExpr("")
    member = MemberExpr(str_expr, "join")
    call = CallExpr(member, [args], [ARG_POS], [None])
    read_loc(data, call)
    set_line_column(args, call)
    set_line_column(str_expr, call)
    set_line_column(member, call)
    return call


def read_fstring_item(data: ReadBuffer) -> Expression:
    t = read_tag(data)
    if t == LITERAL_STR:
        str_expr = StrExpr(read_str_bare(data))
        read_loc(data, str_expr)
        return str_expr
    elif t == nodes.FSTRING_INTERPOLATION:
        expr = read_expression(data)

        # Read conversion flag such as !r
        has_conv = read_bool(data)
        if has_conv:
            c = read_str(data)
            fmt = "{" + c + ":{}}"
        else:
            fmt = "{:{}}"

        # Read format spec such as <30 (which may have nested {...})
        has_spec = read_bool(data)
        if has_spec:
            spec = read_fstring_items(data)
        else:
            spec = StrExpr("")

        member = MemberExpr(StrExpr(fmt), "format")
        set_line_column(member, expr)
        call = CallExpr(member, [expr, spec], [ARG_POS, ARG_POS], [None, None])
        set_line_column(call, expr)
        expect_end_tag(data)
        return call
    else:
        raise ValueError(f"Unexpected tag {t}")


def set_line_column(target: Context, src: Context) -> None:
    target.line = src.line
    target.column = src.column


def read_expression_list(data: ReadBuffer) -> list[Expression]:
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    return [read_expression(data) for i in range(n)]


def read_generator_expr(data: ReadBuffer) -> GeneratorExpr:
    """Helper function to read comprehension data (shared by Generator, ListComp, SetComp)"""
    # Read element expression
    left_expr = read_expression(data)
    # Read number of generators
    n_generators = read_int(data)
    # Read all indices (targets)
    indices = [read_expression(data) for _ in range(n_generators)]
    # Read all sequences (iters)
    sequences = [read_expression(data) for _ in range(n_generators)]
    # Read all condlists (ifs for each generator)
    condlists = [read_expression_list(data) for _ in range(n_generators)]
    # Read all is_async flags
    is_async = [read_bool(data) for _ in range(n_generators)]
    return GeneratorExpr(left_expr, indices, sequences, condlists, is_async)


def read_loc(data: ReadBuffer, node: Context) -> None:
    expect_tag(data, LOCATION)
    line = read_int_bare(data)
    node.line = line
    column = read_int_bare(data)
    node.column = column
    node.end_line = line + read_int_bare(data)
    node.end_column = column + read_int_bare(data)
