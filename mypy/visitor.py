"""Generic abstract syntax tree node visitor"""

from abc import abstractmethod
from typing import TypeVar, Generic, Optional
from typing_extensions import TYPE_CHECKING
from mypy_extensions import trait

if TYPE_CHECKING:
    # break import cycle only needed for mypy
    import mypy.nodes


T = TypeVar('T')


@trait
class ExpressionVisitor(Generic[T]):
    @abstractmethod
    def visit_int_expr(self, o: 'mypy.nodes.IntExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_str_expr(self, o: 'mypy.nodes.StrExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_bytes_expr(self, o: 'mypy.nodes.BytesExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_unicode_expr(self, o: 'mypy.nodes.UnicodeExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_float_expr(self, o: 'mypy.nodes.FloatExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_complex_expr(self, o: 'mypy.nodes.ComplexExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_ellipsis(self, o: 'mypy.nodes.EllipsisExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_star_expr(self, o: 'mypy.nodes.StarExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_name_expr(self, o: 'mypy.nodes.NameExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_member_expr(self, o: 'mypy.nodes.MemberExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_yield_from_expr(self, o: 'mypy.nodes.YieldFromExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_yield_expr(self, o: 'mypy.nodes.YieldExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_call_expr(self, o: 'mypy.nodes.CallExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_op_expr(self, o: 'mypy.nodes.OpExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_comparison_expr(self, o: 'mypy.nodes.ComparisonExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_cast_expr(self, o: 'mypy.nodes.CastExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_reveal_expr(self, o: 'mypy.nodes.RevealExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_super_expr(self, o: 'mypy.nodes.SuperExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_unary_expr(self, o: 'mypy.nodes.UnaryExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_assignment_expr(self, o: 'mypy.nodes.AssignmentExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_list_expr(self, o: 'mypy.nodes.ListExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_dict_expr(self, o: 'mypy.nodes.DictExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_tuple_expr(self, o: 'mypy.nodes.TupleExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_set_expr(self, o: 'mypy.nodes.SetExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_index_expr(self, o: 'mypy.nodes.IndexExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_type_application(self, o: 'mypy.nodes.TypeApplication') -> Optional[T]:
        pass

    @abstractmethod
    def visit_lambda_expr(self, o: 'mypy.nodes.LambdaExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_list_comprehension(self, o: 'mypy.nodes.ListComprehension') -> Optional[T]:
        pass

    @abstractmethod
    def visit_set_comprehension(self, o: 'mypy.nodes.SetComprehension') -> Optional[T]:
        pass

    @abstractmethod
    def visit_dictionary_comprehension(self, o: 'mypy.nodes.DictionaryComprehension'
                                       ) -> Optional[T]:
        pass

    @abstractmethod
    def visit_generator_expr(self, o: 'mypy.nodes.GeneratorExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_slice_expr(self, o: 'mypy.nodes.SliceExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_conditional_expr(self, o: 'mypy.nodes.ConditionalExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_backquote_expr(self, o: 'mypy.nodes.BackquoteExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_type_var_expr(self, o: 'mypy.nodes.TypeVarExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_type_alias_expr(self, o: 'mypy.nodes.TypeAliasExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_namedtuple_expr(self, o: 'mypy.nodes.NamedTupleExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_enum_call_expr(self, o: 'mypy.nodes.EnumCallExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_typeddict_expr(self, o: 'mypy.nodes.TypedDictExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_newtype_expr(self, o: 'mypy.nodes.NewTypeExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit__promote_expr(self, o: 'mypy.nodes.PromoteExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_await_expr(self, o: 'mypy.nodes.AwaitExpr') -> Optional[T]:
        pass

    @abstractmethod
    def visit_temp_node(self, o: 'mypy.nodes.TempNode') -> Optional[T]:
        pass


@trait
class StatementVisitor(Generic[T]):
    # Definitions

    @abstractmethod
    def visit_assignment_stmt(self, o: 'mypy.nodes.AssignmentStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_for_stmt(self, o: 'mypy.nodes.ForStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_with_stmt(self, o: 'mypy.nodes.WithStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_del_stmt(self, o: 'mypy.nodes.DelStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_func_def(self, o: 'mypy.nodes.FuncDef') -> Optional[T]:
        pass

    @abstractmethod
    def visit_overloaded_func_def(self, o: 'mypy.nodes.OverloadedFuncDef') -> Optional[T]:
        pass

    @abstractmethod
    def visit_class_def(self, o: 'mypy.nodes.ClassDef') -> Optional[T]:
        pass

    @abstractmethod
    def visit_global_decl(self, o: 'mypy.nodes.GlobalDecl') -> Optional[T]:
        pass

    @abstractmethod
    def visit_nonlocal_decl(self, o: 'mypy.nodes.NonlocalDecl') -> Optional[T]:
        pass

    @abstractmethod
    def visit_decorator(self, o: 'mypy.nodes.Decorator') -> Optional[T]:
        pass

    # Module structure

    @abstractmethod
    def visit_import(self, o: 'mypy.nodes.Import') -> Optional[T]:
        pass

    @abstractmethod
    def visit_import_from(self, o: 'mypy.nodes.ImportFrom') -> Optional[T]:
        pass

    @abstractmethod
    def visit_import_all(self, o: 'mypy.nodes.ImportAll') -> Optional[T]:
        pass

    # Statements

    @abstractmethod
    def visit_block(self, o: 'mypy.nodes.Block') -> Optional[T]:
        pass

    @abstractmethod
    def visit_expression_stmt(self, o: 'mypy.nodes.ExpressionStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_operator_assignment_stmt(self, o: 'mypy.nodes.OperatorAssignmentStmt'
                                       ) -> Optional[T]:
        pass

    @abstractmethod
    def visit_while_stmt(self, o: 'mypy.nodes.WhileStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_return_stmt(self, o: 'mypy.nodes.ReturnStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_assert_stmt(self, o: 'mypy.nodes.AssertStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_if_stmt(self, o: 'mypy.nodes.IfStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_break_stmt(self, o: 'mypy.nodes.BreakStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_continue_stmt(self, o: 'mypy.nodes.ContinueStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_pass_stmt(self, o: 'mypy.nodes.PassStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_raise_stmt(self, o: 'mypy.nodes.RaiseStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_try_stmt(self, o: 'mypy.nodes.TryStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_print_stmt(self, o: 'mypy.nodes.PrintStmt') -> Optional[T]:
        pass

    @abstractmethod
    def visit_exec_stmt(self, o: 'mypy.nodes.ExecStmt') -> Optional[T]:
        pass


@trait
class NodeVisitor(Generic[T], ExpressionVisitor[T], StatementVisitor[T]):
    """Empty base class for parse tree node visitors.

    The T type argument specifies the return type of the visit
    methods. As all methods defined here return None by default,
    subclasses do not always need to override all the methods.

    TODO make the default return value explicit
    """

    # Not in superclasses:

    def visit_mypy_file(self, o: 'mypy.nodes.MypyFile') -> Optional[T]:
        pass

    # TODO: We have a visit_var method, but no visit_typeinfo or any
    # other non-Statement SymbolNode (accepting those will raise a
    # runtime error). Maybe this should be resolved in some direction.
    def visit_var(self, o: 'mypy.nodes.Var') -> T:
        pass

    # Module structure

    def visit_import(self, o: 'mypy.nodes.Import') -> Optional[T]:
        pass

    def visit_import_from(self, o: 'mypy.nodes.ImportFrom') -> Optional[T]:
        pass

    def visit_import_all(self, o: 'mypy.nodes.ImportAll') -> Optional[T]:
        pass

    # Definitions

    def visit_func_def(self, o: 'mypy.nodes.FuncDef') -> Optional[T]:
        pass

    def visit_overloaded_func_def(self,
                                  o: 'mypy.nodes.OverloadedFuncDef') -> Optional[T]:
        pass

    def visit_class_def(self, o: 'mypy.nodes.ClassDef') -> Optional[T]:
        pass

    def visit_global_decl(self, o: 'mypy.nodes.GlobalDecl') -> Optional[T]:
        pass

    def visit_nonlocal_decl(self, o: 'mypy.nodes.NonlocalDecl') -> Optional[T]:
        pass

    def visit_decorator(self, o: 'mypy.nodes.Decorator') -> Optional[T]:
        pass

    def visit_type_alias(self, o: 'mypy.nodes.TypeAlias') -> Optional[T]:
        pass

    def visit_placeholder_node(self, o: 'mypy.nodes.PlaceholderNode') -> Optional[T]:
        pass

    # Statements

    def visit_block(self, o: 'mypy.nodes.Block') -> Optional[T]:
        pass

    def visit_expression_stmt(self, o: 'mypy.nodes.ExpressionStmt') -> Optional[T]:
        pass

    def visit_assignment_stmt(self, o: 'mypy.nodes.AssignmentStmt') -> Optional[T]:
        pass

    def visit_operator_assignment_stmt(self,
                                       o: 'mypy.nodes.OperatorAssignmentStmt') -> Optional[T]:
        pass

    def visit_while_stmt(self, o: 'mypy.nodes.WhileStmt') -> Optional[T]:
        pass

    def visit_for_stmt(self, o: 'mypy.nodes.ForStmt') -> Optional[T]:
        pass

    def visit_return_stmt(self, o: 'mypy.nodes.ReturnStmt') -> Optional[T]:
        pass

    def visit_assert_stmt(self, o: 'mypy.nodes.AssertStmt') -> Optional[T]:
        pass

    def visit_del_stmt(self, o: 'mypy.nodes.DelStmt') -> Optional[T]:
        pass

    def visit_if_stmt(self, o: 'mypy.nodes.IfStmt') -> Optional[T]:
        pass

    def visit_break_stmt(self, o: 'mypy.nodes.BreakStmt') -> Optional[T]:
        pass

    def visit_continue_stmt(self, o: 'mypy.nodes.ContinueStmt') -> Optional[T]:
        pass

    def visit_pass_stmt(self, o: 'mypy.nodes.PassStmt') -> Optional[T]:
        pass

    def visit_raise_stmt(self, o: 'mypy.nodes.RaiseStmt') -> Optional[T]:
        pass

    def visit_try_stmt(self, o: 'mypy.nodes.TryStmt') -> Optional[T]:
        pass

    def visit_with_stmt(self, o: 'mypy.nodes.WithStmt') -> Optional[T]:
        pass

    def visit_print_stmt(self, o: 'mypy.nodes.PrintStmt') -> Optional[T]:
        pass

    def visit_exec_stmt(self, o: 'mypy.nodes.ExecStmt') -> Optional[T]:
        pass

    # Expressions (default no-op implementation)

    def visit_int_expr(self, o: 'mypy.nodes.IntExpr') -> Optional[T]:
        pass

    def visit_str_expr(self, o: 'mypy.nodes.StrExpr') -> Optional[T]:
        pass

    def visit_bytes_expr(self, o: 'mypy.nodes.BytesExpr') -> Optional[T]:
        pass

    def visit_unicode_expr(self, o: 'mypy.nodes.UnicodeExpr') -> Optional[T]:
        pass

    def visit_float_expr(self, o: 'mypy.nodes.FloatExpr') -> Optional[T]:
        pass

    def visit_complex_expr(self, o: 'mypy.nodes.ComplexExpr') -> Optional[T]:
        pass

    def visit_ellipsis(self, o: 'mypy.nodes.EllipsisExpr') -> Optional[T]:
        pass

    def visit_star_expr(self, o: 'mypy.nodes.StarExpr') -> Optional[T]:
        pass

    def visit_name_expr(self, o: 'mypy.nodes.NameExpr') -> Optional[T]:
        pass

    def visit_member_expr(self, o: 'mypy.nodes.MemberExpr') -> Optional[T]:
        pass

    def visit_yield_from_expr(self, o: 'mypy.nodes.YieldFromExpr') -> Optional[T]:
        pass

    def visit_yield_expr(self, o: 'mypy.nodes.YieldExpr') -> Optional[T]:
        pass

    def visit_call_expr(self, o: 'mypy.nodes.CallExpr') -> Optional[T]:
        pass

    def visit_op_expr(self, o: 'mypy.nodes.OpExpr') -> Optional[T]:
        pass

    def visit_comparison_expr(self, o: 'mypy.nodes.ComparisonExpr') -> Optional[T]:
        pass

    def visit_cast_expr(self, o: 'mypy.nodes.CastExpr') -> Optional[T]:
        pass

    def visit_reveal_expr(self, o: 'mypy.nodes.RevealExpr') -> Optional[T]:
        pass

    def visit_super_expr(self, o: 'mypy.nodes.SuperExpr') -> Optional[T]:
        pass

    def visit_assignment_expr(self, o: 'mypy.nodes.AssignmentExpr') -> Optional[T]:
        pass

    def visit_unary_expr(self, o: 'mypy.nodes.UnaryExpr') -> Optional[T]:
        pass

    def visit_list_expr(self, o: 'mypy.nodes.ListExpr') -> Optional[T]:
        pass

    def visit_dict_expr(self, o: 'mypy.nodes.DictExpr') -> Optional[T]:
        pass

    def visit_tuple_expr(self, o: 'mypy.nodes.TupleExpr') -> Optional[T]:
        pass

    def visit_set_expr(self, o: 'mypy.nodes.SetExpr') -> Optional[T]:
        pass

    def visit_index_expr(self, o: 'mypy.nodes.IndexExpr') -> Optional[T]:
        pass

    def visit_type_application(self, o: 'mypy.nodes.TypeApplication') -> Optional[T]:
        pass

    def visit_lambda_expr(self, o: 'mypy.nodes.LambdaExpr') -> Optional[T]:
        pass

    def visit_list_comprehension(self, o: 'mypy.nodes.ListComprehension') -> Optional[T]:
        pass

    def visit_set_comprehension(self, o: 'mypy.nodes.SetComprehension') -> Optional[T]:
        pass

    def visit_dictionary_comprehension(self, o: 'mypy.nodes.DictionaryComprehension'
                                       ) -> Optional[T]:
        pass

    def visit_generator_expr(self, o: 'mypy.nodes.GeneratorExpr') -> Optional[T]:
        pass

    def visit_slice_expr(self, o: 'mypy.nodes.SliceExpr') -> Optional[T]:
        pass

    def visit_conditional_expr(self, o: 'mypy.nodes.ConditionalExpr') -> Optional[T]:
        pass

    def visit_backquote_expr(self, o: 'mypy.nodes.BackquoteExpr') -> Optional[T]:
        pass

    def visit_type_var_expr(self, o: 'mypy.nodes.TypeVarExpr') -> Optional[T]:
        pass

    def visit_type_alias_expr(self, o: 'mypy.nodes.TypeAliasExpr') -> Optional[T]:
        pass

    def visit_namedtuple_expr(self, o: 'mypy.nodes.NamedTupleExpr') -> Optional[T]:
        pass

    def visit_enum_call_expr(self, o: 'mypy.nodes.EnumCallExpr') -> Optional[T]:
        pass

    def visit_typeddict_expr(self, o: 'mypy.nodes.TypedDictExpr') -> Optional[T]:
        pass

    def visit_newtype_expr(self, o: 'mypy.nodes.NewTypeExpr') -> Optional[T]:
        pass

    def visit__promote_expr(self, o: 'mypy.nodes.PromoteExpr') -> Optional[T]:
        pass

    def visit_await_expr(self, o: 'mypy.nodes.AwaitExpr') -> Optional[T]:
        pass

    def visit_temp_node(self, o: 'mypy.nodes.TempNode') -> Optional[T]:
        pass
