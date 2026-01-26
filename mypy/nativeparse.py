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

import os
from typing import Any, Final, cast

import ast_serialize  # type: ignore[import-untyped, import-not-found, unused-ignore]
from librt.internal import (
    read_float as read_float_bare,
    read_int as read_int_bare,
    read_str as read_str_bare,
)

from mypy import message_registry, nodes, types
from mypy.sharedparse import special_function_elide_names
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
    read_tag,
)
from mypy.nodes import (
    ARG_KINDS,
    ARG_POS,
    MISSING_FALLBACK,
    Argument,
    AssertStmt,
    AssignmentExpr,
    AssignmentStmt,
    AwaitExpr,
    Block,
    BreakStmt,
    BytesExpr,
    CallExpr,
    ClassDef,
    ComparisonExpr,
    ComplexExpr,
    ConditionalExpr,
    Context,
    ContinueStmt,
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
    ImportAll,
    ImportFrom,
    IndexExpr,
    IntExpr,
    LambdaExpr,
    ListComprehension,
    ListExpr,
    MemberExpr,
    MypyFile,
    NameExpr,
    NonlocalDecl,
    OperatorAssignmentStmt,
    OpExpr,
    OverloadedFuncDef,
    PassStmt,
    RaiseStmt,
    ReturnStmt,
    SetComprehension,
    SetExpr,
    SliceExpr,
    StarExpr,
    Statement,
    StrExpr,
    SuperExpr,
    TempNode,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    Var,
    WhileStmt,
    WithStmt,
    YieldExpr,
    YieldFromExpr,
)
from mypy.types import (
    AnyType,
    CallableArgument,
    CallableType,
    EllipsisType,
    Instance,
    RawExpressionType,
    Type,
    TypeList,
    TypeOfAny,
    UnboundType,
    UnionType,
    UnpackType,
)

TypeIgnores = list[tuple[int, list[str]]]


# There is no way to create reasonable fallbacks at this stage,
# they must be patched later.
_dummy_fallback: Final = Instance(MISSING_FALLBACK, [], -1)


class State:
    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []

    def add_error(self, message: str, line: int, column: int) -> None:
        """Report an error at a specific location."""
        self.errors.append({"line": line, "column": column, "message": message})


def expect_end_tag(data: ReadBuffer) -> None:
    assert read_tag(data) == END_TAG


def expect_tag(data: ReadBuffer, tag: Tag) -> None:
    assert read_tag(data) == tag


def native_parse(
    filename: str, skip_function_bodies: bool = False
) -> tuple[MypyFile, list[dict[str, Any]], TypeIgnores]:
    # If the path is a directory, return empty AST (matching fastparse behavior)
    # This can happen for packages that only contain .pyc files without source
    if os.path.isdir(filename):
        node = MypyFile([], [])
        node.path = filename
        return node, [], []

    b, errors, ignores = parse_to_binary_ast(filename, skip_function_bodies)
    data = ReadBuffer(b)
    n = read_int(data)
    state = State()
    defs = read_statements(state, data, n)
    node = MypyFile(defs, [])
    node.path = filename
    # Merge deserialization errors with parsing errors
    all_errors = errors + state.errors
    return node, all_errors, ignores


def read_statements(state: State, data: ReadBuffer, n: int) -> list[Statement]:
    defs: list[Statement] = []
    prev_func = False
    prev_name = ""
    for _ in range(n):
        stmt = read_statement(state, data)
        if isinstance(stmt, (FuncDef, Decorator)):
            if prev_func and stmt.name == prev_name:
                # Merge into overloaded function definition
                prev = defs[-1]
                if isinstance(prev, OverloadedFuncDef):
                    prev.items.append(stmt)
                    prev.unanalyzed_items.append(stmt)
                else:
                    assert isinstance(prev, (FuncDef, Decorator))
                    defs[-1] = OverloadedFuncDef([prev, stmt])
            else:
                defs.append(stmt)
                prev_name = stmt.name
            prev_func = True
        else:
            defs.append(stmt)
            prev_func = False
    return defs


def parse_to_binary_ast(
    filename: str, skip_function_bodies: bool = False
) -> tuple[bytes, list[dict[str, Any]], TypeIgnores]:
    return ast_serialize.parse(filename, skip_function_bodies)  # type: ignore[no-any-return]


