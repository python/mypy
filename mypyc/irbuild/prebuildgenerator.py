from mypy.nodes import LDEF, ArgKind, Argument, Block, Expression, ExpressionStmt, ForStmt, GeneratorExpr, IfStmt, NameExpr, Statement, Var, YieldExpr

def gen_generator_expression_body(expr: GeneratorExpr, param_name: str) -> None:
    inner_stmt: Statement = ExpressionStmt(YieldExpr(expr.left_expr))
    for i in reversed(range(len(expr.indices))):
        for cond in reversed(expr.condlists[i]):
            inner_stmt = IfStmt(expr=[cond], body=[Block(body=[inner_stmt])], else_body=None)
        loop_var: Expression
        if i == 0:
            loop_var = NameExpr(param_name)
            loop_var.kind = LDEF
            loop_var.node = Var(param_name)
        else:
            loop_var = expr.sequences[i]
        inner_stmt = ForStmt(index=expr.indices[i], expr=loop_var, body=Block(body=[inner_stmt]), else_body=None)
        inner_stmt.is_async = expr.is_async[i]
    expr.arguments = [
        Argument(
            variable=Var(param_name),
            type_annotation=None,
            initializer=None,
            kind=ArgKind.ARG_POS,
            pos_only=True
        )
    ]
    expr.body = Block(body=[inner_stmt])
