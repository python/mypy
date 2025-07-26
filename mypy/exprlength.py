"""Static expression length analysis utilities for mypy.

Provides helpers for statically determining the length of expressions,
when possible.
"""

from typing import List, Optional, Tuple

from mypy.nodes import (
    ARG_POS,
    AssignmentStmt,
    Block,
    BytesExpr,
    CallExpr,
    ClassDef,
    DictExpr,
    Expression,
    ExpressionStmt,
    ForStmt,
    FuncDef,
    GeneratorExpr,
    GlobalDecl,
    IfStmt,
    ListComprehension,
    ListExpr,
    MemberExpr,
    NameExpr,
    NonlocalDecl,
    OverloadedFuncDef,
    SetExpr,
    StarExpr,
    StrExpr,
    TryStmt,
    TupleExpr,
    WhileStmt,
    WithStmt,
    is_IntExpr_list,
)


def get_static_expr_length(expr: Expression, context: Optional[Block] = None) -> Optional[int]:
    """Try to statically determine the length of an expression.

    Returns the length if it can be determined at type-check time,
    otherwise returns None.

    If context is provided, will attempt to resolve NameExpr/Var assignments.
    """
    # NOTE: currently only used for indexing but could be extended to flag
    # fun things like list.pop or to allow len([1, 2, 3]) to type check as Literal[3]

    # List, tuple literals (with possible star expressions)
    if isinstance(expr, (ListExpr, TupleExpr)):
        stars = [get_static_expr_length(i, context) for i in expr.items if isinstance(i, StarExpr)]
        if None not in stars:
            # if there are no star expressions, or we know the
            # length of them, we know the length of the expression
            other = sum(not isinstance(i, StarExpr) for i in expr.items)
            return other + sum(star for star in stars if star is not None)
    elif isinstance(expr, SetExpr):
        # TODO: set expressions are more complicated, you need to know the
        # actual value of each item in order to confidently state its length
        pass
    elif isinstance(expr, DictExpr):
        # TODO: same as with sets, dicts are more complicated since you need
        # to know the specific value of each key, and ensure they don't collide
        pass
    # String or bytes literal
    elif isinstance(expr, (StrExpr, BytesExpr)):
        return len(expr.value)
    elif isinstance(expr, ListComprehension):
        # If the generator's length is known, the list's length is known
        return get_static_expr_length(expr.generator, context)
    elif isinstance(expr, GeneratorExpr):
        # If there is only one sequence and no conditions, and we know
        # the sequence length, we know the max number of items yielded
        # from the genexp and can pass that info forward
        if len(expr.sequences) == 1 and len(expr.condlists) == 0:
            return get_static_expr_length(expr.sequences[0], context)
    # range() with constant arguments
    elif isinstance(expr, CallExpr):
        callee = expr.callee
        if isinstance(callee, NameExpr) and callee.fullname == "builtins.range":
            args = expr.args
            if is_IntExpr_list(args) and all(kind == ARG_POS for kind in expr.arg_kinds):
                if len(args) == 1:
                    # range(stop)
                    stop = args[0].value
                    return max(0, stop)
                elif len(args) == 2:
                    # range(start, stop)
                    start, stop = args[0].value, args[1].value
                    return max(0, stop - start)
                elif len(args) == 3:
                    # range(start, stop, step)
                    start, stop, step = args[0].value, args[1].value, args[2].value
                    if step == 0:
                        return None
                    n = (stop - start + (step - (1 if step > 0 else -1))) // step
                    return max(0, n)
    # We have a big spaghetti monster of special case logic to resolve name expressions
    elif isinstance(expr, NameExpr):
        # Try to resolve the value of a local variable if possible
        if context is None:
            # Cannot resolve without context
            return None
        assignments: List[Tuple[AssignmentStmt, int]] = []

        # Iterate thru all statements in the block
        for stmt in context.body:
            if isinstance(
                stmt,
                (
                    IfStmt,
                    ForStmt,
                    WhileStmt,
                    TryStmt,
                    WithStmt,
                    FuncDef,
                    OverloadedFuncDef,
                    ClassDef,
                ),
            ):
                # These statements complicate things and render the whole block useless
                return None
            elif isinstance(stmt, (GlobalDecl, NonlocalDecl)) and expr.name in stmt.names:
                # We cannot assure the value of a global or nonlocal
                return None
            elif stmt.line >= expr.line:
                # We can stop our analysis at the line where the name is used
                break
            # Check for any assignments
            elif isinstance(stmt, AssignmentStmt):
                # First, exit if any assignment has a rhs expression that
                # could mutate the name
                # TODO Write logic to recursively unwrap statements to see
                # if any internal statements mess with our var

                # Iterate thru lvalues in the assignment
                for idx, lval in enumerate(stmt.lvalues):
                    # Check if any of them matches our variable
                    if isinstance(lval, NameExpr) and lval.name == expr.name:
                        assignments.append((stmt, idx))
            elif isinstance(stmt, ExpressionStmt):
                if isinstance(stmt.expr, CallExpr):
                    callee = stmt.expr.callee
                    for arg in stmt.expr.args:
                        if isinstance(arg, NameExpr) and arg.name == expr.name:
                            # our var was passed to a function as an input,
                            # it could be mutated now
                            return None
                    if (
                        isinstance(callee, MemberExpr)
                        and isinstance(callee.expr, NameExpr)
                        and callee.expr.name == expr.name
                    ):
                        return None

        # For now, we only attempt to resolve the length
        # when the name was only ever assigned to once
        if len(assignments) != 1:
            return None
        stmt, idx = assignments[0]
        rvalue = stmt.rvalue
        # If single lvalue, just use rvalue
        if len(stmt.lvalues) == 1:
            return get_static_expr_length(rvalue, context)
        # If multiple lvalues, try to extract the corresponding value
        elif isinstance(rvalue, (TupleExpr, ListExpr)):
            if len(rvalue.items) == len(stmt.lvalues):
                return get_static_expr_length(rvalue.items[idx], context)
        # Otherwise, cannot determine
    # Could add more cases (e.g. dicts, sets) in the future
    return None