def read_statement(state: State, data: ReadBuffer) -> Statement:
    tag = read_tag(data)
    stmt: Statement
    if tag == nodes.FUNC_DEF_STMT:
        return read_func_def(state, data)
    elif tag == nodes.DECORATOR:
        expect_tag(data, LIST_GEN)
        n_decorators = read_int_bare(data)
        decorators = [read_expression(state, data) for i in range(n_decorators)]
        line = read_int(data)
        column = read_int(data)
        fdef = read_statement(state, data)
        assert isinstance(fdef, FuncDef)
        fdef.is_decorated = True
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
        es = ExpressionStmt(read_expression(state, data))
        es.line = es.expr.line
        es.column = es.expr.column
        es.end_line = es.expr.end_line
        es.end_column = es.expr.end_column
        expect_end_tag(data)
        return es
    elif tag == nodes.ASSIGNMENT_STMT:
        lvalues = read_expression_list(state, data)
        rvalue = read_expression(state, data)
        # Read type annotation
        has_type = read_bool(data)
        if has_type:
            type_annotation = read_type(state, data)
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
        lvalue = read_expression(state, data)
        # Read rvalue (value)
        rvalue = read_expression(state, data)
        stmt = OperatorAssignmentStmt(op, lvalue, rvalue)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.IF_STMT:
        # Read the main if condition and body
        expr = read_expression(state, data)
        body = read_block(state, data)

        # Read elif clauses
        num_elif = read_int(data)
        elif_exprs = []
        elif_bodies = []
        for i in range(num_elif):
            elif_exprs.append(read_expression(state, data))
            elif_bodies.append(read_block(state, data))

        # Read else clause
        has_else = read_bool(data)
        if has_else:
            else_body = read_block(state, data)
        else:
            else_body = None

        # Normalize elif into nested if/else statements
        # Build from the bottom up, starting with the final else body
        current_else = else_body

        # Process elif clauses in reverse order
        for i in range(len(elif_exprs) - 1, -1, -1):
            # Create an IfStmt for this elif
            elif_stmt = IfStmt([elif_exprs[i]], [elif_bodies[i]], current_else)
            # Set location from the elif expression
            elif_stmt.line = elif_exprs[i].line
            elif_stmt.column = elif_exprs[i].column
            # Set end location based on what follows
            if current_else is not None:
                elif_stmt.end_line = current_else.end_line
                elif_stmt.end_column = current_else.end_column
            else:
                elif_stmt.end_line = elif_bodies[i].end_line
                elif_stmt.end_column = elif_bodies[i].end_column

            # Wrap in a Block to become the else clause for the outer if
            current_else = Block([elif_stmt])
            current_else.line = elif_stmt.line
            current_else.column = elif_stmt.column
            current_else.end_line = elif_stmt.end_line
            current_else.end_column = elif_stmt.end_column

        # Create the main if statement
        if_stmt = IfStmt([expr], [body], current_else)
        read_loc(data, if_stmt)
        expect_end_tag(data)
        return if_stmt
    elif tag == nodes.RETURN_STMT:
        has_value = read_bool(data)
        if has_value:
            value = read_expression(state, data)
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
            exc = read_expression(state, data)
        else:
            exc = None
        # Read from expression (optional)
        has_from = read_bool(data)
        if has_from:
            from_expr = read_expression(state, data)
        else:
            from_expr = None
        stmt = RaiseStmt(exc, from_expr)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.ASSERT_STMT:
        # Read test expression
        test = read_expression(state, data)
        # Read optional message expression
        has_msg = read_bool(data)
        if has_msg:
            msg = read_expression(state, data)
        else:
            msg = None
        stmt = AssertStmt(test, msg)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.WHILE_STMT:
        expr = read_expression(state, data)
        body = read_block(state, data)
        else_body = read_optional_block(state, data)
        stmt = WhileStmt(expr, body, else_body)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.FOR_STMT:
        # Read index (target)
        index = read_expression(state, data)
        # Read iterator expression
        expr = read_expression(state, data)
        # Read body
        body = read_block(state, data)
        # Read else clause
        else_body = read_optional_block(state, data)
        # Read is_async flag
        is_async = read_bool(data)
        stmt = ForStmt(index, expr, body, else_body)
        stmt.is_async = is_async
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
            context_expr = read_expression(state, data)
            expr_list.append(context_expr)
            # Read optional target
            has_target = read_bool(data)
            if has_target:
                target = read_expression(state, data)
                target_list.append(target)
            else:
                target_list.append(None)
        # Read body
        body = read_block(state, data)
        # Read is_async flag
        is_async = read_bool(data)
        stmt = WithStmt(expr_list, target_list, body)
        stmt.is_async = is_async
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
    elif tag == nodes.IMPORT_ALL:
        # Read module name (empty string for "from . import *")
        module_id = read_str(data)

        # Read relative import level
        relative = read_int(data)

        stmt = ImportAll(module_id, relative)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.CLASS_DEF:
        return read_class_def(state, data)
    elif tag == nodes.TRY_STMT:
        return read_try_stmt(state, data)
    elif tag == nodes.DEL_STMT:
        # Read the target expression
        expr = read_expression(state, data)
        stmt = DelStmt(expr)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.GLOBAL_DECL:
        # Read number of names
        n = read_int(data)
        decl_names = []
        for _ in range(n):
            decl_names.append(read_str(data))
        stmt = GlobalDecl(decl_names)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    elif tag == nodes.NONLOCAL_DECL:
        # Read number of names
        n = read_int(data)
        decl_names = []
        for _ in range(n):
            decl_names.append(read_str(data))
        stmt = NonlocalDecl(decl_names)
        read_loc(data, stmt)
        expect_end_tag(data)
        return stmt
    else:
        assert False, tag


