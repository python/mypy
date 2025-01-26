"""Generic abstract syntax tree node visitor"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

from mypy_extensions import mypyc_attr, trait

if TYPE_CHECKING:
    # break import cycle only needed for mypy
    import mypy.nodes
    import mypy.patterns


T = TypeVar("T")


@trait
@mypyc_attr(allow_interpreted_subclasses=True)
class ExpressionVisitor(Generic[T]):
    @abstractmethod
    def visit_int_expr(self, o: mypy.nodes.IntExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_str_expr(self, o: mypy.nodes.StrExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_bytes_expr(self, o: mypy.nodes.BytesExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_float_expr(self, o: mypy.nodes.FloatExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_complex_expr(self, o: mypy.nodes.ComplexExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_ellipsis(self, o: mypy.nodes.EllipsisExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_star_expr(self, o: mypy.nodes.StarExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_name_expr(self, o: mypy.nodes.NameExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_member_expr(self, o: mypy.nodes.MemberExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_yield_from_expr(self, o: mypy.nodes.YieldFromExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_yield_expr(self, o: mypy.nodes.YieldExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_call_expr(self, o: mypy.nodes.CallExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_op_expr(self, o: mypy.nodes.OpExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_comparison_expr(self, o: mypy.nodes.ComparisonExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_cast_expr(self, o: mypy.nodes.CastExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_assert_type_expr(self, o: mypy.nodes.AssertTypeExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_reveal_expr(self, o: mypy.nodes.RevealExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_super_expr(self, o: mypy.nodes.SuperExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_unary_expr(self, o: mypy.nodes.UnaryExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_assignment_expr(self, o: mypy.nodes.AssignmentExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_list_expr(self, o: mypy.nodes.ListExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_dict_expr(self, o: mypy.nodes.DictExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_tuple_expr(self, o: mypy.nodes.TupleExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_set_expr(self, o: mypy.nodes.SetExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_index_expr(self, o: mypy.nodes.IndexExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_type_application(self, o: mypy.nodes.TypeApplication, /) -> T | None:
        pass

    @abstractmethod
    def visit_lambda_expr(self, o: mypy.nodes.LambdaExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_list_comprehension(self, o: mypy.nodes.ListComprehension, /) -> T | None:
        pass

    @abstractmethod
    def visit_set_comprehension(self, o: mypy.nodes.SetComprehension, /) -> T | None:
        pass

    @abstractmethod
    def visit_dictionary_comprehension(self, o: mypy.nodes.DictionaryComprehension, /) -> T | None:
        pass

    @abstractmethod
    def visit_generator_expr(self, o: mypy.nodes.GeneratorExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_slice_expr(self, o: mypy.nodes.SliceExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_conditional_expr(self, o: mypy.nodes.ConditionalExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_type_var_expr(self, o: mypy.nodes.TypeVarExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_paramspec_expr(self, o: mypy.nodes.ParamSpecExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_type_var_tuple_expr(self, o: mypy.nodes.TypeVarTupleExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_type_alias_expr(self, o: mypy.nodes.TypeAliasExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_namedtuple_expr(self, o: mypy.nodes.NamedTupleExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_enum_call_expr(self, o: mypy.nodes.EnumCallExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_typeddict_expr(self, o: mypy.nodes.TypedDictExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_newtype_expr(self, o: mypy.nodes.NewTypeExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit__promote_expr(self, o: mypy.nodes.PromoteExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_await_expr(self, o: mypy.nodes.AwaitExpr, /) -> T | None:
        pass

    @abstractmethod
    def visit_temp_node(self, o: mypy.nodes.TempNode, /) -> T | None:
        pass


@trait
@mypyc_attr(allow_interpreted_subclasses=True)
class StatementVisitor(Generic[T]):
    # Definitions

    @abstractmethod
    def visit_assignment_stmt(self, o: mypy.nodes.AssignmentStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_for_stmt(self, o: mypy.nodes.ForStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_with_stmt(self, o: mypy.nodes.WithStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_del_stmt(self, o: mypy.nodes.DelStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_func_def(self, o: mypy.nodes.FuncDef, /) -> T | None:
        pass

    @abstractmethod
    def visit_overloaded_func_def(self, o: mypy.nodes.OverloadedFuncDef, /) -> T | None:
        pass

    @abstractmethod
    def visit_class_def(self, o: mypy.nodes.ClassDef, /) -> T | None:
        pass

    @abstractmethod
    def visit_global_decl(self, o: mypy.nodes.GlobalDecl, /) -> T | None:
        pass

    @abstractmethod
    def visit_nonlocal_decl(self, o: mypy.nodes.NonlocalDecl, /) -> T | None:
        pass

    @abstractmethod
    def visit_decorator(self, o: mypy.nodes.Decorator, /) -> T | None:
        pass

    # Module structure

    @abstractmethod
    def visit_import(self, o: mypy.nodes.Import, /) -> T | None:
        pass

    @abstractmethod
    def visit_import_from(self, o: mypy.nodes.ImportFrom, /) -> T | None:
        pass

    @abstractmethod
    def visit_import_all(self, o: mypy.nodes.ImportAll, /) -> T | None:
        pass

    # Statements

    @abstractmethod
    def visit_block(self, o: mypy.nodes.Block, /) -> T | None:
        pass

    @abstractmethod
    def visit_expression_stmt(self, o: mypy.nodes.ExpressionStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_operator_assignment_stmt(self, o: mypy.nodes.OperatorAssignmentStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_while_stmt(self, o: mypy.nodes.WhileStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_return_stmt(self, o: mypy.nodes.ReturnStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_assert_stmt(self, o: mypy.nodes.AssertStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_if_stmt(self, o: mypy.nodes.IfStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_break_stmt(self, o: mypy.nodes.BreakStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_continue_stmt(self, o: mypy.nodes.ContinueStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_pass_stmt(self, o: mypy.nodes.PassStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_raise_stmt(self, o: mypy.nodes.RaiseStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_try_stmt(self, o: mypy.nodes.TryStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_match_stmt(self, o: mypy.nodes.MatchStmt, /) -> T | None:
        pass

    @abstractmethod
    def visit_type_alias_stmt(self, o: mypy.nodes.TypeAliasStmt, /) -> T | None:
        pass


@trait
@mypyc_attr(allow_interpreted_subclasses=True)
class PatternVisitor(Generic[T]):
    @abstractmethod
    def visit_as_pattern(self, o: mypy.patterns.AsPattern, /) -> T | None:
        pass

    @abstractmethod
    def visit_or_pattern(self, o: mypy.patterns.OrPattern, /) -> T | None:
        pass

    @abstractmethod
    def visit_value_pattern(self, o: mypy.patterns.ValuePattern, /) -> T | None:
        pass

    @abstractmethod
    def visit_singleton_pattern(self, o: mypy.patterns.SingletonPattern, /) -> T | None:
        pass

    @abstractmethod
    def visit_sequence_pattern(self, o: mypy.patterns.SequencePattern, /) -> T | None:
        pass

    @abstractmethod
    def visit_starred_pattern(self, o: mypy.patterns.StarredPattern, /) -> T | None:
        pass

    @abstractmethod
    def visit_mapping_pattern(self, o: mypy.patterns.MappingPattern, /) -> T | None:
        pass

    @abstractmethod
    def visit_class_pattern(self, o: mypy.patterns.ClassPattern, /) -> T | None:
        pass


@trait
@mypyc_attr(allow_interpreted_subclasses=True)
class NodeVisitor(Generic[T], ExpressionVisitor[T], StatementVisitor[T], PatternVisitor[T]):
    """Empty base class for parse tree node visitors.

    The T type argument specifies the return type of the visit
    methods. As all methods defined here return None by default,
    subclasses do not always need to override all the methods.
    """

    # Not in superclasses:

    def visit_mypy_file(self, o: mypy.nodes.MypyFile, /) -> T | None:
        pass

    # TODO: We have a visit_var method, but no visit_typeinfo or any
    # other non-Statement SymbolNode (accepting those will raise a
    # runtime error). Maybe this should be resolved in some direction.
    def visit_var(self, o: mypy.nodes.Var, /) -> T | None:
        pass

    # Module structure

    def visit_import(self, o: mypy.nodes.Import, /) -> T | None:
        pass

    def visit_import_from(self, o: mypy.nodes.ImportFrom, /) -> T | None:
        pass

    def visit_import_all(self, o: mypy.nodes.ImportAll, /) -> T | None:
        pass

    # Definitions

    def visit_func_def(self, o: mypy.nodes.FuncDef, /) -> T | None:
        pass

    def visit_overloaded_func_def(self, o: mypy.nodes.OverloadedFuncDef, /) -> T | None:
        pass

    def visit_class_def(self, o: mypy.nodes.ClassDef, /) -> T | None:
        pass

    def visit_global_decl(self, o: mypy.nodes.GlobalDecl, /) -> T | None:
        pass

    def visit_nonlocal_decl(self, o: mypy.nodes.NonlocalDecl, /) -> T | None:
        pass

    def visit_decorator(self, o: mypy.nodes.Decorator, /) -> T | None:
        pass

    def visit_type_alias(self, o: mypy.nodes.TypeAlias, /) -> T | None:
        pass

    def visit_placeholder_node(self, o: mypy.nodes.PlaceholderNode, /) -> T | None:
        pass

    # Statements

    def visit_block(self, o: mypy.nodes.Block, /) -> T | None:
        pass

    def visit_expression_stmt(self, o: mypy.nodes.ExpressionStmt, /) -> T | None:
        pass

    def visit_assignment_stmt(self, o: mypy.nodes.AssignmentStmt, /) -> T | None:
        pass

    def visit_operator_assignment_stmt(self, o: mypy.nodes.OperatorAssignmentStmt, /) -> T | None:
        pass

    def visit_while_stmt(self, o: mypy.nodes.WhileStmt, /) -> T | None:
        pass

    def visit_for_stmt(self, o: mypy.nodes.ForStmt, /) -> T | None:
        pass

    def visit_return_stmt(self, o: mypy.nodes.ReturnStmt, /) -> T | None:
        pass

    def visit_assert_stmt(self, o: mypy.nodes.AssertStmt, /) -> T | None:
        pass

    def visit_del_stmt(self, o: mypy.nodes.DelStmt, /) -> T | None:
        pass

    def visit_if_stmt(self, o: mypy.nodes.IfStmt, /) -> T | None:
        pass

    def visit_break_stmt(self, o: mypy.nodes.BreakStmt, /) -> T | None:
        pass

    def visit_continue_stmt(self, o: mypy.nodes.ContinueStmt, /) -> T | None:
        pass

    def visit_pass_stmt(self, o: mypy.nodes.PassStmt, /) -> T | None:
        pass

    def visit_raise_stmt(self, o: mypy.nodes.RaiseStmt, /) -> T | None:
        pass

    def visit_try_stmt(self, o: mypy.nodes.TryStmt, /) -> T | None:
        pass

    def visit_with_stmt(self, o: mypy.nodes.WithStmt, /) -> T | None:
        pass

    def visit_match_stmt(self, o: mypy.nodes.MatchStmt, /) -> T | None:
        pass

    def visit_type_alias_stmt(self, o: mypy.nodes.TypeAliasStmt, /) -> T | None:
        pass

    # Expressions (default no-op implementation)

    def visit_int_expr(self, o: mypy.nodes.IntExpr, /) -> T | None:
        pass

    def visit_str_expr(self, o: mypy.nodes.StrExpr, /) -> T | None:
        pass

    def visit_bytes_expr(self, o: mypy.nodes.BytesExpr, /) -> T | None:
        pass

    def visit_float_expr(self, o: mypy.nodes.FloatExpr, /) -> T | None:
        pass

    def visit_complex_expr(self, o: mypy.nodes.ComplexExpr, /) -> T | None:
        pass

    def visit_ellipsis(self, o: mypy.nodes.EllipsisExpr, /) -> T | None:
        pass

    def visit_star_expr(self, o: mypy.nodes.StarExpr, /) -> T | None:
        pass

    def visit_name_expr(self, o: mypy.nodes.NameExpr, /) -> T | None:
        pass

    def visit_member_expr(self, o: mypy.nodes.MemberExpr, /) -> T | None:
        pass

    def visit_yield_from_expr(self, o: mypy.nodes.YieldFromExpr, /) -> T | None:
        pass

    def visit_yield_expr(self, o: mypy.nodes.YieldExpr, /) -> T | None:
        pass

    def visit_call_expr(self, o: mypy.nodes.CallExpr, /) -> T | None:
        pass

    def visit_op_expr(self, o: mypy.nodes.OpExpr, /) -> T | None:
        pass

    def visit_comparison_expr(self, o: mypy.nodes.ComparisonExpr, /) -> T | None:
        pass

    def visit_cast_expr(self, o: mypy.nodes.CastExpr, /) -> T | None:
        pass

    def visit_assert_type_expr(self, o: mypy.nodes.AssertTypeExpr, /) -> T | None:
        pass

    def visit_reveal_expr(self, o: mypy.nodes.RevealExpr, /) -> T | None:
        pass

    def visit_super_expr(self, o: mypy.nodes.SuperExpr, /) -> T | None:
        pass

    def visit_assignment_expr(self, o: mypy.nodes.AssignmentExpr, /) -> T | None:
        pass

    def visit_unary_expr(self, o: mypy.nodes.UnaryExpr, /) -> T | None:
        pass

    def visit_list_expr(self, o: mypy.nodes.ListExpr, /) -> T | None:
        pass

    def visit_dict_expr(self, o: mypy.nodes.DictExpr, /) -> T | None:
        pass

    def visit_tuple_expr(self, o: mypy.nodes.TupleExpr, /) -> T | None:
        pass

    def visit_set_expr(self, o: mypy.nodes.SetExpr, /) -> T | None:
        pass

    def visit_index_expr(self, o: mypy.nodes.IndexExpr, /) -> T | None:
        pass

    def visit_type_application(self, o: mypy.nodes.TypeApplication, /) -> T | None:
        pass

    def visit_lambda_expr(self, o: mypy.nodes.LambdaExpr, /) -> T | None:
        pass

    def visit_list_comprehension(self, o: mypy.nodes.ListComprehension, /) -> T | None:
        pass

    def visit_set_comprehension(self, o: mypy.nodes.SetComprehension, /) -> T | None:
        pass

    def visit_dictionary_comprehension(self, o: mypy.nodes.DictionaryComprehension, /) -> T | None:
        pass

    def visit_generator_expr(self, o: mypy.nodes.GeneratorExpr, /) -> T | None:
        pass

    def visit_slice_expr(self, o: mypy.nodes.SliceExpr, /) -> T | None:
        pass

    def visit_conditional_expr(self, o: mypy.nodes.ConditionalExpr, /) -> T | None:
        pass

    def visit_type_var_expr(self, o: mypy.nodes.TypeVarExpr, /) -> T | None:
        pass

    def visit_paramspec_expr(self, o: mypy.nodes.ParamSpecExpr, /) -> T | None:
        pass

    def visit_type_var_tuple_expr(self, o: mypy.nodes.TypeVarTupleExpr, /) -> T | None:
        pass

    def visit_type_alias_expr(self, o: mypy.nodes.TypeAliasExpr, /) -> T | None:
        pass

    def visit_namedtuple_expr(self, o: mypy.nodes.NamedTupleExpr, /) -> T | None:
        pass

    def visit_enum_call_expr(self, o: mypy.nodes.EnumCallExpr, /) -> T | None:
        pass

    def visit_typeddict_expr(self, o: mypy.nodes.TypedDictExpr, /) -> T | None:
        pass

    def visit_newtype_expr(self, o: mypy.nodes.NewTypeExpr, /) -> T | None:
        pass

    def visit__promote_expr(self, o: mypy.nodes.PromoteExpr, /) -> T | None:
        pass

    def visit_await_expr(self, o: mypy.nodes.AwaitExpr, /) -> T | None:
        pass

    def visit_temp_node(self, o: mypy.nodes.TempNode, /) -> T | None:
        pass

    # Patterns

    def visit_as_pattern(self, o: mypy.patterns.AsPattern, /) -> T | None:
        pass

    def visit_or_pattern(self, o: mypy.patterns.OrPattern, /) -> T | None:
        pass

    def visit_value_pattern(self, o: mypy.patterns.ValuePattern, /) -> T | None:
        pass

    def visit_singleton_pattern(self, o: mypy.patterns.SingletonPattern, /) -> T | None:
        pass

    def visit_sequence_pattern(self, o: mypy.patterns.SequencePattern, /) -> T | None:
        pass

    def visit_starred_pattern(self, o: mypy.patterns.StarredPattern, /) -> T | None:
        pass

    def visit_mapping_pattern(self, o: mypy.patterns.MappingPattern, /) -> T | None:
        pass

    def visit_class_pattern(self, o: mypy.patterns.ClassPattern, /) -> T | None:
        pass
