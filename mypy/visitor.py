import mypy.nodes


class NodeVisitor<T>:
    """Empty base class for parse tree node visitors.

    The T type argument specifies the return type of the visit
    methods. As all methods defined here return None by default,
    subclasses do not always need to override all the methods.
    """
    
    # Top-level structures
    
    T visit_mypy_file(self, mypy.nodes.MypyFile o):
        pass
    
    T visit_import(self, mypy.nodes.Import o):
        pass
    T visit_import_from(self, mypy.nodes.ImportFrom o):
        pass
    T visit_import_all(self, mypy.nodes.ImportAll o):
        pass
    
    # Definitions
    
    T visit_func_def(self, mypy.nodes.FuncDef o):
        pass
    T visit_overloaded_func_def(self, mypy.nodes.OverloadedFuncDef o):
        pass
    T visit_type_def(self, mypy.nodes.TypeDef o):
        pass
    T visit_var_def(self, mypy.nodes.VarDef o):
        pass
    T visit_global_decl(self, mypy.nodes.GlobalDecl o):
        pass
    T visit_decorator(self, mypy.nodes.Decorator o):
        pass
    
    T visit_var(self, mypy.nodes.Var o):
        pass
    
    # Statements
    
    T visit_block(self, mypy.nodes.Block o):
        pass
    
    T visit_expression_stmt(self, mypy.nodes.ExpressionStmt o):
        pass
    T visit_assignment_stmt(self, mypy.nodes.AssignmentStmt o):
        pass
    T visit_operator_assignment_stmt(self,
                                     mypy.nodes.OperatorAssignmentStmt o):
        pass
    T visit_while_stmt(self, mypy.nodes.WhileStmt o):
        pass
    T visit_for_stmt(self, mypy.nodes.ForStmt o):
        pass
    T visit_return_stmt(self, mypy.nodes.ReturnStmt o):
        pass
    T visit_assert_stmt(self, mypy.nodes.AssertStmt o):
        pass
    T visit_yield_stmt(self, mypy.nodes.YieldStmt o):
        pass
    T visit_del_stmt(self, mypy.nodes.DelStmt o):
        pass
    T visit_if_stmt(self, mypy.nodes.IfStmt o):
        pass
    T visit_break_stmt(self, mypy.nodes.BreakStmt o):
        pass
    T visit_continue_stmt(self, mypy.nodes.ContinueStmt o):
        pass
    T visit_pass_stmt(self, mypy.nodes.PassStmt o):
        pass
    T visit_raise_stmt(self, mypy.nodes.RaiseStmt o):
        pass
    T visit_try_stmt(self, mypy.nodes.TryStmt o):
        pass
    T visit_with_stmt(self, mypy.nodes.WithStmt o):
        pass
    
    # Expressions
    
    T visit_int_expr(self, mypy.nodes.IntExpr o):
        pass
    T visit_str_expr(self, mypy.nodes.StrExpr o):
        pass
    T visit_bytes_expr(self, mypy.nodes.BytesExpr o):
        pass
    T visit_float_expr(self, mypy.nodes.FloatExpr o):
        pass
    T visit_paren_expr(self, mypy.nodes.ParenExpr o):
        pass
    T visit_name_expr(self, mypy.nodes.NameExpr o):
        pass
    T visit_member_expr(self, mypy.nodes.MemberExpr o):
        pass
    T visit_call_expr(self, mypy.nodes.CallExpr o):
        pass
    T visit_op_expr(self, mypy.nodes.OpExpr o):
        pass
    T visit_cast_expr(self, mypy.nodes.CastExpr o):
        pass
    T visit_super_expr(self, mypy.nodes.SuperExpr o):
        pass
    T visit_unary_expr(self, mypy.nodes.UnaryExpr o):
        pass
    T visit_list_expr(self, mypy.nodes.ListExpr o):
        pass
    T visit_dict_expr(self, mypy.nodes.DictExpr o):
        pass
    T visit_tuple_expr(self, mypy.nodes.TupleExpr o):
        pass
    T visit_set_expr(self, mypy.nodes.SetExpr o):
        pass
    T visit_index_expr(self, mypy.nodes.IndexExpr o):
        pass
    T visit_undefined_expr(self, mypy.nodes.UndefinedExpr o):
        pass
    T visit_type_application(self, mypy.nodes.TypeApplication o):
        pass
    T visit_func_expr(self, mypy.nodes.FuncExpr o):
        pass
    T visit_list_comprehension(self, mypy.nodes.ListComprehension o):
        pass
    T visit_generator_expr(self, mypy.nodes.GeneratorExpr o):
        pass
    T visit_slice_expr(self, mypy.nodes.SliceExpr o):
        pass
    T visit_conditional_expr(self, mypy.nodes.ConditionalExpr o):
        pass
    
    T visit_coerce_expr(self, mypy.nodes.CoerceExpr o):
        pass
    T visit_type_expr(self, mypy.nodes.TypeExpr o):
        pass
    T visit_java_cast(self, mypy.nodes.JavaCast o):
        pass
    
    T visit_temp_node(self, mypy.nodes.TempNode o):
        pass