def read_parameters(state: State, data: ReadBuffer) -> tuple[list[Argument], bool]:
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
            ann = read_type(state, data)
            has_ann = True
        else:
            ann = None
        # Read default value
        has_default = read_bool(data)
        if has_default:
            default = read_expression(state, data)
        else:
            default = None
        pos_only = read_bool(data)

        var = Var(arg_name, ann)
        var.is_inferred = False
        arg = Argument(var, ann, default, arg_kind, pos_only)
        read_loc(data, arg)
        var.line = arg.line
        var.column = arg.column
        var.end_line = arg.end_line
        var.end_column = arg.end_column
        arguments.append(arg)

    return arguments, has_ann


def read_func_def(state: State, data: ReadBuffer) -> FuncDef:
    # Function name
    name = read_str(data)

    # Parameters
    arguments, has_ann = read_parameters(state, data)

    if special_function_elide_names(name):
        for arg in arguments:
            arg.pos_only = True

    body = read_block(state, data)

    is_async = read_bool(data)

    # TODO: type_params
    has_type_params = read_bool(data)
    assert not has_type_params, "Type params not yet supported"

    # TODO: Return type annotation
    has_return_type = read_bool(data)
    if has_return_type:
        return_type = read_type(state, data)
        has_ann = True
    else:
        return_type = None

    if has_ann:
        typ = CallableType(
            [
                arg.type_annotation if arg.type_annotation else AnyType(TypeOfAny.unannotated)
                for arg in arguments
            ],
            [arg.kind for arg in arguments],
            [None if arg.pos_only else arg.variable.name for arg in arguments],
            return_type if return_type else AnyType(TypeOfAny.unannotated),
            _dummy_fallback,
        )
    else:
        typ = None

    func_def = FuncDef(name, arguments, body, typ=typ)
    if typ:
        # TODO: This seems wasteful, can we avoid it?
        func_def.unanalyzed_type = typ.copy_modified()

        typ.definition = func_def
        typ.line = func_def.line
    if is_async:
        func_def.is_coroutine = True
    read_loc(data, func_def)
    expect_end_tag(data)
    return func_def


def read_class_def(state: State, data: ReadBuffer) -> ClassDef:
    # Class name
    name = read_str(data)

    # Body
    body = read_block(state, data)

    # Base classes
    base_type_exprs = read_expression_list(state, data)

    # Decorators
    expect_tag(data, LIST_GEN)
    n_decorators = read_int_bare(data)
    decorators = [read_expression(state, data) for _ in range(n_decorators)]

    # TODO: Type parameters (skip for now)
    has_type_params = read_bool(data)
    assert not has_type_params, "Type parameters not yet supported"

    # Keywords (all keyword arguments including metaclass)
    expect_tag(data, DICT_STR_GEN)
    n_keywords = read_int_bare(data)
    keywords = []
    for _ in range(n_keywords):
        key = read_str(data)
        value = read_expression(state, data)
        keywords.append((key, value))

    # Extract metaclass from keywords if present
    metaclass = dict(keywords).get("metaclass") if keywords else None
    # Remove metaclass from keywords since it's passed as a separate field
    filtered_keywords = [(k, v) for k, v in keywords if k != "metaclass"] if keywords else None

    class_def = ClassDef(
        name,
        body,
        base_type_exprs=base_type_exprs if base_type_exprs else None,
        metaclass=metaclass,
        keywords=filtered_keywords,
    )
    class_def.decorators = decorators
    read_loc(data, class_def)
    expect_end_tag(data)
    return class_def


