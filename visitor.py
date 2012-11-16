import nodes


class NodeVisitor<T>:
    """Empty base class for parse tree node visitors.

    The T type argument specifies the return type of the visit
    methods. As all methods defined here return None by default,
    subclasses do not always need to override all the methods.
    """
    
    # Top-level structures
    
    T visit_mypy_file(self, nodes.MypyFile o):
        pass
    
    T visit_import(self, nodes.Import o):
        pass
    T visit_import_from(self, nodes.ImportFrom o):
        pass
    T visit_import_all(self, nodes.ImportAll o):
        pass
    
    # Definitions
    
    T visit_func_def(self, nodes.FuncDef o):
        pass
    T visit_overloaded_func_def(self, nodes.OverloadedFuncDef o):
        pass
    T visit_type_def(self, nodes.TypeDef o):
        pass
    T visit_var_def(self, nodes.VarDef o):
        pass
    T visit_global_decl(self, nodes.GlobalDecl o):
        pass
    T visit_decorator(self, nodes.Decorator o):
        pass
    
    T visit_var(self, nodes.Var o):
        pass
    
    T visit_annotation(self, nodes.Annotation o):
        pass
    
    # Statements
    
    T visit_block(self, nodes.Block o):
        pass
    
    T visit_expression_stmt(self, nodes.ExpressionStmt o):
        pass
    T visit_assignment_stmt(self, nodes.AssignmentStmt o):
        pass
    T visit_operator_assignment_stmt(self, nodes.OperatorAssignmentStmt o):
        pass
    T visit_while_stmt(self, nodes.WhileStmt o):
        pass
    T visit_for_stmt(self, nodes.ForStmt o):
        pass
    T visit_return_stmt(self, nodes.ReturnStmt o):
        pass
    T visit_assert_stmt(self, nodes.AssertStmt o):
        pass
    T visit_yield_stmt(self, nodes.YieldStmt o):
        pass
    T visit_del_stmt(self, nodes.DelStmt o):
        pass
    T visit_if_stmt(self, nodes.IfStmt o):
        pass
    T visit_break_stmt(self, nodes.BreakStmt o):
        pass
    T visit_continue_stmt(self, nodes.ContinueStmt o):
        pass
    T visit_pass_stmt(self, nodes.PassStmt o):
        pass
    T visit_raise_stmt(self, nodes.RaiseStmt o):
        pass
    T visit_try_stmt(self, nodes.TryStmt o):
        pass
    T visit_with_stmt(self, nodes.WithStmt o):
        pass
    
    # Expressions
    
    T visit_int_expr(self, nodes.IntExpr o):
        pass
    T visit_str_expr(self, nodes.StrExpr o):
        pass
    T visit_float_expr(self, nodes.FloatExpr o):
        pass
    T visit_paren_expr(self, nodes.ParenExpr o):
        pass
    T visit_name_expr(self, nodes.NameExpr o):
        pass
    T visit_member_expr(self, nodes.MemberExpr o):
        pass
    T visit_call_expr(self, nodes.CallExpr o):
        pass
    T visit_op_expr(self, nodes.OpExpr o):
        pass
    T visit_cast_expr(self, nodes.CastExpr o):
        pass
    T visit_super_expr(self, nodes.SuperExpr o):
        pass
    T visit_unary_expr(self, nodes.UnaryExpr o):
        pass
    T visit_list_expr(self, nodes.ListExpr o):
        pass
    T visit_dict_expr(self, nodes.DictExpr o):
        pass
    T visit_tuple_expr(self, nodes.TupleExpr o):
        pass
    T visit_set_expr(self, nodes.SetExpr o):
        pass
    T visit_index_expr(self, nodes.IndexExpr o):
        pass
    T visit_type_application(self, nodes.TypeApplication o):
        pass
    T visit_func_expr(self, nodes.FuncExpr o):
        pass
    T visit_list_comprehension(self, nodes.ListComprehension o):
        pass
    T visit_generator_expr(self, nodes.GeneratorExpr o):
        pass
    T visit_slice_expr(self, nodes.SliceExpr o):
        pass
    T visit_conditional_expr(self, nodes.ConditionalExpr o):
        pass
    
    T visit_coerce_expr(self, nodes.CoerceExpr o):
        pass
    T visit_type_expr(self, nodes.TypeExpr o):
        pass
    T visit_java_cast(self, nodes.JavaCast o):
        pass
    
    T visit_temp_node(self, nodes.TempNode o):
        pass
