"""Generic abstract syntax tree node visitor"""

from typing import TypeVar, Generic

if False:
    # break import cycle only needed for mypy
    import mypy.nodes


T = TypeVar('T')


class NodeVisitor(Generic[T]):
    """Empty base class for parse tree node visitors.

    The T type argument specifies the return type of the visit
    methods. As all methods defined here return None by default,
    subclasses do not always need to override all the methods.

    TODO make the default return value explicit
    """

    # Module structure

    def visit_mypy_file(self, o: 'mypy.nodes.MypyFile') -> T:
        pass

    def visit_import(self, o: 'mypy.nodes.Import') -> T:
        pass

    def visit_import_from(self, o: 'mypy.nodes.ImportFrom') -> T:
        pass

    def visit_import_all(self, o: 'mypy.nodes.ImportAll') -> T:
        pass

    # Definitions

    def visit_func_def(self, o: 'mypy.nodes.FuncDef') -> T:
        pass

    def visit_overloaded_func_def(self,
                                  o: 'mypy.nodes.OverloadedFuncDef') -> T:
        pass

    def visit_class_def(self, o: 'mypy.nodes.ClassDef') -> T:
        pass

    def visit_global_decl(self, o: 'mypy.nodes.GlobalDecl') -> T:
        pass

    def visit_nonlocal_decl(self, o: 'mypy.nodes.NonlocalDecl') -> T:
        pass

    def visit_decorator(self, o: 'mypy.nodes.Decorator') -> T:
        pass

    def visit_var(self, o: 'mypy.nodes.Var') -> T:
        pass

    # Statements

    def visit_block(self, o: 'mypy.nodes.Block') -> T:
        pass

    def visit_expression_stmt(self, o: 'mypy.nodes.ExpressionStmt') -> T:
        pass

    def visit_assignment_stmt(self, o: 'mypy.nodes.AssignmentStmt') -> T:
        pass

    def visit_operator_assignment_stmt(self,
                                       o: 'mypy.nodes.OperatorAssignmentStmt') -> T:
        pass

    def visit_while_stmt(self, o: 'mypy.nodes.WhileStmt') -> T:
        pass

    def visit_for_stmt(self, o: 'mypy.nodes.ForStmt') -> T:
        pass

    def visit_return_stmt(self, o: 'mypy.nodes.ReturnStmt') -> T:
        pass

    def visit_assert_stmt(self, o: 'mypy.nodes.AssertStmt') -> T:
        pass

    def visit_del_stmt(self, o: 'mypy.nodes.DelStmt') -> T:
        pass

    def visit_if_stmt(self, o: 'mypy.nodes.IfStmt') -> T:
        pass

    def visit_break_stmt(self, o: 'mypy.nodes.BreakStmt') -> T:
        pass

    def visit_continue_stmt(self, o: 'mypy.nodes.ContinueStmt') -> T:
        pass

    def visit_pass_stmt(self, o: 'mypy.nodes.PassStmt') -> T:
        pass

    def visit_raise_stmt(self, o: 'mypy.nodes.RaiseStmt') -> T:
        pass

    def visit_try_stmt(self, o: 'mypy.nodes.TryStmt') -> T:
        pass

    def visit_with_stmt(self, o: 'mypy.nodes.WithStmt') -> T:
        pass

    def visit_print_stmt(self, o: 'mypy.nodes.PrintStmt') -> T:
        pass

    def visit_exec_stmt(self, o: 'mypy.nodes.ExecStmt') -> T:
        pass

    # Expressions

    def visit_int_expr(self, o: 'mypy.nodes.IntExpr') -> T:
        pass

    def visit_str_expr(self, o: 'mypy.nodes.StrExpr') -> T:
        pass

    def visit_bytes_expr(self, o: 'mypy.nodes.BytesExpr') -> T:
        pass

    def visit_unicode_expr(self, o: 'mypy.nodes.UnicodeExpr') -> T:
        pass

    def visit_float_expr(self, o: 'mypy.nodes.FloatExpr') -> T:
        pass

    def visit_complex_expr(self, o: 'mypy.nodes.ComplexExpr') -> T:
        pass

    def visit_ellipsis(self, o: 'mypy.nodes.EllipsisExpr') -> T:
        pass

    def visit_star_expr(self, o: 'mypy.nodes.StarExpr') -> T:
        pass

    def visit_name_expr(self, o: 'mypy.nodes.NameExpr') -> T:
        pass

    def visit_member_expr(self, o: 'mypy.nodes.MemberExpr') -> T:
        pass

    def visit_yield_from_expr(self, o: 'mypy.nodes.YieldFromExpr') -> T:
        pass

    def visit_yield_expr(self, o: 'mypy.nodes.YieldExpr') -> T:
        pass

    def visit_call_expr(self, o: 'mypy.nodes.CallExpr') -> T:
        pass

    def visit_op_expr(self, o: 'mypy.nodes.OpExpr') -> T:
        pass

    def visit_comparison_expr(self, o: 'mypy.nodes.ComparisonExpr') -> T:
        pass

    def visit_cast_expr(self, o: 'mypy.nodes.CastExpr') -> T:
        pass

    def visit_reveal_type_expr(self, o: 'mypy.nodes.RevealTypeExpr') -> T:
        pass

    def visit_super_expr(self, o: 'mypy.nodes.SuperExpr') -> T:
        pass

    def visit_unary_expr(self, o: 'mypy.nodes.UnaryExpr') -> T:
        pass

    def visit_list_expr(self, o: 'mypy.nodes.ListExpr') -> T:
        pass

    def visit_dict_expr(self, o: 'mypy.nodes.DictExpr') -> T:
        pass

    def visit_tuple_expr(self, o: 'mypy.nodes.TupleExpr') -> T:
        pass

    def visit_set_expr(self, o: 'mypy.nodes.SetExpr') -> T:
        pass

    def visit_index_expr(self, o: 'mypy.nodes.IndexExpr') -> T:
        pass

    def visit_type_application(self, o: 'mypy.nodes.TypeApplication') -> T:
        pass

    def visit_func_expr(self, o: 'mypy.nodes.FuncExpr') -> T:
        pass

    def visit_list_comprehension(self, o: 'mypy.nodes.ListComprehension') -> T:
        pass

    def visit_set_comprehension(self, o: 'mypy.nodes.SetComprehension') -> T:
        pass

    def visit_dictionary_comprehension(self, o: 'mypy.nodes.DictionaryComprehension') -> T:
        pass

    def visit_generator_expr(self, o: 'mypy.nodes.GeneratorExpr') -> T:
        pass

    def visit_slice_expr(self, o: 'mypy.nodes.SliceExpr') -> T:
        pass

    def visit_conditional_expr(self, o: 'mypy.nodes.ConditionalExpr') -> T:
        pass

    def visit_backquote_expr(self, o: 'mypy.nodes.BackquoteExpr') -> T:
        pass

    def visit_type_var_expr(self, o: 'mypy.nodes.TypeVarExpr') -> T:
        pass

    def visit_type_alias_expr(self, o: 'mypy.nodes.TypeAliasExpr') -> T:
        pass

    def visit_namedtuple_expr(self, o: 'mypy.nodes.NamedTupleExpr') -> T:
        pass

    def visit_newtype_expr(self, o: 'mypy.nodes.NewTypeExpr') -> T:
        pass

    def visit__promote_expr(self, o: 'mypy.nodes.PromoteExpr') -> T:
        pass

    def visit_await_expr(self, o: 'mypy.nodes.AwaitExpr') -> T:
        pass

    def visit_temp_node(self, o: 'mypy.nodes.TempNode') -> T:
        pass