def read_try_stmt(state: State, data: ReadBuffer) -> TryStmt:
    # Read try body
    body = read_block(state, data)

    # Read number of except handlers
    num_handlers = read_int(data)

    # Read exception types for each handler
    types_list: list[Expression | None] = []
    for _ in range(num_handlers):
        has_type = read_bool(data)
        if has_type:
            exc_type = read_expression(state, data)
            types_list.append(exc_type)
        else:
            types_list.append(None)

    # Read variable names for each handler
    vars_list: list[NameExpr | None] = []
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
        handler_body = read_block(state, data)
        handlers.append(handler_body)

    # Read else body (optional)
    has_else = read_bool(data)
    if has_else:
        else_body = read_block(state, data)
    else:
        else_body = None

    # Read finally body (optional)
    has_finally = read_bool(data)
    if has_finally:
        finally_body = read_block(state, data)
    else:
        finally_body = None

    stmt = TryStmt(body, vars_list, types_list, handlers, else_body, finally_body)
    read_loc(data, stmt)
    expect_end_tag(data)
    return stmt


def read_type(state: State, data: ReadBuffer) -> Type:
    tag = read_tag(data)
    if tag == types.UNBOUND_TYPE:
        name = read_str(data)
        expect_tag(data, LIST_GEN)
        n = read_int_bare(data)
        args = tuple(read_type(state, data) for i in range(n))
        # Read optional original_str_expr
        t = read_tag(data)
        if t == LITERAL_NONE:
            original_str_expr = None
        elif t == LITERAL_STR:
            original_str_expr = read_str_bare(data)
        else:
            assert False, f"Unexpected tag for original_str_expr: {t}"
        # Read optional original_str_fallback
        t = read_tag(data)
        if t == LITERAL_NONE:
            original_str_fallback = None
        elif t == LITERAL_STR:
            original_str_fallback = read_str_bare(data)
        else:
            assert False, f"Unexpected tag for original_str_fallback: {t}"
        unbound = UnboundType(
            name,
            args,
            original_str_expr=original_str_expr,
            original_str_fallback=original_str_fallback,
        )
        read_loc(data, unbound)
        expect_end_tag(data)
        return unbound
    elif tag == types.UNION_TYPE:
        # Read items list
        expect_tag(data, LIST_GEN)
        n = read_int_bare(data)
        items = [read_type(state, data) for i in range(n)]
        # Read uses_pep604_syntax flag
        uses_pep604_syntax = read_bool(data)
        # Read optional original_str_expr
        t = read_tag(data)
        if t == LITERAL_NONE:
            original_str_expr = None
        elif t == LITERAL_STR:
            original_str_expr = read_str_bare(data)
        else:
            assert False, f"Unexpected tag for original_str_expr: {t}"
        # Read optional original_str_fallback
        t = read_tag(data)
        if t == LITERAL_NONE:
            original_str_fallback = None
        elif t == LITERAL_STR:
            original_str_fallback = read_str_bare(data)
        else:
            assert False, f"Unexpected tag for original_str_fallback: {t}"
        union = UnionType(items, uses_pep604_syntax=uses_pep604_syntax)
        union.original_str_expr = original_str_expr
        union.original_str_fallback = original_str_fallback
        read_loc(data, union)
        expect_end_tag(data)
        return union
    elif tag == types.LIST_TYPE:
        # Read items list
        expect_tag(data, LIST_GEN)
        n = read_int_bare(data)
        items = [read_type(state, data) for i in range(n)]
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
        value: types.LiteralValue | str | None
        if type_name == "builtins.bool":
            value = read_bool(data)
        elif type_name == "builtins.int":
            value = read_int(data)
        elif type_name == "builtins.str":
            value = read_str(data)
        elif type_name == "builtins.bytes":
            # Bytes literals are serialized as escaped strings
            value = read_str(data)
        elif type_name == "typing.Any":
            # Invalid type - read None value
            tag = read_tag(data)
            assert tag == types.LITERAL_NONE, f"Expected LITERAL_NONE for invalid type, got {tag}"
            value = None
        else:
            assert False, f"Unsupported RawExpressionType: {type_name}"
        raw_type = RawExpressionType(value, type_name)
        read_loc(data, raw_type)
        expect_end_tag(data)
        return raw_type
    elif tag == types.UNPACK_TYPE:
        inner_type = read_type(state, data)
        unpack = UnpackType(inner_type)
        read_loc(data, unpack)
        expect_end_tag(data)
        return unpack
    elif tag == types.CALL_TYPE:
        return read_call_type(state, data)
    else:
        assert False, tag


