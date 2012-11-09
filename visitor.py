

# Empty base class for parse tree node visitors. The T type argument
# specifies the return type of the visit methods. As all methods defined here
# return nil by default, subclasses do not always need to override all the
# methods.
class NodeVisitor<T>:
    # Top-level structures
    
    T visit_mypy_file(self, MypyFile o):
        pass
    
    T visit_import(self, Import o):
        pass
    T visit_import_from(self, ImportFrom o):
        pass
    T visit_import_all(self, ImportAll o):
        pass
    
    # Definitions
    
    T visit_func_def(self, FuncDef o):
        pass
    T visit_overloaded_func_def(self, OverloadedFuncDef o):
        pass
    T visit_type_def(self, TypeDef o):
        pass
    T visit_var_def(self, VarDef o):
        pass
    T visit_global_decl(self, GlobalDecl o):
        pass
    T visit_decorator(self, Decorator o):
        pass
    
    T visit_var(self, Var o):
        pass
    
    T visit_annotation(self, Annotation o):
        pass
    
    # Statements
    
    T visit_block(self, Block o):
        pass
    
    T visit_expression_stmt(self, ExpressionStmt o):
        pass
    T visit_assignment_stmt(self, AssignmentStmt o):
        pass
    T visit_operator_assignment_stmt(self, OperatorAssignmentStmt o):
        pass
    T visit_while_stmt(self, WhileStmt o):
        pass
    T visit_for_stmt(self, ForStmt o):
        pass
    T visit_return_stmt(self, ReturnStmt o):
        pass
    T visit_assert_stmt(self, AssertStmt o):
        pass
    T visit_yield_stmt(self, YieldStmt o):
        pass
    T visit_del_stmt(self, DelStmt o):
        pass
    T visit_if_stmt(self, IfStmt o):
        pass
    T visit_break_stmt(self, BreakStmt o):
        pass
    T visit_continue_stmt(self, ContinueStmt o):
        pass
    T visit_pass_stmt(self, PassStmt o):
        pass
    T visit_raise_stmt(self, RaiseStmt o):
        pass
    T visit_try_stmt(self, TryStmt o):
        pass
    T visit_with_stmt(self, WithStmt o):
        pass
    
    # Expressions
    
    T visit_int_expr(self, IntExpr o):
        pass
    T visit_str_expr(self, StrExpr o):
        pass
    T visit_float_expr(self, FloatExpr o):
        pass
    T visit_paren_expr(self, ParenExpr o):
        pass
    T visit_name_expr(self, NameExpr o):
        pass
    T visit_member_expr(self, MemberExpr o):
        pass
    T visit_call_expr(self, CallExpr o):
        pass
    T visit_op_expr(self, OpExpr o):
        pass
    T visit_cast_expr(self, CastExpr o):
        pass
    T visit_super_expr(self, SuperExpr o):
        pass
    T visit_unary_expr(self, UnaryExpr o):
        pass
    T visit_list_expr(self, ListExpr o):
        pass
    T visit_dict_expr(self, DictExpr o):
        pass
    T visit_tuple_expr(self, TupleExpr o):
        pass
    T visit_set_expr(self, SetExpr o):
        pass
    T visit_index_expr(self, IndexExpr o):
        pass
    T visit_type_application(self, TypeApplication o):
        pass
    T visit_func_expr(self, FuncExpr o):
        pass
    T visit_list_comprehension(self, ListComprehension o):
        pass
    T visit_generator_expr(self, GeneratorExpr o):
        pass
    T visit_slice_expr(self, SliceExpr o):
        pass
    T visit_conditional_expr(self, ConditionalExpr o):
        pass
    
    T visit_coerce_expr(self, CoerceExpr o):
        pass
    T visit_type_expr(self, TypeExpr o):
        pass
    T visit_java_cast(self, JavaCast o):
        pass
    
    T visit_temp_node(self, TempNode o):
        pass