def read_block(state: State, data: ReadBuffer) -> Block:
    expect_tag(data, nodes.BLOCK)
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    if n == 0:
        # Empty block - read explicit location
        b = Block([])
        read_loc(data, b)
        expect_end_tag(data)
        return b
    else:
        # Non-empty block - read statements and set location from them
        a = read_statements(state, data, n)
        expect_end_tag(data)
        b = Block(a)
        b.line = a[0].line
        b.column = a[0].column
        b.end_line = a[-1].end_line
        b.end_column = a[-1].end_column
        return b


def read_optional_block(state: State, data: ReadBuffer) -> Block | None:
    expect_tag(data, nodes.BLOCK)
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    if n == 0:
        b = None
    else:
        a = [read_statement(state, data) for i in range(n)]
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


def read_expression(state: State, data: ReadBuffer) -> Expression:
    tag = read_tag(data)
    expr: Expression
    if tag == nodes.CALL_EXPR:
        callee = read_expression(state, data)
        args = read_expression_list(state, data)
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
        e = read_expression(state, data)
        attr = read_str(data)
        m = MemberExpr(e, attr)
        # Check if this is a super() call - if so, convert to SuperExpr
        if isinstance(e, CallExpr) and isinstance(e.callee, NameExpr) and e.callee.name == "super":
            result: Expression = SuperExpr(attr, e)
        else:
            result = m
        read_loc(data, result)
        expect_end_tag(data)
        return result
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
        items = read_expression_list(state, data)
        expr = ListExpr(items)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.TUPLE_EXPR:
        items = read_expression_list(state, data)
        t = TupleExpr(items)
        read_loc(data, t)
        expect_end_tag(data)
        return t
    elif tag == nodes.SET_EXPR:
        items = read_expression_list(state, data)
        expr = SetExpr(items)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.GENERATOR_EXPR:
        expr = read_generator_expr(state, data)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.LIST_COMPREHENSION:
        generator = read_generator_expr(state, data)
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
        generator = read_generator_expr(state, data)
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
        key = read_expression(state, data)
        # Read value expression
        value = read_expression(state, data)
        # Read number of generators
        n_generators = read_int(data)
        # Read all indices (targets)
        indices = [read_expression(state, data) for _ in range(n_generators)]
        # Read all sequences (iters)
        sequences = [read_expression(state, data) for _ in range(n_generators)]
        # Read all condlists (ifs for each generator)
        condlists = [read_expression_list(state, data) for _ in range(n_generators)]
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
            value = read_expression(state, data)
        else:
            value = None
        expr = YieldExpr(value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.YIELD_FROM_EXPR:
        # Read value expression (required for yield from)
        value = read_expression(state, data)
        expr = YieldFromExpr(value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.OP_EXPR:
        op = bin_ops[read_int(data)]
        left = read_expression(state, data)
        right = read_expression(state, data)
        o = OpExpr(op, left, right)
        # TODO: Store these explicitly?
        o.line = left.line
        o.column = left.column
        o.end_line = right.end_line
        o.end_column = right.end_column
        expect_end_tag(data)
        return o
    elif tag == nodes.INDEX_EXPR:
        base = read_expression(state, data)
        index = read_expression(state, data)
        expr = IndexExpr(base, index)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.BOOL_OP_EXPR:
        op = bool_ops[read_int(data)]
        values = read_expression_list(state, data)
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
        left = read_expression(state, data)
        # Read operators list
        expect_tag(data, LIST_INT)
        n_ops = read_int_bare(data)
        ops = [cmp_ops[read_int_bare(data)] for _ in range(n_ops)]
        # Read comparators list
        comparators = read_expression_list(state, data)
        assert len(ops) == len(comparators)
        expr = ComparisonExpr(ops, [left] + comparators)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.UNARY_EXPR:
        op = unary_ops[read_int(data)]
        operand = read_expression(state, data)
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
                keys.append(read_expression(state, data))
            else:
                keys.append(None)
        # Read values
        values = read_expression_list(state, data)
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
        begin_index = read_expression(state, data) if has_begin else None
        # Read end_index (upper in Ruff)
        has_end = read_bool(data)
        end_index = read_expression(state, data) if has_end else None
        # Read stride (step in Ruff)
        has_stride = read_bool(data)
        stride = read_expression(state, data) if has_stride else None
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
        if_expr = read_expression(state, data)
        # Read cond (the condition)
        cond = read_expression(state, data)
        # Read else_expr (value when condition is false)
        else_expr = read_expression(state, data)
        expr = ConditionalExpr(cond, if_expr, else_expr)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.FSTRING_EXPR:
        # F-strings are converted into nodes representing "".join([...]), to match
        # pre-existing behavior.
        nparts = read_int(data)
        fitems = []
        for _ in range(nparts):
            b = read_bool(data)
            if b:
                n = read_int(data)
                for i in range(n):
                    fitems.append(read_fstring_item(state, data))
            else:
                s = StrExpr(read_str(data))
                read_loc(data, s)
                fitems.append(s)
        expr = build_fstring_join(state, data, fitems)
        expect_end_tag(data)
        return expr
    elif tag == nodes.LAMBDA_EXPR:
        # Read parameters
        arguments, has_ann = read_parameters(state, data)

        # Read body block
        body = read_block(state, data)

        # Create lambda expression
        if has_ann:
            typ = CallableType(
                [
                    arg.type_annotation if arg.type_annotation else AnyType(TypeOfAny.unannotated)
                    for arg in arguments
                ],
                [arg.kind for arg in arguments],
                [None if arg.pos_only else arg.variable.name for arg in arguments],
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
        target = read_expression(state, data)
        # Read value expression
        value = read_expression(state, data)
        # AssignmentExpr expects target to be a NameExpr
        if not isinstance(target, NameExpr):
            # In case target is not a NameExpr, we need to handle this
            # For now, we'll assert since the grammar should ensure it's a NameExpr
            assert isinstance(
                target, NameExpr
            ), f"Expected NameExpr for target, got {type(target)}"
        expr = AssignmentExpr(target, value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.STAR_EXPR:
        # Read the wrapped expression
        wrapped_expr = read_expression(state, data)
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
        value = read_expression(state, data)
        expr = AwaitExpr(value)
        read_loc(data, expr)
        expect_end_tag(data)
        return expr
    elif tag == nodes.BIG_INT_EXPR:
        strval = read_str(data)
        ie = IntExpr(int(strval))
        read_loc(data, ie)
        expect_end_tag(data)
        return ie
    else:
        assert False, tag


def read_fstring_items(state: State, data: ReadBuffer) -> Expression:
    items = []
    n = read_int(data)
    items = [read_fstring_item(state, data) for i in range(n)]
    return build_fstring_join(state, data, items)


def build_fstring_join(state: State, data: ReadBuffer, items: list[Expression]) -> Expression:
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


def read_fstring_item(state: State, data: ReadBuffer) -> Expression:
    t = read_tag(data)
    if t == LITERAL_STR:
        str_expr = StrExpr(read_str_bare(data))
        read_loc(data, str_expr)
        return str_expr
    elif t == nodes.FSTRING_INTERPOLATION:
        expr = read_expression(state, data)

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
            spec = read_fstring_items(state, data)
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


def read_expression_list(state: State, data: ReadBuffer) -> list[Expression]:
    expect_tag(data, LIST_GEN)
    n = read_int_bare(data)
    return [read_expression(state, data) for i in range(n)]


def read_generator_expr(state: State, data: ReadBuffer) -> GeneratorExpr:
    """Helper function to read comprehension data (shared by Generator, ListComp, SetComp)"""
    # Read element expression
    left_expr = read_expression(state, data)
    # Read number of generators
    n_generators = read_int(data)
    # Read all indices (targets)
    indices = [read_expression(state, data) for _ in range(n_generators)]
    # Read all sequences (iters)
    sequences = [read_expression(state, data) for _ in range(n_generators)]
    # Read all condlists (ifs for each generator)
    condlists = [read_expression_list(state, data) for _ in range(n_generators)]
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


def stringify_type_name(typ: Type) -> str | None:
    """Extract qualified name from a type (for Arg constructor detection)."""
    if isinstance(typ, UnboundType):
        return typ.name
    return None


def extract_arg_name(typ: Type) -> str | None:
    """Extract argument name from a type (for Arg name parameter)."""
    if isinstance(typ, RawExpressionType) and typ.base_type_name == "builtins.str":
        return typ.literal_value  # type: ignore[return-value]
    elif isinstance(typ, UnboundType):
        # String literals in type context are parsed as UnboundType (forward references)
        # For Arg names, these are typically simple names without dots
        if typ.name == "None":
            return None
        # Return the name as-is (it's the argument name)
        return typ.name
    return None  # Invalid, but let validation handle it


def read_call_type(state: State, data: ReadBuffer) -> Type:
    """Read Call in type context - check if it's an Arg/DefaultArg/VarArg/KwArg constructor.

    This performs validation and error reporting similar to mypy/fastparse.py.
    """
    # Read callee
    callee_type = read_type(state, data)

    # Read positional arguments
    expect_tag(data, LIST_GEN)
    n_args = read_int_bare(data)
    args = [read_type(state, data) for _ in range(n_args)]

    # Read keyword arguments
    expect_tag(data, LIST_GEN)
    n_kwargs = read_int_bare(data)
    kwargs = []
    for _ in range(n_kwargs):
        tag_kw = read_tag(data)
        if tag_kw == LITERAL_NONE:
            kw_name = None
        elif tag_kw == LITERAL_STR:
            kw_name = read_str_bare(data)
        else:
            assert False, f"Unexpected tag for keyword name: {tag_kw}"
        kw_value = read_type(state, data)
        kwargs.append((kw_name, kw_value))

    # Try to detect Arg/DefaultArg/VarArg/KwArg pattern
    constructor = stringify_type_name(callee_type)

    # We'll read location before processing errors so we can report them correctly
    invalid = AnyType(TypeOfAny.from_error)
    read_loc(data, invalid)
    expect_end_tag(data)

    if not constructor:
        # ARG_CONSTRUCTOR_NAME_EXPECTED
        state.add_error(
            message_registry.ARG_CONSTRUCTOR_NAME_EXPECTED.value, invalid.line, invalid.column
        )
        return invalid

    # Extract type and name from arguments
    name: str | None = None
    name_set_from_positional = False
    default_type = AnyType(TypeOfAny.special_form)
    typ: Type = default_type
    typ_set_from_positional = False

    # Process positional arguments
    for i, arg in enumerate(args):
        if i == 0:
            typ = arg
            typ_set_from_positional = True
        elif i == 1:
            name = extract_arg_name(arg)
            name_set_from_positional = True
        else:
            # ARG_CONSTRUCTOR_TOO_MANY_ARGS
            state.add_error(
                message_registry.ARG_CONSTRUCTOR_TOO_MANY_ARGS.value, invalid.line, invalid.column
            )

    # Process keyword arguments
    for kw_name, kw_value in kwargs:
        if kw_name == "name":
            # MULTIPLE_VALUES_FOR_NAME_KWARG
            if name is not None and name_set_from_positional:
                state.add_error(
                    message_registry.MULTIPLE_VALUES_FOR_NAME_KWARG.format(constructor).value,
                    invalid.line,
                    invalid.column,
                )
            name = extract_arg_name(kw_value)
        elif kw_name == "type":
            # MULTIPLE_VALUES_FOR_TYPE_KWARG
            if typ is not default_type and typ_set_from_positional:
                state.add_error(
                    message_registry.MULTIPLE_VALUES_FOR_TYPE_KWARG.format(constructor).value,
                    invalid.line,
                    invalid.column,
                )
            typ = kw_value
        else:
            # ARG_CONSTRUCTOR_UNEXPECTED_ARG
            state.add_error(
                message_registry.ARG_CONSTRUCTOR_UNEXPECTED_ARG.format(kw_name).value,
                invalid.line,
                invalid.column,
            )

    # Create CallableArgument
    call_arg = CallableArgument(typ, name, constructor)
    call_arg.line = invalid.line
    call_arg.column = invalid.column
    call_arg.end_line = invalid.end_line
    call_arg.end_column = invalid.end_column
    return call_arg
