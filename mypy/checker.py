"""Mypy type checker."""

import itertools
import fnmatch
from contextlib import contextmanager
import sys

from typing import (
    Dict, Set, List, cast, Tuple, TypeVar, Union, Optional, NamedTuple, Iterator
)

from mypy.errors import Errors, report_internal_error
from mypy.nodes import (
    SymbolTable, Statement, MypyFile, Var, Expression, Lvalue,
    OverloadedFuncDef, FuncDef, FuncItem, FuncBase, TypeInfo,
    ClassDef, GDEF, Block, AssignmentStmt, NameExpr, MemberExpr, IndexExpr,
    TupleExpr, ListExpr, ExpressionStmt, ReturnStmt, IfStmt,
    WhileStmt, OperatorAssignmentStmt, WithStmt, AssertStmt,
    RaiseStmt, TryStmt, ForStmt, DelStmt, CallExpr, IntExpr, StrExpr,
    BytesExpr, UnicodeExpr, FloatExpr, OpExpr, UnaryExpr, CastExpr, RevealTypeExpr, SuperExpr,
    TypeApplication, DictExpr, SliceExpr, LambdaExpr, TempNode, SymbolTableNode,
    Context, ListComprehension, ConditionalExpr, GeneratorExpr,
    Decorator, SetExpr, TypeVarExpr, NewTypeExpr, PrintStmt,
    LITERAL_TYPE, BreakStmt, PassStmt, ContinueStmt, ComparisonExpr, StarExpr,
    YieldFromExpr, NamedTupleExpr, TypedDictExpr, SetComprehension,
    DictionaryComprehension, ComplexExpr, EllipsisExpr, TypeAliasExpr,
    RefExpr, YieldExpr, BackquoteExpr, Import, ImportFrom, ImportAll, ImportBase,
    AwaitExpr, PromoteExpr, Node, EnumCallExpr,
    ARG_POS, MDEF,
    CONTRAVARIANT, COVARIANT, INVARIANT)
from mypy import nodes
from mypy.literals import literal, literal_hash
from mypy.typeanal import has_any_from_unimported_type, check_for_explicit_any
from mypy.types import (
    Type, AnyType, CallableType, FunctionLike, Overloaded, TupleType, TypedDictType,
    Instance, NoneTyp, strip_type, TypeType, TypeOfAny,
    UnionType, TypeVarId, TypeVarType, PartialType, DeletedType, UninhabitedType, TypeVarDef,
    true_only, false_only, function_type, is_named_instance, union_items
)
from mypy.sametypes import is_same_type, is_same_types
from mypy.messages import MessageBuilder, make_inferred_type_note
import mypy.checkexpr
from mypy.checkmember import map_type_from_supertype, bind_self, erase_to_bound
from mypy import messages
from mypy.subtypes import (
    is_subtype, is_equivalent, is_proper_subtype, is_more_precise,
    restrict_subtype_away, is_subtype_ignoring_tvars, is_callable_subtype,
    unify_generic_callable, find_member
)
from mypy.maptype import map_instance_to_supertype
from mypy.typevars import fill_typevars, has_no_typevars
from mypy.semanal import set_callable_name, refers_to_fullname
from mypy.erasetype import erase_typevars
from mypy.expandtype import expand_type, expand_type_by_instance
from mypy.visitor import NodeVisitor
from mypy.join import join_types
from mypy.treetransform import TransformVisitor
from mypy.binder import ConditionalTypeBinder, get_declaration
from mypy.meet import is_overlapping_types
from mypy.options import Options
from mypy.plugin import Plugin, CheckerPluginInterface

from mypy import experiments


T = TypeVar('T')

LAST_PASS = 1  # Pass numbers start at 0


# A node which is postponed to be processed during the next pass.
# This is used for both batch mode and fine-grained incremental mode.
DeferredNode = NamedTuple(
    'DeferredNode',
    [
        # In batch mode only FuncDef and LambdaExpr are supported
        ('node', Union[FuncDef, LambdaExpr, MypyFile]),
        ('context_type_name', Optional[str]),  # Name of the surrounding class (for error messages)
        ('active_typeinfo', Optional[TypeInfo]),  # And its TypeInfo (for semantic analysis
                                                  # self type handling)
    ])


class TypeChecker(NodeVisitor[None], CheckerPluginInterface):
    """Mypy type checker.

    Type check mypy source files that have been semantically analyzed.

    You must create a separate instance for each source file.
    """

    # Are we type checking a stub?
    is_stub = False
    # Error message reporter
    errors = None  # type: Errors
    # Utility for generating messages
    msg = None  # type: MessageBuilder
    # Types of type checked nodes
    type_map = None  # type: Dict[Expression, Type]

    # Helper for managing conditional types
    binder = None  # type: ConditionalTypeBinder
    # Helper for type checking expressions
    expr_checker = None  # type: mypy.checkexpr.ExpressionChecker

    scope = None  # type: Scope
    # Stack of function return types
    return_types = None  # type: List[Type]
    # Flags; true for dynamically typed functions
    dynamic_funcs = None  # type: List[bool]
    # Stack of collections of variables with partial types
    partial_types = None  # type: List[Dict[Var, Context]]
    # Vars for which partial type errors are already reported
    # (to avoid logically duplicate errors with different error context).
    partial_reported = None  # type: Set[Var]
    globals = None  # type: SymbolTable
    modules = None  # type: Dict[str, MypyFile]
    # Nodes that couldn't be checked because some types weren't available. We'll run
    # another pass and try these again.
    deferred_nodes = None  # type: List[DeferredNode]
    # Type checking pass number (0 = first pass)
    pass_num = 0
    # Have we deferred the current function? If yes, don't infer additional
    # types during this pass within the function.
    current_node_deferred = False
    # Is this file a typeshed stub?
    is_typeshed_stub = False
    # Should strict Optional-related errors be suppressed in this file?
    suppress_none_errors = False  # TODO: Get it from options instead
    options = None  # type: Options
    # Used for collecting inferred attribute types so that they can be checked
    # for consistency.
    inferred_attribute_types = None  # type: Optional[Dict[Var, Type]]
    # Don't infer partial None types if we are processing assignment from Union
    no_partial_types = False  # type: bool

    # The set of all dependencies (suppressed or not) that this module accesses, either
    # directly or indirectly.
    module_refs = None  # type: Set[str]

    # Plugin that provides special type checking rules for specific library
    # functions such as open(), etc.
    plugin = None  # type: Plugin

    def __init__(self, errors: Errors, modules: Dict[str, MypyFile], options: Options,
                 tree: MypyFile, path: str, plugin: Plugin) -> None:
        """Construct a type checker.

        Use errors to report type check errors.
        """
        self.errors = errors
        self.modules = modules
        self.options = options
        self.tree = tree
        self.path = path
        self.msg = MessageBuilder(errors, modules)
        self.plugin = plugin
        self.expr_checker = mypy.checkexpr.ExpressionChecker(self, self.msg, self.plugin)
        self.scope = Scope(tree)
        self.binder = ConditionalTypeBinder()
        self.globals = tree.names
        self.return_types = []
        self.dynamic_funcs = []
        self.partial_types = []
        self.partial_reported = set()
        self.deferred_nodes = []
        self.type_map = {}
        self.module_refs = set()
        self.pass_num = 0
        self.current_node_deferred = False
        self.is_stub = tree.is_stub
        self.is_typeshed_stub = errors.is_typeshed_file(path)
        self.inferred_attribute_types = None
        if options.strict_optional_whitelist is None:
            self.suppress_none_errors = not options.show_none_errors
        else:
            self.suppress_none_errors = not any(fnmatch.fnmatch(path, pattern)
                                                for pattern
                                                in options.strict_optional_whitelist)

    def check_first_pass(self) -> None:
        """Type check the entire file, but defer functions with unresolved references.

        Unresolved references are forward references to variables
        whose types haven't been inferred yet.  They may occur later
        in the same file or in a different file that's being processed
        later (usually due to an import cycle).

        Deferred functions will be processed by check_second_pass().
        """
        with experiments.strict_optional_set(self.options.strict_optional):
            self.errors.set_file(self.path, self.tree.fullname())
            with self.enter_partial_types():
                with self.binder.top_frame_context():
                    for d in self.tree.defs:
                        self.accept(d)

            assert not self.current_node_deferred

            all_ = self.globals.get('__all__')
            if all_ is not None and all_.type is not None:
                all_node = all_.node
                assert all_node is not None
                seq_str = self.named_generic_type('typing.Sequence',
                                                [self.named_type('builtins.str')])
                if self.options.python_version[0] < 3:
                    seq_str = self.named_generic_type('typing.Sequence',
                                                    [self.named_type('builtins.unicode')])
                if not is_subtype(all_.type, seq_str):
                    str_seq_s, all_s = self.msg.format_distinctly(seq_str, all_.type)
                    self.fail(messages.ALL_MUST_BE_SEQ_STR.format(str_seq_s, all_s),
                            all_node)

    def check_second_pass(self, todo: Optional[List[DeferredNode]] = None) -> bool:
        """Run second or following pass of type checking.

        This goes through deferred nodes, returning True if there were any.
        """
        with experiments.strict_optional_set(self.options.strict_optional):
            if not todo and not self.deferred_nodes:
                return False
            self.errors.set_file(self.path, self.tree.fullname())
            self.pass_num += 1
            if not todo:
                todo = self.deferred_nodes
            else:
                assert not self.deferred_nodes
            self.deferred_nodes = []
            done = set()  # type: Set[Union[FuncDef, LambdaExpr, MypyFile]]
            for node, type_name, active_typeinfo in todo:
                if node in done:
                    continue
                # This is useful for debugging:
                # print("XXX in pass %d, class %s, function %s" %
                #       (self.pass_num, type_name, node.fullname() or node.name()))
                done.add(node)
                with self.errors.enter_type(type_name) if type_name else nothing():
                    with self.scope.push_class(active_typeinfo) if active_typeinfo else nothing():
                        self.check_partial(node)
            return True

    def check_partial(self, node: Union[FuncDef, LambdaExpr, MypyFile]) -> None:
        if isinstance(node, MypyFile):
            self.check_top_level(node)
        elif isinstance(node, LambdaExpr):
            self.expr_checker.accept(node)
        else:
            self.accept(node)

    def check_top_level(self, node: MypyFile) -> None:
        """Check only the top-level of a module, skipping function definitions."""
        with self.enter_partial_types():
            with self.binder.top_frame_context():
                for d in node.defs:
                    # TODO: Type check class bodies.
                    if not isinstance(d, (FuncDef, ClassDef)):
                        d.accept(self)

        assert not self.current_node_deferred
        # TODO: Handle __all__

    def handle_cannot_determine_type(self, name: str, context: Context) -> None:
        node = self.scope.top_function()
        if self.pass_num < LAST_PASS and isinstance(node, (FuncDef, LambdaExpr)):
            # Don't report an error yet. Just defer.
            if self.errors.type_name:
                type_name = self.errors.type_name[-1]
            else:
                type_name = None
            # Shouldn't we freeze the entire scope?
            enclosing_class = self.scope.enclosing_class()
            self.deferred_nodes.append(DeferredNode(node, type_name, enclosing_class))
            # Set a marker so that we won't infer additional types in this
            # function. Any inferred types could be bogus, because there's at
            # least one type that we don't know.
            self.current_node_deferred = True
        else:
            self.msg.cannot_determine_type(name, context)

    def accept(self, stmt: Statement) -> None:
        """Type check a node in the given type context."""
        try:
            stmt.accept(self)
        except Exception as err:
            report_internal_error(err, self.errors.file, stmt.line, self.errors, self.options)

    def accept_loop(self, body: Statement, else_body: Optional[Statement] = None, *,
                    exit_condition: Optional[Expression] = None) -> None:
        """Repeatedly type check a loop body until the frame doesn't change.
        If exit_condition is set, assume it must be False on exit from the loop.

        Then check the else_body.
        """
        # The outer frame accumulates the results of all iterations
        with self.binder.frame_context(can_skip=False):
            while True:
                with self.binder.frame_context(can_skip=True,
                                               break_frame=2, continue_frame=1):
                    self.accept(body)
                if not self.binder.last_pop_changed:
                    break
            if exit_condition:
                _, else_map = self.find_isinstance_check(exit_condition)
                self.push_type_map(else_map)
            if else_body:
                self.accept(else_body)

    #
    # Definitions
    #

    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> None:
        num_abstract = 0
        if not defn.items:
            # In this case we have already complained about none of these being
            # valid overloads.
            return None
        if len(defn.items) == 1:
            self.fail('Single overload definition, multiple required', defn)

        if defn.is_property:
            # HACK: Infer the type of the property.
            self.visit_decorator(cast(Decorator, defn.items[0]))
        for fdef in defn.items:
            assert isinstance(fdef, Decorator)
            self.check_func_item(fdef.func, name=fdef.func.name())
            if fdef.func.is_abstract:
                num_abstract += 1
        if num_abstract not in (0, len(defn.items)):
            self.fail(messages.INCONSISTENT_ABSTRACT_OVERLOAD, defn)
        if defn.impl:
            defn.impl.accept(self)
        if defn.info:
            self.check_method_override(defn)
            self.check_inplace_operator_method(defn)
        self.check_overlapping_overloads(defn)
        return None

    def check_overlapping_overloads(self, defn: OverloadedFuncDef) -> None:
        # At this point we should have set the impl already, and all remaining
        # items are decorators
        for i, item in enumerate(defn.items):
            assert isinstance(item, Decorator)
            sig1 = self.function_type(item.func)
            for j, item2 in enumerate(defn.items[i + 1:]):
                # TODO overloads involving decorators
                assert isinstance(item2, Decorator)
                sig2 = self.function_type(item2.func)
                if is_unsafe_overlapping_signatures(sig1, sig2):
                    self.msg.overloaded_signatures_overlap(i + 1, i + j + 2,
                                                           item.func)
            if defn.impl:
                if isinstance(defn.impl, FuncDef):
                    impl_type = defn.impl.type
                elif isinstance(defn.impl, Decorator):
                    impl_type = defn.impl.var.type
                else:
                    assert False, "Impl isn't the right type"
                # This can happen if we've got an overload with a different
                # decorator too -- we gave up on the types.
                if impl_type is None or isinstance(impl_type, AnyType) or sig1 is None:
                    return

                assert isinstance(impl_type, CallableType)
                assert isinstance(sig1, CallableType)
                if not is_callable_subtype(impl_type, sig1, ignore_return=True):
                    self.msg.overloaded_signatures_arg_specific(i + 1, defn.impl)
                impl_type_subst = impl_type
                if impl_type.variables:
                    unified = unify_generic_callable(impl_type, sig1, ignore_return=False)
                    if unified is None:
                        self.fail("Type variable mismatch between " +
                                  "overload signature {} and implementation".format(i + 1),
                                  defn.impl)
                        return
                    impl_type_subst = unified
                if not is_subtype(sig1.ret_type, impl_type_subst.ret_type):
                    self.msg.overloaded_signatures_ret_specific(i + 1, defn.impl)

    # Here's the scoop about generators and coroutines.
    #
    # There are two kinds of generators: classic generators (functions
    # with `yield` or `yield from` in the body) and coroutines
    # (functions declared with `async def`).  The latter are specified
    # in PEP 492 and only available in Python >= 3.5.
    #
    # Classic generators can be parameterized with three types:
    # - ty is the Yield type (the type of y in `yield y`)
    # - tc is the type reCeived by yield (the type of c in `c = yield`).
    # - tr is the Return type (the type of r in `return r`)
    #
    # A classic generator must define a return type that's either
    # `Generator[ty, tc, tr]`, Iterator[ty], or Iterable[ty] (or
    # object or Any).  If tc/tr are not given, both are None.
    #
    # A coroutine must define a return type corresponding to tr; the
    # other two are unconstrained.  The "external" return type (seen
    # by the caller) is Awaitable[tr].
    #
    # In addition, there's the synthetic type AwaitableGenerator: it
    # inherits from both Awaitable and Generator and can be used both
    # in `yield from` and in `await`.  This type is set automatically
    # for functions decorated with `@types.coroutine` or
    # `@asyncio.coroutine`.  Its single parameter corresponds to tr.
    #
    # PEP 525 adds a new type, the asynchronous generator, which was
    # first released in Python 3.6. Async generators are `async def`
    # functions that can also `yield` values. They can be parameterized
    # with two types, ty and tc, because they cannot return a value.
    #
    # There are several useful methods, each taking a type t and a
    # flag c indicating whether it's for a generator or coroutine:
    #
    # - is_generator_return_type(t, c) returns whether t is a Generator,
    #   Iterator, Iterable (if not c), or Awaitable (if c), or
    #   AwaitableGenerator (regardless of c).
    # - is_async_generator_return_type(t) returns whether t is an
    #   AsyncGenerator.
    # - get_generator_yield_type(t, c) returns ty.
    # - get_generator_receive_type(t, c) returns tc.
    # - get_generator_return_type(t, c) returns tr.

    def is_generator_return_type(self, typ: Type, is_coroutine: bool) -> bool:
        """Is `typ` a valid type for a generator/coroutine?

        True if `typ` is a *supertype* of Generator or Awaitable.
        Also true it it's *exactly* AwaitableGenerator (modulo type parameters).
        """
        if is_coroutine:
            # This means we're in Python 3.5 or later.
            at = self.named_generic_type('typing.Awaitable', [AnyType(TypeOfAny.special_form)])
            if is_subtype(at, typ):
                return True
        else:
            any_type = AnyType(TypeOfAny.special_form)
            gt = self.named_generic_type('typing.Generator', [any_type, any_type, any_type])
            if is_subtype(gt, typ):
                return True
        return isinstance(typ, Instance) and typ.type.fullname() == 'typing.AwaitableGenerator'

    def is_async_generator_return_type(self, typ: Type) -> bool:
        """Is `typ` a valid type for an async generator?

        True if `typ` is a supertype of AsyncGenerator.
        """
        try:
            any_type = AnyType(TypeOfAny.special_form)
            agt = self.named_generic_type('typing.AsyncGenerator', [any_type, any_type])
        except KeyError:
            # we're running on a version of typing that doesn't have AsyncGenerator yet
            return False
        return is_subtype(agt, typ)

    def get_generator_yield_type(self, return_type: Type, is_coroutine: bool) -> Type:
        """Given the declared return type of a generator (t), return the type it yields (ty)."""
        if isinstance(return_type, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=return_type)
        elif (not self.is_generator_return_type(return_type, is_coroutine)
                and not self.is_async_generator_return_type(return_type)):
            # If the function doesn't have a proper Generator (or
            # Awaitable) return type, anything is permissible.
            return AnyType(TypeOfAny.from_error)
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType(TypeOfAny.from_error)
        elif return_type.type.fullname() == 'typing.Awaitable':
            # Awaitable: ty is Any.
            return AnyType(TypeOfAny.special_form)
        elif return_type.args:
            # AwaitableGenerator, Generator, AsyncGenerator, Iterator, or Iterable; ty is args[0].
            ret_type = return_type.args[0]
            # TODO not best fix, better have dedicated yield token
            return ret_type
        else:
            # If the function's declared supertype of Generator has no type
            # parameters (i.e. is `object`), then the yielded values can't
            # be accessed so any type is acceptable.  IOW, ty is Any.
            # (However, see https://github.com/python/mypy/issues/1933)
            return AnyType(TypeOfAny.special_form)

    def get_generator_receive_type(self, return_type: Type, is_coroutine: bool) -> Type:
        """Given a declared generator return type (t), return the type its yield receives (tc)."""
        if isinstance(return_type, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=return_type)
        elif (not self.is_generator_return_type(return_type, is_coroutine)
                and not self.is_async_generator_return_type(return_type)):
            # If the function doesn't have a proper Generator (or
            # Awaitable) return type, anything is permissible.
            return AnyType(TypeOfAny.from_error)
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType(TypeOfAny.from_error)
        elif return_type.type.fullname() == 'typing.Awaitable':
            # Awaitable, AwaitableGenerator: tc is Any.
            return AnyType(TypeOfAny.special_form)
        elif (return_type.type.fullname() in ('typing.Generator', 'typing.AwaitableGenerator')
              and len(return_type.args) >= 3):
            # Generator: tc is args[1].
            return return_type.args[1]
        elif return_type.type.fullname() == 'typing.AsyncGenerator' and len(return_type.args) >= 2:
            return return_type.args[1]
        else:
            # `return_type` is a supertype of Generator, so callers won't be able to send it
            # values.  IOW, tc is None.
            return NoneTyp()

    def get_generator_return_type(self, return_type: Type, is_coroutine: bool) -> Type:
        """Given the declared return type of a generator (t), return the type it returns (tr)."""
        if isinstance(return_type, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=return_type)
        elif not self.is_generator_return_type(return_type, is_coroutine):
            # If the function doesn't have a proper Generator (or
            # Awaitable) return type, anything is permissible.
            return AnyType(TypeOfAny.from_error)
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType(TypeOfAny.from_error)
        elif return_type.type.fullname() == 'typing.Awaitable' and len(return_type.args) == 1:
            # Awaitable: tr is args[0].
            return return_type.args[0]
        elif (return_type.type.fullname() in ('typing.Generator', 'typing.AwaitableGenerator')
              and len(return_type.args) >= 3):
            # AwaitableGenerator, Generator: tr is args[2].
            return return_type.args[2]
        else:
            # Supertype of Generator (Iterator, Iterable, object): tr is any.
            return AnyType(TypeOfAny.special_form)

    def visit_func_def(self, defn: FuncDef) -> None:
        """Type check a function definition."""
        self.check_func_item(defn, name=defn.name())
        if defn.info:
            if not defn.is_dynamic():
                self.check_method_override(defn)
            self.check_inplace_operator_method(defn)
        if defn.original_def:
            # Override previous definition.
            new_type = self.function_type(defn)
            if isinstance(defn.original_def, FuncDef):
                # Function definition overrides function definition.
                if not is_same_type(new_type, self.function_type(defn.original_def)):
                    self.msg.incompatible_conditional_function_def(defn)
            else:
                # Function definition overrides a variable initialized via assignment.
                orig_type = defn.original_def.type
                if orig_type is None:
                    # XXX This can be None, as happens in
                    # test_testcheck_TypeCheckSuite.testRedefinedFunctionInTryWithElse
                    self.msg.note("Internal mypy error checking function redefinition.", defn)
                    return
                if isinstance(orig_type, PartialType):
                    if orig_type.type is None:
                        # Ah this is a partial type. Give it the type of the function.
                        var = defn.original_def
                        partial_types = self.find_partial_types(var)
                        if partial_types is not None:
                            var.type = new_type
                            del partial_types[var]
                    else:
                        # Trying to redefine something like partial empty list as function.
                        self.fail(messages.INCOMPATIBLE_REDEFINITION, defn)
                else:
                    # TODO: Update conditional type binder.
                    self.check_subtype(new_type, orig_type, defn,
                                       messages.INCOMPATIBLE_REDEFINITION,
                                       'redefinition with type',
                                       'original type')

    def check_func_item(self, defn: FuncItem,
                        type_override: Optional[CallableType] = None,
                        name: Optional[str] = None) -> None:
        """Type check a function.

        If type_override is provided, use it as the function type.
        """
        # We may be checking a function definition or an anonymous function. In
        # the first case, set up another reference with the precise type.
        fdef = None  # type: Optional[FuncDef]
        if isinstance(defn, FuncDef):
            fdef = defn

        self.dynamic_funcs.append(defn.is_dynamic() and not type_override)

        with self.errors.enter_function(fdef.name()) if fdef else nothing():
            with self.enter_partial_types():
                typ = self.function_type(defn)
                if type_override:
                    typ = type_override
                if isinstance(typ, CallableType):
                    with self.enter_attribute_inference_context():
                        self.check_func_def(defn, typ, name)
                else:
                    raise RuntimeError('Not supported')

        self.dynamic_funcs.pop()
        self.current_node_deferred = False

    @contextmanager
    def enter_attribute_inference_context(self) -> Iterator[None]:
        old_types = self.inferred_attribute_types
        self.inferred_attribute_types = {}
        yield None
        self.inferred_attribute_types = old_types

    def check_func_def(self, defn: FuncItem, typ: CallableType, name: Optional[str]) -> None:
        """Type check a function definition."""
        # Expand type variables with value restrictions to ordinary types.
        for item, typ in self.expand_typevars(defn, typ):
            old_binder = self.binder
            self.binder = ConditionalTypeBinder()
            with self.binder.top_frame_context():
                defn.expanded.append(item)

                # We may be checking a function definition or an anonymous
                # function. In the first case, set up another reference with the
                # precise type.
                if isinstance(item, FuncDef):
                    fdef = item
                    # Check if __init__ has an invalid, non-None return type.
                    if (fdef.info and fdef.name() in ('__init__', '__init_subclass__') and
                            not isinstance(typ.ret_type, NoneTyp) and
                            not self.dynamic_funcs[-1]):
                        self.fail(messages.MUST_HAVE_NONE_RETURN_TYPE.format(fdef.name()),
                                  item)

                    self.check_for_missing_annotations(fdef)
                    if 'unimported' in self.options.disallow_any:
                        if fdef.type and isinstance(fdef.type, CallableType):
                            ret_type = fdef.type.ret_type
                            if has_any_from_unimported_type(ret_type):
                                self.msg.unimported_type_becomes_any("Return type", ret_type, fdef)
                            for idx, arg_type in enumerate(fdef.type.arg_types):
                                if has_any_from_unimported_type(arg_type):
                                    prefix = "Argument {} to \"{}\"".format(idx + 1, fdef.name())
                                    self.msg.unimported_type_becomes_any(prefix, arg_type, fdef)
                    check_for_explicit_any(fdef.type, self.options, self.is_typeshed_stub,
                                           self.msg, context=fdef)

                if name:  # Special method names
                    if name in nodes.reverse_op_method_set:
                        self.check_reverse_op_method(item, typ, name)
                    elif name in ('__getattr__', '__getattribute__'):
                        self.check_getattr_method(typ, defn, name)
                    elif name == '__setattr__':
                        self.check_setattr_method(typ, defn)

                # Refuse contravariant return type variable
                if isinstance(typ.ret_type, TypeVarType):
                    if typ.ret_type.variance == CONTRAVARIANT:
                        self.fail(messages.RETURN_TYPE_CANNOT_BE_CONTRAVARIANT,
                             typ.ret_type)

                # Check that Generator functions have the appropriate return type.
                if defn.is_generator:
                    if defn.is_async_generator:
                        if not self.is_async_generator_return_type(typ.ret_type):
                            self.fail(messages.INVALID_RETURN_TYPE_FOR_ASYNC_GENERATOR, typ)
                    else:
                        if not self.is_generator_return_type(typ.ret_type, defn.is_coroutine):
                            self.fail(messages.INVALID_RETURN_TYPE_FOR_GENERATOR, typ)

                    # Python 2 generators aren't allowed to return values.
                    if (self.options.python_version[0] == 2 and
                            isinstance(typ.ret_type, Instance) and
                            typ.ret_type.type.fullname() == 'typing.Generator'):
                        if not isinstance(typ.ret_type.args[2], (NoneTyp, AnyType)):
                            self.fail(messages.INVALID_GENERATOR_RETURN_ITEM_TYPE, typ)

                # Fix the type if decorated with `@types.coroutine` or `@asyncio.coroutine`.
                if defn.is_awaitable_coroutine:
                    # Update the return type to AwaitableGenerator.
                    # (This doesn't exist in typing.py, only in typing.pyi.)
                    t = typ.ret_type
                    c = defn.is_coroutine
                    ty = self.get_generator_yield_type(t, c)
                    tc = self.get_generator_receive_type(t, c)
                    tr = self.get_generator_return_type(t, c)
                    ret_type = self.named_generic_type('typing.AwaitableGenerator',
                                                       [ty, tc, tr, t])
                    typ = typ.copy_modified(ret_type=ret_type)
                    defn.type = typ

                # Push return type.
                self.return_types.append(typ.ret_type)

                # Store argument types.
                for i in range(len(typ.arg_types)):
                    arg_type = typ.arg_types[i]

                    ref_type = self.scope.active_self_type()  # type: Optional[Type]
                    if (isinstance(defn, FuncDef) and ref_type is not None and i == 0
                            and not defn.is_static
                            and typ.arg_kinds[0] not in [nodes.ARG_STAR, nodes.ARG_STAR2]):
                        isclass = defn.is_class or defn.name() in ('__new__', '__init_subclass__')
                        if isclass:
                            ref_type = mypy.types.TypeType.make_normalized(ref_type)
                        erased = erase_to_bound(arg_type)
                        if not is_subtype_ignoring_tvars(ref_type, erased):
                            note = None
                            if typ.arg_names[i] in ['self', 'cls']:
                                if (self.options.python_version[0] < 3
                                        and is_same_type(erased, arg_type) and not isclass):
                                    msg = ("Invalid type for self, or extra argument type "
                                           "in function annotation")
                                    note = '(Hint: typically annotations omit the type for self)'
                                else:
                                    msg = ("The erased type of self '{}' "
                                           "is not a supertype of its class '{}'"
                                           ).format(erased, ref_type)
                            else:
                                msg = ("Self argument missing for a non-static method "
                                       "(or an invalid type for self)")
                            self.fail(msg, defn)
                            if note:
                                self.note(note, defn)
                        if defn.is_class and isinstance(arg_type, CallableType):
                            arg_type.is_classmethod_class = True
                    elif isinstance(arg_type, TypeVarType):
                        # Refuse covariant parameter type variables
                        # TODO: check recursively for inner type variables
                        if (
                            arg_type.variance == COVARIANT and
                            defn.name() not in ('__init__', '__new__')
                        ):
                            self.fail(messages.FUNCTION_PARAMETER_CANNOT_BE_COVARIANT, arg_type)
                    if typ.arg_kinds[i] == nodes.ARG_STAR:
                        # builtins.tuple[T] is typing.Tuple[T, ...]
                        arg_type = self.named_generic_type('builtins.tuple',
                                                           [arg_type])
                    elif typ.arg_kinds[i] == nodes.ARG_STAR2:
                        arg_type = self.named_generic_type('builtins.dict',
                                                           [self.str_type(),
                                                            arg_type])
                    item.arguments[i].variable.type = arg_type

                # Type check initialization expressions.
                for arg in item.arguments:
                    if arg.initializer is not None:
                        name = arg.variable.name()
                        msg = 'Incompatible default for '
                        if name.startswith('__tuple_arg_'):
                            msg += "tuple argument {}".format(name[12:])
                        else:
                            msg += 'argument "{}"'.format(name)
                        self.check_simple_assignment(arg.variable.type, arg.initializer,
                            context=arg, msg=msg, lvalue_name='argument', rvalue_name='default')

            # Type check body in a new scope.
            with self.binder.top_frame_context():
                with self.scope.push_function(defn):
                    self.accept(item.body)
                unreachable = self.binder.is_unreachable()

            if (self.options.warn_no_return and not unreachable):
                if (defn.is_generator or
                        is_named_instance(self.return_types[-1], 'typing.AwaitableGenerator')):
                    return_type = self.get_generator_return_type(self.return_types[-1],
                                                                 defn.is_coroutine)
                else:
                    return_type = self.return_types[-1]

                if (not isinstance(return_type, (NoneTyp, AnyType))
                        and not self.is_trivial_body(defn.body)):
                    # Control flow fell off the end of a function that was
                    # declared to return a non-None type and is not
                    # entirely pass/Ellipsis.
                    if isinstance(return_type, UninhabitedType):
                        # This is a NoReturn function
                        self.msg.note(messages.INVALID_IMPLICIT_RETURN, defn)
                    else:
                        self.msg.fail(messages.MISSING_RETURN_STATEMENT, defn)

            self.return_types.pop()

            self.binder = old_binder

    def check_for_missing_annotations(self, fdef: FuncItem) -> None:
        # Check for functions with unspecified/not fully specified types.
        def is_unannotated_any(t: Type) -> bool:
            return isinstance(t, AnyType) and t.type_of_any == TypeOfAny.unannotated

        has_explicit_annotation = (isinstance(fdef.type, CallableType)
                                   and any(not is_unannotated_any(t)
                                           for t in fdef.type.arg_types + [fdef.type.ret_type]))

        show_untyped = not self.is_typeshed_stub or self.options.warn_incomplete_stub
        check_incomplete_defs = self.options.disallow_incomplete_defs and has_explicit_annotation
        if show_untyped and (self.options.disallow_untyped_defs or check_incomplete_defs):
            if fdef.type is None and self.options.disallow_untyped_defs:
                self.fail(messages.FUNCTION_TYPE_EXPECTED, fdef)
            elif isinstance(fdef.type, CallableType):
                if is_unannotated_any(fdef.type.ret_type):
                    self.fail(messages.RETURN_TYPE_EXPECTED, fdef)
                if any(is_unannotated_any(t) for t in fdef.type.arg_types):
                    self.fail(messages.ARGUMENT_TYPE_EXPECTED, fdef)

    def is_trivial_body(self, block: Block) -> bool:
        body = block.body

        # Skip a docstring
        if (isinstance(body[0], ExpressionStmt) and
                isinstance(body[0].expr, (StrExpr, UnicodeExpr))):
            body = block.body[1:]

        if len(body) == 0:
            # There's only a docstring.
            return True
        elif len(body) > 1:
            return False
        stmt = body[0]
        return (isinstance(stmt, PassStmt) or
                (isinstance(stmt, ExpressionStmt) and
                 isinstance(stmt.expr, EllipsisExpr)))

    def check_reverse_op_method(self, defn: FuncItem, typ: CallableType,
                                method: str) -> None:
        """Check a reverse operator method such as __radd__."""

        # This used to check for some very obscure scenario.  It now
        # just decides whether it's worth calling
        # check_overlapping_op_methods().

        if method in ('__eq__', '__ne__'):
            # These are defined for all objects => can't cause trouble.
            return

        # With 'Any' or 'object' return type we are happy, since any possible
        # return value is valid.
        ret_type = typ.ret_type
        if isinstance(ret_type, AnyType):
            return
        if isinstance(ret_type, Instance):
            if ret_type.type.fullname() == 'builtins.object':
                return
        # Plausibly the method could have too few arguments, which would result
        # in an error elsewhere.
        if len(typ.arg_types) <= 2:
            # TODO check self argument kind

            # Check for the issue described above.
            arg_type = typ.arg_types[1]
            other_method = nodes.normal_from_reverse_op[method]
            if isinstance(arg_type, Instance):
                if not arg_type.type.has_readable_member(other_method):
                    return
            elif isinstance(arg_type, AnyType):
                return
            elif isinstance(arg_type, UnionType):
                if not arg_type.has_readable_member(other_method):
                    return
            else:
                return

            typ2 = self.expr_checker.analyze_external_member_access(
                other_method, arg_type, defn)
            self.check_overlapping_op_methods(
                typ, method, defn.info,
                typ2, other_method, cast(Instance, arg_type),
                defn)

    def check_overlapping_op_methods(self,
                                     reverse_type: CallableType,
                                     reverse_name: str,
                                     reverse_class: TypeInfo,
                                     forward_type: Type,
                                     forward_name: str,
                                     forward_base: Instance,
                                     context: Context) -> None:
        """Check for overlapping method and reverse method signatures.

        Assume reverse method has valid argument count and kinds.
        """

        # Reverse operator method that overlaps unsafely with the
        # forward operator method can result in type unsafety. This is
        # similar to overlapping overload variants.
        #
        # This example illustrates the issue:
        #
        #   class X: pass
        #   class A:
        #       def __add__(self, x: X) -> int:
        #           if isinstance(x, X):
        #               return 1
        #           return NotImplemented
        #   class B:
        #       def __radd__(self, x: A) -> str: return 'x'
        #   class C(X, B): pass
        #   def f(b: B) -> None:
        #       A() + b # Result is 1, even though static type seems to be str!
        #   f(C())
        #
        # The reason for the problem is that B and X are overlapping
        # types, and the return types are different. Also, if the type
        # of x in __radd__ would not be A, the methods could be
        # non-overlapping.

        for forward_item in union_items(forward_type):
            if isinstance(forward_item, CallableType):
                # TODO check argument kinds
                if len(forward_item.arg_types) < 1:
                    # Not a valid operator method -- can't succeed anyway.
                    return

                # Construct normalized function signatures corresponding to the
                # operator methods. The first argument is the left operand and the
                # second operand is the right argument -- we switch the order of
                # the arguments of the reverse method.
                forward_tweaked = CallableType(
                    [forward_base, forward_item.arg_types[0]],
                    [nodes.ARG_POS] * 2,
                    [None] * 2,
                    forward_item.ret_type,
                    forward_item.fallback,
                    name=forward_item.name)
                reverse_args = reverse_type.arg_types
                reverse_tweaked = CallableType(
                    [reverse_args[1], reverse_args[0]],
                    [nodes.ARG_POS] * 2,
                    [None] * 2,
                    reverse_type.ret_type,
                    fallback=self.named_type('builtins.function'),
                    name=reverse_type.name)

                if is_unsafe_overlapping_signatures(forward_tweaked,
                                                    reverse_tweaked):
                    self.msg.operator_method_signatures_overlap(
                        reverse_class.name(), reverse_name,
                        forward_base.type.name(), forward_name, context)
            elif isinstance(forward_item, Overloaded):
                for item in forward_item.items():
                    self.check_overlapping_op_methods(
                        reverse_type, reverse_name, reverse_class,
                        item, forward_name, forward_base, context)
            elif not isinstance(forward_item, AnyType):
                self.msg.forward_operator_not_callable(forward_name, context)

    def check_inplace_operator_method(self, defn: FuncBase) -> None:
        """Check an inplace operator method such as __iadd__.

        They cannot arbitrarily overlap with __add__.
        """
        method = defn.name()
        if method not in nodes.inplace_operator_methods:
            return
        typ = bind_self(self.function_type(defn))
        cls = defn.info
        other_method = '__' + method[3:]
        if cls.has_readable_member(other_method):
            instance = fill_typevars(cls)
            typ2 = self.expr_checker.analyze_external_member_access(
                other_method, instance, defn)
            fail = False
            if isinstance(typ2, FunctionLike):
                if not is_more_general_arg_prefix(typ, typ2):
                    fail = True
            else:
                # TODO overloads
                fail = True
            if fail:
                self.msg.signatures_incompatible(method, other_method, defn)

    def check_getattr_method(self, typ: CallableType, context: Context, name: str) -> None:
        if len(self.scope.stack) == 1:
            # module-level __getattr__
            if name == '__getattribute__':
                self.msg.fail('__getattribute__ is not valid at the module level', context)
                return
            elif name == '__getattr__' and not self.is_stub:
                self.msg.fail('__getattr__ is not valid at the module level outside a stub file',
                              context)
                return
            method_type = CallableType([self.named_type('builtins.str')],
                                       [nodes.ARG_POS],
                                       [None],
                                       AnyType(TypeOfAny.special_form),
                                       self.named_type('builtins.function'))
        else:
            method_type = CallableType([AnyType(TypeOfAny.special_form),
                                        self.named_type('builtins.str')],
                                       [nodes.ARG_POS, nodes.ARG_POS],
                                       [None, None],
                                       AnyType(TypeOfAny.special_form),
                                       self.named_type('builtins.function'))
        if not is_subtype(typ, method_type):
            self.msg.invalid_signature(typ, context)

    def check_setattr_method(self, typ: CallableType, context: Context) -> None:
        method_type = CallableType([AnyType(TypeOfAny.special_form),
                                    self.named_type('builtins.str'),
                                    AnyType(TypeOfAny.special_form)],
                                   [nodes.ARG_POS, nodes.ARG_POS, nodes.ARG_POS],
                                   [None, None, None],
                                   NoneTyp(),
                                   self.named_type('builtins.function'))
        if not is_subtype(typ, method_type):
            self.msg.invalid_signature(typ, context)

    def expand_typevars(self, defn: FuncItem,
                        typ: CallableType) -> List[Tuple[FuncItem, CallableType]]:
        # TODO use generator
        subst = []  # type: List[List[Tuple[TypeVarId, Type]]]
        tvars = typ.variables or []
        tvars = tvars[:]
        if defn.info:
            # Class type variables
            tvars += defn.info.defn.type_vars or []
        for tvar in tvars:
            if tvar.values:
                subst.append([(tvar.id, value)
                              for value in tvar.values])
        if subst:
            result = []  # type: List[Tuple[FuncItem, CallableType]]
            for substitutions in itertools.product(*subst):
                mapping = dict(substitutions)
                expanded = cast(CallableType, expand_type(typ, mapping))
                result.append((expand_func(defn, mapping), expanded))
            return result
        else:
            return [(defn, typ)]

    def check_method_override(self, defn: Union[FuncBase, Decorator]) -> None:
        """Check if function definition is compatible with base classes."""
        # Check against definitions in base classes.
        for base in defn.info.mro[1:]:
            self.check_method_or_accessor_override_for_base(defn, base)

    def check_method_or_accessor_override_for_base(self, defn: Union[FuncBase, Decorator],
                                                   base: TypeInfo) -> None:
        """Check if method definition is compatible with a base class."""
        if base:
            name = defn.name()
            if name not in ('__init__', '__new__', '__init_subclass__'):
                # Check method override
                # (__init__, __new__, __init_subclass__ are special).
                self.check_method_override_for_base_with_name(defn, name, base)
                if name in nodes.inplace_operator_methods:
                    # Figure out the name of the corresponding operator method.
                    method = '__' + name[3:]
                    # An inplace operator method such as __iadd__ might not be
                    # always introduced safely if a base class defined __add__.
                    # TODO can't come up with an example where this is
                    #      necessary; now it's "just in case"
                    self.check_method_override_for_base_with_name(defn, method,
                                                                  base)

    def check_method_override_for_base_with_name(
            self, defn: Union[FuncBase, Decorator], name: str, base: TypeInfo) -> None:
        base_attr = base.names.get(name)
        if base_attr:
            # The name of the method is defined in the base class.

            # Point errors at the 'def' line (important for backward compatibility
            # of type ignores).
            if not isinstance(defn, Decorator):
                context = defn
            else:
                context = defn.func
            # Construct the type of the overriding method.
            if isinstance(defn, FuncBase):
                typ = self.function_type(defn)  # type: Type
            else:
                assert defn.var.is_ready
                assert defn.var.type is not None
                typ = defn.var.type
            if isinstance(typ, FunctionLike) and not is_static(context):
                typ = bind_self(typ, self.scope.active_self_type())
            # Map the overridden method type to subtype context so that
            # it can be checked for compatibility.
            original_type = base_attr.type
            if original_type is None:
                if isinstance(base_attr.node, FuncDef):
                    original_type = self.function_type(base_attr.node)
                elif isinstance(base_attr.node, Decorator):
                    original_type = self.function_type(base_attr.node.func)
                else:
                    assert False, str(base_attr.node)
            if isinstance(original_type, AnyType) or isinstance(typ, AnyType):
                pass
            elif isinstance(original_type, FunctionLike) and isinstance(typ, FunctionLike):
                if (isinstance(base_attr.node, (FuncBase, Decorator))
                        and not is_static(base_attr.node)):
                    bound = bind_self(original_type, self.scope.active_self_type())
                else:
                    bound = original_type
                original = map_type_from_supertype(bound, defn.info, base)
                # Check that the types are compatible.
                # TODO overloaded signatures
                self.check_override(typ,
                                    cast(FunctionLike, original),
                                    defn.name(),
                                    name,
                                    base.name(),
                                    context)
            elif is_equivalent(original_type, typ):
                # Assume invariance for a non-callable attribute here. Note
                # that this doesn't affect read-only properties which can have
                # covariant overrides.
                #
                # TODO: Allow covariance for read-only attributes?
                pass
            else:
                self.msg.signature_incompatible_with_supertype(
                    defn.name(), name, base.name(), context)

    def check_override(self, override: FunctionLike, original: FunctionLike,
                       name: str, name_in_super: str, supertype: str,
                       node: Context) -> None:
        """Check a method override with given signatures.

        Arguments:
          override:  The signature of the overriding method.
          original:  The signature of the original supertype method.
          name:      The name of the subtype. This and the next argument are
                     only used for generating error messages.
          supertype: The name of the supertype.
        """
        # Use boolean variable to clarify code.
        fail = False
        if not is_subtype(override, original, ignore_pos_arg_names=True):
            fail = True
        elif (not isinstance(original, Overloaded) and
              isinstance(override, Overloaded) and
              name in nodes.reverse_op_methods.keys()):
            # Operator method overrides cannot introduce overloading, as
            # this could be unsafe with reverse operator methods.
            fail = True

        if isinstance(original, CallableType) and isinstance(override, CallableType):
            if (isinstance(original.definition, FuncItem) and
                    isinstance(override.definition, FuncItem)):
                if ((original.definition.is_static or original.definition.is_class) and
                        not (override.definition.is_static or override.definition.is_class)):
                    fail = True

        if fail:
            emitted_msg = False
            if (isinstance(override, CallableType) and
                    isinstance(original, CallableType) and
                    len(override.arg_types) == len(original.arg_types) and
                    override.min_args == original.min_args):
                # Give more detailed messages for the common case of both
                # signatures having the same number of arguments and no
                # overloads.

                # override might have its own generic function type
                # variables. If an argument or return type of override
                # does not have the correct subtyping relationship
                # with the original type even after these variables
                # are erased, then it is definitely an incompatibility.

                override_ids = override.type_var_ids()

                def erase_override(t: Type) -> Type:
                    return erase_typevars(t, ids_to_erase=override_ids)

                for i in range(len(override.arg_types)):
                    if not is_subtype(original.arg_types[i],
                                      erase_override(override.arg_types[i])):
                        self.msg.argument_incompatible_with_supertype(
                            i + 1, name, name_in_super, supertype, node)
                        emitted_msg = True

                if not is_subtype(erase_override(override.ret_type),
                                  original.ret_type):
                    self.msg.return_type_incompatible_with_supertype(
                        name, name_in_super, supertype, node)
                    emitted_msg = True

            if not emitted_msg:
                # Fall back to generic incompatibility message.
                self.msg.signature_incompatible_with_supertype(
                    name, name_in_super, supertype, node)

    def visit_class_def(self, defn: ClassDef) -> None:
        """Type check a class definition."""
        typ = defn.info
        if typ.is_protocol and typ.defn.type_vars:
            self.check_protocol_variance(defn)
        with self.errors.enter_type(defn.name), self.enter_partial_types():
            old_binder = self.binder
            self.binder = ConditionalTypeBinder()
            with self.binder.top_frame_context():
                with self.scope.push_class(defn.info):
                    self.accept(defn.defs)
            self.binder = old_binder
            if not defn.has_incompatible_baseclass:
                # Otherwise we've already found errors; more errors are not useful
                self.check_multiple_inheritance(typ)

    def check_protocol_variance(self, defn: ClassDef) -> None:
        """Check that protocol definition is compatible with declared
        variances of type variables.

        Note that we also prohibit declaring protocol classes as invariant
        if they are actually covariant/contravariant, since this may break
        transitivity of subtyping, see PEP 544.
        """
        info = defn.info
        object_type = Instance(info.mro[-1], [])
        tvars = info.defn.type_vars
        for i, tvar in enumerate(tvars):
            up_args = [object_type if i == j else AnyType(TypeOfAny.special_form)
                       for j, _ in enumerate(tvars)]
            down_args = [UninhabitedType() if i == j else AnyType(TypeOfAny.special_form)
                         for j, _ in enumerate(tvars)]
            up, down = Instance(info, up_args), Instance(info, down_args)
            # TODO: add advanced variance checks for recursive protocols
            if is_subtype(down, up, ignore_declared_variance=True):
                expected = COVARIANT
            elif is_subtype(up, down, ignore_declared_variance=True):
                expected = CONTRAVARIANT
            else:
                expected = INVARIANT
            if expected != tvar.variance:
                self.msg.bad_proto_variance(tvar.variance, tvar.name, expected, defn)

    def check_multiple_inheritance(self, typ: TypeInfo) -> None:
        """Check for multiple inheritance related errors."""
        if len(typ.bases) <= 1:
            # No multiple inheritance.
            return
        # Verify that inherited attributes are compatible.
        mro = typ.mro[1:]
        for i, base in enumerate(mro):
            for name in base.names:
                for base2 in mro[i + 1:]:
                    # We only need to check compatibility of attributes from classes not
                    # in a subclass relationship. For subclasses, normal (single inheritance)
                    # checks suffice (these are implemented elsewhere).
                    if name in base2.names and base2 not in base.mro:
                        self.check_compatibility(name, base, base2, typ)

    def check_compatibility(self, name: str, base1: TypeInfo,
                            base2: TypeInfo, ctx: Context) -> None:
        """Check if attribute name in base1 is compatible with base2 in multiple inheritance.

        Assume base1 comes before base2 in the MRO, and that base1 and base2 don't have
        a direct subclass relationship (i.e., the compatibility requirement only derives from
        multiple inheritance).
        """
        if name == '__init__':
            # __init__ can be incompatible -- it's a special case.
            return
        first = base1[name]
        second = base2[name]
        first_type = first.type
        if first_type is None and isinstance(first.node, FuncDef):
            first_type = self.function_type(first.node)
        second_type = second.type
        if second_type is None and isinstance(second.node, FuncDef):
            second_type = self.function_type(second.node)
        # TODO: What if some classes are generic?
        if (isinstance(first_type, FunctionLike) and
                isinstance(second_type, FunctionLike)):
            # Method override
            first_sig = bind_self(first_type)
            second_sig = bind_self(second_type)
            ok = is_subtype(first_sig, second_sig, ignore_pos_arg_names=True)
        elif first_type and second_type:
            ok = is_equivalent(first_type, second_type)
        else:
            if first_type is None:
                self.msg.cannot_determine_type_in_base(name, base1.name(), ctx)
            if second_type is None:
                self.msg.cannot_determine_type_in_base(name, base2.name(), ctx)
            ok = True
        if not ok:
            self.msg.base_class_definitions_incompatible(name, base1, base2,
                                                         ctx)

    def visit_import_from(self, node: ImportFrom) -> None:
        self.check_import(node)

    def visit_import_all(self, node: ImportAll) -> None:
        self.check_import(node)

    def visit_import(self, s: Import) -> None:
        pass

    def check_import(self, node: ImportBase) -> None:
        for assign in node.assignments:
            lvalue = assign.lvalues[0]
            lvalue_type, _, __ = self.check_lvalue(lvalue)
            if lvalue_type is None:
                # TODO: This is broken.
                lvalue_type = AnyType(TypeOfAny.special_form)
            message = '{} "{}"'.format(messages.INCOMPATIBLE_IMPORT_OF,
                                       cast(NameExpr, assign.rvalue).name)
            self.check_simple_assignment(lvalue_type, assign.rvalue, node,
                                         msg=message, lvalue_name='local name',
                                         rvalue_name='imported name')

    #
    # Statements
    #

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            self.binder.unreachable()
            return
        for s in b.body:
            if self.binder.is_unreachable():
                break
            self.accept(s)

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        """Type check an assignment statement.

        Handle all kinds of assignment statements (simple, indexed, multiple).
        """
        self.check_assignment(s.lvalues[-1], s.rvalue, s.type is None, s.new_syntax)

        if (s.type is not None and
                'unimported' in self.options.disallow_any and
                has_any_from_unimported_type(s.type)):
            if isinstance(s.lvalues[-1], TupleExpr):
                # This is a multiple assignment. Instead of figuring out which type is problematic,
                # give a generic error message.
                self.msg.unimported_type_becomes_any("A type on this line",
                                                     AnyType(TypeOfAny.special_form), s)
            else:
                self.msg.unimported_type_becomes_any("Type of variable", s.type, s)
        check_for_explicit_any(s.type, self.options, self.is_typeshed_stub, self.msg, context=s)

        if len(s.lvalues) > 1:
            # Chained assignment (e.g. x = y = ...).
            # Make sure that rvalue type will not be reinferred.
            if s.rvalue not in self.type_map:
                self.expr_checker.accept(s.rvalue)
            rvalue = self.temp_node(self.type_map[s.rvalue], s)
            for lv in s.lvalues[:-1]:
                self.check_assignment(lv, rvalue, s.type is None)

    def check_assignment(self, lvalue: Lvalue, rvalue: Expression, infer_lvalue_type: bool = True,
                         new_syntax: bool = False) -> None:
        """Type check a single assignment: lvalue = rvalue."""
        if isinstance(lvalue, TupleExpr) or isinstance(lvalue, ListExpr):
            self.check_assignment_to_multiple_lvalues(lvalue.items, rvalue, lvalue,
                                                      infer_lvalue_type)
        else:
            lvalue_type, index_lvalue, inferred = self.check_lvalue(lvalue)

            if isinstance(lvalue, NameExpr):
                if self.check_compatibility_all_supers(lvalue, lvalue_type, rvalue):
                    # We hit an error on this line; don't check for any others
                    return

            if lvalue_type:
                if isinstance(lvalue_type, PartialType) and lvalue_type.type is None:
                    # Try to infer a proper type for a variable with a partial None type.
                    rvalue_type = self.expr_checker.accept(rvalue)
                    if isinstance(rvalue_type, NoneTyp):
                        # This doesn't actually provide any additional information -- multiple
                        # None initializers preserve the partial None type.
                        return

                    if is_valid_inferred_type(rvalue_type):
                        var = lvalue_type.var
                        partial_types = self.find_partial_types(var)
                        if partial_types is not None:
                            if not self.current_node_deferred:
                                var.type = UnionType.make_simplified_union(
                                    [rvalue_type, NoneTyp()])
                            else:
                                var.type = None
                            del partial_types[var]
                            lvalue_type = var.type
                    else:
                        # Try to infer a partial type. No need to check the return value, as
                        # an error will be reported elsewhere.
                        self.infer_partial_type(lvalue_type.var, lvalue, rvalue_type)
                elif (is_literal_none(rvalue) and
                        isinstance(lvalue, NameExpr) and
                        isinstance(lvalue.node, Var) and
                        lvalue.node.is_initialized_in_class and
                        not new_syntax):
                    # Allow None's to be assigned to class variables with non-Optional types.
                    rvalue_type = lvalue_type
                elif (isinstance(lvalue, MemberExpr) and
                        lvalue.kind is None):  # Ignore member access to modules
                    instance_type = self.expr_checker.accept(lvalue.expr)
                    rvalue_type, infer_lvalue_type = self.check_member_assignment(
                        instance_type, lvalue_type, rvalue, lvalue)
                else:
                    rvalue_type = self.check_simple_assignment(lvalue_type, rvalue, lvalue)

                # Special case: only non-abstract non-protocol classes can be assigned to
                # variables with explicit type Type[A], where A is protocol or abstract.
                if (isinstance(rvalue_type, CallableType) and rvalue_type.is_type_obj() and
                        (rvalue_type.type_object().is_abstract or
                         rvalue_type.type_object().is_protocol) and
                        isinstance(lvalue_type, TypeType) and
                        isinstance(lvalue_type.item, Instance) and
                        (lvalue_type.item.type.is_abstract or
                         lvalue_type.item.type.is_protocol)):
                    self.msg.concrete_only_assign(lvalue_type, rvalue)
                    return
                if rvalue_type and infer_lvalue_type:
                    self.binder.assign_type(lvalue, rvalue_type, lvalue_type, False)
            elif index_lvalue:
                self.check_indexed_assignment(index_lvalue, rvalue, lvalue)

            if inferred:
                self.infer_variable_type(inferred, lvalue, self.expr_checker.accept(rvalue),
                                         rvalue)

    def check_compatibility_all_supers(self, lvalue: NameExpr, lvalue_type: Optional[Type],
                                       rvalue: Expression) -> bool:
        lvalue_node = lvalue.node

        # Check if we are a class variable with at least one base class
        if (isinstance(lvalue_node, Var) and
                lvalue.kind == MDEF and
                len(lvalue_node.info.bases) > 0):

            for base in lvalue_node.info.mro[1:]:
                tnode = base.names.get(lvalue_node.name())
                if tnode is not None:
                    if not self.check_compatibility_classvar_super(lvalue_node,
                                                                   base,
                                                                   tnode.node):
                        # Show only one error per variable
                        break

            for base in lvalue_node.info.mro[1:]:
                # Only check __slots__ against the 'object'
                # If a base class defines a Tuple of 3 elements, a child of
                # this class should not be allowed to define it as a Tuple of
                # anything other than 3 elements. The exception to this rule
                # is __slots__, where it is allowed for any child class to
                # redefine it.
                if lvalue_node.name() == "__slots__" and base.fullname() != "builtins.object":
                    continue

                base_type, base_node = self.lvalue_type_from_base(lvalue_node, base)

                if base_type:
                    assert base_node is not None
                    if not self.check_compatibility_super(lvalue,
                                                          lvalue_type,
                                                          rvalue,
                                                          base,
                                                          base_type,
                                                          base_node):
                        # Only show one error per variable; even if other
                        # base classes are also incompatible
                        return True
                    break
        return False

    def check_compatibility_super(self, lvalue: NameExpr, lvalue_type: Optional[Type],
                                  rvalue: Expression, base: TypeInfo, base_type: Type,
                                  base_node: Node) -> bool:
        lvalue_node = lvalue.node
        assert isinstance(lvalue_node, Var)

        # Do not check whether the rvalue is compatible if the
        # lvalue had a type defined; this is handled by other
        # parts, and all we have to worry about in that case is
        # that lvalue is compatible with the base class.
        compare_node = None
        if lvalue_type:
            compare_type = lvalue_type
            compare_node = lvalue.node
        else:
            compare_type = self.expr_checker.accept(rvalue, base_type)
            if isinstance(rvalue, NameExpr):
                compare_node = rvalue.node
                if isinstance(compare_node, Decorator):
                    compare_node = compare_node.func

        if compare_type:
            if (isinstance(base_type, CallableType) and
                    isinstance(compare_type, CallableType)):
                base_static = is_node_static(base_node)
                compare_static = is_node_static(compare_node)

                # In case compare_static is unknown, also check
                # if 'definition' is set. The most common case for
                # this is with TempNode(), where we lose all
                # information about the real rvalue node (but only get
                # the rvalue type)
                if compare_static is None and compare_type.definition:
                    compare_static = is_node_static(compare_type.definition)

                # Compare against False, as is_node_static can return None
                if base_static is False and compare_static is False:
                    # Class-level function objects and classmethods become bound
                    # methods: the former to the instance, the latter to the
                    # class
                    base_type = bind_self(base_type, self.scope.active_self_type())
                    compare_type = bind_self(compare_type, self.scope.active_self_type())

                # If we are a static method, ensure to also tell the
                # lvalue it now contains a static method
                if base_static and compare_static:
                    lvalue_node.is_staticmethod = True

            return self.check_subtype(compare_type, base_type, lvalue,
                                      messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT,
                                      'expression has type',
                                      'base class "%s" defined the type as' % base.name())
        return True

    def lvalue_type_from_base(self, expr_node: Var,
                              base: TypeInfo) -> Tuple[Optional[Type], Optional[Node]]:
        """For a NameExpr that is part of a class, walk all base classes and try
        to find the first class that defines a Type for the same name."""
        expr_name = expr_node.name()
        base_var = base.names.get(expr_name)

        if base_var:
            base_node = base_var.node
            base_type = base_var.type
            if isinstance(base_node, Decorator):
                base_node = base_node.func
                base_type = base_node.type

            if base_type:
                if not has_no_typevars(base_type):
                    self_type = self.scope.active_self_type()
                    assert self_type is not None, "Internal error: base lookup outside class"
                    if isinstance(self_type, TupleType):
                        instance = self_type.fallback
                    else:
                        instance = self_type
                    itype = map_instance_to_supertype(instance, base)
                    base_type = expand_type_by_instance(base_type, itype)

                if isinstance(base_type, CallableType) and isinstance(base_node, FuncDef):
                    # If we are a property, return the Type of the return
                    # value, not the Callable
                    if base_node.is_property:
                        base_type = base_type.ret_type

                return base_type, base_node

        return None, None

    def check_compatibility_classvar_super(self, node: Var,
                                           base: TypeInfo, base_node: Optional[Node]) -> bool:
        if not isinstance(base_node, Var):
            return True
        if node.is_classvar and not base_node.is_classvar:
            self.fail('Cannot override instance variable '
                      '(previously declared on base class "%s") '
                      'with class variable' % base.name(), node)
            return False
        elif not node.is_classvar and base_node.is_classvar:
            self.fail('Cannot override class variable '
                      '(previously declared on base class "%s") '
                      'with instance variable' % base.name(), node)
            return False
        return True

    def check_assignment_to_multiple_lvalues(self, lvalues: List[Lvalue], rvalue: Expression,
                                             context: Context,
                                             infer_lvalue_type: bool = True) -> None:
        if isinstance(rvalue, TupleExpr) or isinstance(rvalue, ListExpr):
            # Recursively go into Tuple or List expression rhs instead of
            # using the type of rhs, because this allowed more fine grained
            # control in cases like: a, b = [int, str] where rhs would get
            # type List[object]

            rvalues = rvalue.items

            if self.check_rvalue_count_in_assignment(lvalues, len(rvalues), context):
                star_index = next((i for i, lv in enumerate(lvalues) if
                                   isinstance(lv, StarExpr)), len(lvalues))

                left_lvs = lvalues[:star_index]
                star_lv = cast(StarExpr,
                               lvalues[star_index]) if star_index != len(lvalues) else None
                right_lvs = lvalues[star_index + 1:]

                left_rvs, star_rvs, right_rvs = self.split_around_star(
                    rvalues, star_index, len(lvalues))

                lr_pairs = list(zip(left_lvs, left_rvs))
                if star_lv:
                    rv_list = ListExpr(star_rvs)
                    rv_list.set_line(rvalue.get_line())
                    lr_pairs.append((star_lv.expr, rv_list))
                lr_pairs.extend(zip(right_lvs, right_rvs))

                for lv, rv in lr_pairs:
                    self.check_assignment(lv, rv, infer_lvalue_type)
        else:
            self.check_multi_assignment(lvalues, rvalue, context, infer_lvalue_type)

    def check_rvalue_count_in_assignment(self, lvalues: List[Lvalue], rvalue_count: int,
                                         context: Context) -> bool:
        if any(isinstance(lvalue, StarExpr) for lvalue in lvalues):
            if len(lvalues) - 1 > rvalue_count:
                self.msg.wrong_number_values_to_unpack(rvalue_count,
                                                       len(lvalues) - 1, context)
                return False
        elif rvalue_count != len(lvalues):
            self.msg.wrong_number_values_to_unpack(rvalue_count,
                            len(lvalues), context)
            return False
        return True

    def check_multi_assignment(self, lvalues: List[Lvalue],
                               rvalue: Expression,
                               context: Context,
                               infer_lvalue_type: bool = True,
                               rv_type: Optional[Type] = None,
                               undefined_rvalue: bool = False) -> None:
        """Check the assignment of one rvalue to a number of lvalues."""

        # Infer the type of an ordinary rvalue expression.
        # TODO: maybe elsewhere; redundant.
        rvalue_type = rv_type or self.expr_checker.accept(rvalue)

        if isinstance(rvalue_type, UnionType):
            # If this is an Optional type in non-strict Optional code, unwrap it.
            relevant_items = rvalue_type.relevant_items()
            if len(relevant_items) == 1:
                rvalue_type = relevant_items[0]

        if isinstance(rvalue_type, AnyType):
            for lv in lvalues:
                if isinstance(lv, StarExpr):
                    lv = lv.expr
                temp_node = self.temp_node(AnyType(TypeOfAny.from_another_any,
                                                   source_any=rvalue_type), context)
                self.check_assignment(lv, temp_node, infer_lvalue_type)
        elif isinstance(rvalue_type, TupleType):
            self.check_multi_assignment_from_tuple(lvalues, rvalue, rvalue_type,
                                                   context, undefined_rvalue, infer_lvalue_type)
        elif isinstance(rvalue_type, UnionType):
            self.check_multi_assignment_from_union(lvalues, rvalue, rvalue_type, context,
                                                   infer_lvalue_type)
        else:
            self.check_multi_assignment_from_iterable(lvalues, rvalue_type,
                                                      context, infer_lvalue_type)

    def check_multi_assignment_from_union(self, lvalues: List[Expression], rvalue: Expression,
                                          rvalue_type: UnionType, context: Context,
                                          infer_lvalue_type: bool) -> None:
        """Check assignment to multiple lvalue targets when rvalue type is a Union[...].
        For example:

            t: Union[Tuple[int, int], Tuple[str, str]]
            x, y = t
            reveal_type(x)  # Union[int, str]

        The idea in this case is to process the assignment for every item of the union.
        Important note: the types are collected in two places, 'union_types' contains
        inferred types for first assignments, 'assignments' contains the narrowed types
        for binder.
        """
        self.no_partial_types = True
        transposed = tuple([] for _ in
                           self.flatten_lvalues(lvalues))  # type: Tuple[List[Type], ...]
        # Notify binder that we want to defer bindings and instead collect types.
        with self.binder.accumulate_type_assignments() as assignments:
            for item in rvalue_type.items:
                # Type check the assignment separately for each union item and collect
                # the inferred lvalue types for each union item.
                self.check_multi_assignment(lvalues, rvalue, context,
                                            infer_lvalue_type=infer_lvalue_type,
                                            rv_type=item, undefined_rvalue=True)
                for t, lv in zip(transposed, self.flatten_lvalues(lvalues)):
                    t.append(self.type_map.pop(lv, AnyType(TypeOfAny.special_form)))
        union_types = tuple(UnionType.make_simplified_union(col) for col in transposed)
        for expr, items in assignments.items():
            # Bind a union of types collected in 'assignments' to every expression.
            if isinstance(expr, StarExpr):
                expr = expr.expr
            types, declared_types = zip(*items)
            self.binder.assign_type(expr,
                                    UnionType.make_simplified_union(types),
                                    UnionType.make_simplified_union(declared_types),
                                    False)
        for union, lv in zip(union_types, self.flatten_lvalues(lvalues)):
            # Properly store the inferred types.
            _1, _2, inferred = self.check_lvalue(lv)
            if inferred:
                self.set_inferred_type(inferred, lv, union)
            else:
                self.store_type(lv, union)
        self.no_partial_types = False

    def flatten_lvalues(self, lvalues: List[Expression]) -> List[Expression]:
        res = []  # type: List[Expression]
        for lv in lvalues:
            if isinstance(lv, (TupleExpr, ListExpr)):
                res.extend(self.flatten_lvalues(lv.items))
            if isinstance(lv, StarExpr):
                # Unwrap StarExpr, since it is unwrapped by other helpers.
                lv = lv.expr
            res.append(lv)
        return res

    def check_multi_assignment_from_tuple(self, lvalues: List[Lvalue], rvalue: Expression,
                                          rvalue_type: TupleType, context: Context,
                                          undefined_rvalue: bool,
                                          infer_lvalue_type: bool = True) -> None:
        if self.check_rvalue_count_in_assignment(lvalues, len(rvalue_type.items), context):
            star_index = next((i for i, lv in enumerate(lvalues)
                               if isinstance(lv, StarExpr)), len(lvalues))

            left_lvs = lvalues[:star_index]
            star_lv = cast(StarExpr, lvalues[star_index]) if star_index != len(lvalues) else None
            right_lvs = lvalues[star_index + 1:]

            if not undefined_rvalue:
                # Infer rvalue again, now in the correct type context.
                lvalue_type = self.lvalue_type_for_inference(lvalues, rvalue_type)
                reinferred_rvalue_type = self.expr_checker.accept(rvalue, lvalue_type)

                if isinstance(reinferred_rvalue_type, UnionType):
                    # If this is an Optional type in non-strict Optional code, unwrap it.
                    relevant_items = reinferred_rvalue_type.relevant_items()
                    if len(relevant_items) == 1:
                        reinferred_rvalue_type = relevant_items[0]
                if isinstance(reinferred_rvalue_type, UnionType):
                    self.check_multi_assignment_from_union(lvalues, rvalue,
                                                           reinferred_rvalue_type, context,
                                                           infer_lvalue_type)
                    return
                assert isinstance(reinferred_rvalue_type, TupleType)
                rvalue_type = reinferred_rvalue_type

            left_rv_types, star_rv_types, right_rv_types = self.split_around_star(
                rvalue_type.items, star_index, len(lvalues))

            for lv, rv_type in zip(left_lvs, left_rv_types):
                self.check_assignment(lv, self.temp_node(rv_type, context), infer_lvalue_type)
            if star_lv:
                list_expr = ListExpr([self.temp_node(rv_type, context)
                                      for rv_type in star_rv_types])
                list_expr.set_line(context.get_line())
                self.check_assignment(star_lv.expr, list_expr, infer_lvalue_type)
            for lv, rv_type in zip(right_lvs, right_rv_types):
                self.check_assignment(lv, self.temp_node(rv_type, context), infer_lvalue_type)

    def lvalue_type_for_inference(self, lvalues: List[Lvalue], rvalue_type: TupleType) -> Type:
        star_index = next((i for i, lv in enumerate(lvalues)
                           if isinstance(lv, StarExpr)), len(lvalues))
        left_lvs = lvalues[:star_index]
        star_lv = cast(StarExpr, lvalues[star_index]) if star_index != len(lvalues) else None
        right_lvs = lvalues[star_index + 1:]
        left_rv_types, star_rv_types, right_rv_types = self.split_around_star(
            rvalue_type.items, star_index, len(lvalues))

        type_parameters = []  # type: List[Type]

        def append_types_for_inference(lvs: List[Expression], rv_types: List[Type]) -> None:
            for lv, rv_type in zip(lvs, rv_types):
                sub_lvalue_type, index_expr, inferred = self.check_lvalue(lv)
                if sub_lvalue_type and not isinstance(sub_lvalue_type, PartialType):
                    type_parameters.append(sub_lvalue_type)
                else:  # index lvalue
                    # TODO Figure out more precise type context, probably
                    #      based on the type signature of the _set method.
                    type_parameters.append(rv_type)

        append_types_for_inference(left_lvs, left_rv_types)

        if star_lv:
            sub_lvalue_type, index_expr, inferred = self.check_lvalue(star_lv.expr)
            if sub_lvalue_type and not isinstance(sub_lvalue_type, PartialType):
                type_parameters.extend([sub_lvalue_type] * len(star_rv_types))
            else:  # index lvalue
                # TODO Figure out more precise type context, probably
                #      based on the type signature of the _set method.
                type_parameters.extend(star_rv_types)

        append_types_for_inference(right_lvs, right_rv_types)

        return TupleType(type_parameters, self.named_type('builtins.tuple'))

    def split_around_star(self, items: List[T], star_index: int,
                          length: int) -> Tuple[List[T], List[T], List[T]]:
        """Splits a list of items in three to match another list of length 'length'
        that contains a starred expression at 'star_index' in the following way:

        star_index = 2, length = 5 (i.e., [a,b,*,c,d]), items = [1,2,3,4,5,6,7]
        returns in: ([1,2], [3,4,5], [6,7])
        """
        nr_right_of_star = length - star_index - 1
        right_index = -nr_right_of_star if nr_right_of_star != 0 else len(items)
        left = items[:star_index]
        star = items[star_index:right_index]
        right = items[right_index:]
        return (left, star, right)

    def type_is_iterable(self, type: Type) -> bool:
        if isinstance(type, CallableType) and type.is_type_obj():
            type = type.fallback
        return (is_subtype(type, self.named_generic_type('typing.Iterable',
                                                         [AnyType(TypeOfAny.special_form)])) and
                isinstance(type, Instance))

    def check_multi_assignment_from_iterable(self, lvalues: List[Lvalue], rvalue_type: Type,
                                             context: Context,
                                             infer_lvalue_type: bool = True) -> None:
        if self.type_is_iterable(rvalue_type):
            item_type = self.iterable_item_type(cast(Instance, rvalue_type))
            for lv in lvalues:
                if isinstance(lv, StarExpr):
                    self.check_assignment(lv.expr, self.temp_node(rvalue_type, context),
                                          infer_lvalue_type)
                else:
                    self.check_assignment(lv, self.temp_node(item_type, context),
                                          infer_lvalue_type)
        else:
            self.msg.type_not_iterable(rvalue_type, context)

    def check_lvalue(self, lvalue: Lvalue) -> Tuple[Optional[Type],
                                                    Optional[IndexExpr],
                                                    Optional[Var]]:
        lvalue_type = None  # type: Optional[Type]
        index_lvalue = None  # type: Optional[IndexExpr]
        inferred = None  # type: Optional[Var]

        if self.is_definition(lvalue):
            if isinstance(lvalue, NameExpr):
                inferred = cast(Var, lvalue.node)
                assert isinstance(inferred, Var)
            else:
                assert isinstance(lvalue, MemberExpr)
                self.expr_checker.accept(lvalue.expr)
                inferred = lvalue.def_var
        elif isinstance(lvalue, IndexExpr):
            index_lvalue = lvalue
        elif isinstance(lvalue, MemberExpr):
            lvalue_type = self.expr_checker.analyze_ordinary_member_access(lvalue,
                                                                 True)
            self.store_type(lvalue, lvalue_type)
        elif isinstance(lvalue, NameExpr):
            lvalue_type = self.expr_checker.analyze_ref_expr(lvalue, lvalue=True)
            self.store_type(lvalue, lvalue_type)
        elif isinstance(lvalue, TupleExpr) or isinstance(lvalue, ListExpr):
            types = [self.check_lvalue(sub_expr)[0] or
                     # This type will be used as a context for further inference of rvalue,
                     # we put Uninhabited if there is no information available from lvalue.
                     UninhabitedType() for sub_expr in lvalue.items]
            lvalue_type = TupleType(types, self.named_type('builtins.tuple'))
        else:
            lvalue_type = self.expr_checker.accept(lvalue)

        return lvalue_type, index_lvalue, inferred

    def is_definition(self, s: Lvalue) -> bool:
        if isinstance(s, NameExpr):
            if s.is_def:
                return True
            # If the node type is not defined, this must the first assignment
            # that we process => this is a definition, even though the semantic
            # analyzer did not recognize this as such. This can arise in code
            # that uses isinstance checks, if type checking of the primary
            # definition is skipped due to an always False type check.
            node = s.node
            if isinstance(node, Var):
                return node.type is None
        elif isinstance(s, MemberExpr):
            return s.is_def
        return False

    def infer_variable_type(self, name: Var, lvalue: Lvalue,
                            init_type: Type, context: Context) -> None:
        """Infer the type of initialized variables from initializer type."""
        if isinstance(init_type, DeletedType):
            self.msg.deleted_as_rvalue(init_type, context)
        elif not is_valid_inferred_type(init_type) and not self.no_partial_types:
            # We cannot use the type of the initialization expression for full type
            # inference (it's not specific enough), but we might be able to give
            # partial type which will be made more specific later. A partial type
            # gets generated in assignment like 'x = []' where item type is not known.
            if not self.infer_partial_type(name, lvalue, init_type):
                self.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
                self.set_inference_error_fallback_type(name, lvalue, init_type, context)
        elif (isinstance(lvalue, MemberExpr) and self.inferred_attribute_types is not None
              and lvalue.def_var and lvalue.def_var in self.inferred_attribute_types
              and not is_same_type(self.inferred_attribute_types[lvalue.def_var], init_type)):
            # Multiple, inconsistent types inferred for an attribute.
            self.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
            name.type = AnyType(TypeOfAny.from_error)
        else:
            # Infer type of the target.

            # Make the type more general (strip away function names etc.).
            init_type = strip_type(init_type)

            self.set_inferred_type(name, lvalue, init_type)

    def infer_partial_type(self, name: Var, lvalue: Lvalue, init_type: Type) -> bool:
        if isinstance(init_type, NoneTyp):
            partial_type = PartialType(None, name, [init_type])
        elif isinstance(init_type, Instance):
            fullname = init_type.type.fullname()
            if (isinstance(lvalue, (NameExpr, MemberExpr)) and
                    (fullname == 'builtins.list' or
                     fullname == 'builtins.set' or
                     fullname == 'builtins.dict') and
                    all(isinstance(t, (NoneTyp, UninhabitedType)) for t in init_type.args)):
                partial_type = PartialType(init_type.type, name, init_type.args)
            else:
                return False
        else:
            return False
        self.set_inferred_type(name, lvalue, partial_type)
        self.partial_types[-1][name] = lvalue
        return True

    def set_inferred_type(self, var: Var, lvalue: Lvalue, type: Type) -> None:
        """Store inferred variable type.

        Store the type to both the variable node and the expression node that
        refers to the variable (lvalue). If var is None, do nothing.
        """
        if var and not self.current_node_deferred:
            var.type = type
            var.is_inferred = True
            if isinstance(lvalue, MemberExpr) and self.inferred_attribute_types is not None:
                # Store inferred attribute type so that we can check consistency afterwards.
                if lvalue.def_var is not None:
                    self.inferred_attribute_types[lvalue.def_var] = type
            self.store_type(lvalue, type)

    def set_inference_error_fallback_type(self, var: Var, lvalue: Lvalue, type: Type,
                                          context: Context) -> None:
        """If errors on context line are ignored, store dummy type for variable.

        If a program ignores error on type inference error, the variable should get some
        inferred type so that if can used later on in the program. Example:

          x = []  # type: ignore
          x.append(1)   # Should be ok!

        We implement this here by giving x a valid type (Any).
        """
        if context.get_line() in self.errors.ignored_lines[self.errors.file]:
            self.set_inferred_type(var, lvalue, AnyType(TypeOfAny.from_error))

    def check_simple_assignment(self, lvalue_type: Optional[Type], rvalue: Expression,
                                context: Context,
                                msg: str = messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT,
                                lvalue_name: str = 'variable',
                                rvalue_name: str = 'expression') -> Type:
        if self.is_stub and isinstance(rvalue, EllipsisExpr):
            # '...' is always a valid initializer in a stub.
            return AnyType(TypeOfAny.special_form)
        else:
            always_allow_any = lvalue_type is not None and not isinstance(lvalue_type, AnyType)
            rvalue_type = self.expr_checker.accept(rvalue, lvalue_type,
                                                   always_allow_any=always_allow_any)
            if isinstance(rvalue_type, DeletedType):
                self.msg.deleted_as_rvalue(rvalue_type, context)
            if isinstance(lvalue_type, DeletedType):
                self.msg.deleted_as_lvalue(lvalue_type, context)
            elif lvalue_type:
                self.check_subtype(rvalue_type, lvalue_type, context, msg,
                                   '{} has type'.format(rvalue_name),
                                   '{} has type'.format(lvalue_name))
            return rvalue_type

    def check_member_assignment(self, instance_type: Type, attribute_type: Type,
                                rvalue: Expression, context: Context) -> Tuple[Type, bool]:
        """Type member assigment.

        This defers to check_simple_assignment, unless the member expression
        is a descriptor, in which case this checks descriptor semantics as well.

        Return the inferred rvalue_type and whether to infer anything about the attribute type
        """
        # Descriptors don't participate in class-attribute access
        if ((isinstance(instance_type, FunctionLike) and instance_type.is_type_obj()) or
                isinstance(instance_type, TypeType)):
            rvalue_type = self.check_simple_assignment(attribute_type, rvalue, context)
            return rvalue_type, True

        if not isinstance(attribute_type, Instance):
            rvalue_type = self.check_simple_assignment(attribute_type, rvalue, context)
            return rvalue_type, True

        if not attribute_type.type.has_readable_member('__set__'):
            # If there is no __set__, we type-check that the assigned value matches
            # the return type of __get__. This doesn't match the python semantics,
            # (which allow you to override the descriptor with any value), but preserves
            # the type of accessing the attribute (even after the override).
            if attribute_type.type.has_readable_member('__get__'):
                attribute_type = self.expr_checker.analyze_descriptor_access(
                    instance_type, attribute_type, context)
            rvalue_type = self.check_simple_assignment(attribute_type, rvalue, context)
            return rvalue_type, True

        dunder_set = attribute_type.type.get_method('__set__')
        if dunder_set is None:
            self.msg.fail("{}.__set__ is not callable".format(attribute_type), context)
            return AnyType(TypeOfAny.from_error), False

        function = function_type(dunder_set, self.named_type('builtins.function'))
        bound_method = bind_self(function, attribute_type)
        typ = map_instance_to_supertype(attribute_type, dunder_set.info)
        dunder_set_type = expand_type_by_instance(bound_method, typ)

        _, inferred_dunder_set_type = self.expr_checker.check_call(
            dunder_set_type, [TempNode(instance_type), rvalue],
            [nodes.ARG_POS, nodes.ARG_POS], context)

        if not isinstance(inferred_dunder_set_type, CallableType):
            self.fail("__set__ is not callable", context)
            return AnyType(TypeOfAny.from_error), True

        if len(inferred_dunder_set_type.arg_types) < 2:
            # A message already will have been recorded in check_call
            return AnyType(TypeOfAny.from_error), False

        return inferred_dunder_set_type.arg_types[1], False

    def check_indexed_assignment(self, lvalue: IndexExpr,
                                 rvalue: Expression, context: Context) -> None:
        """Type check indexed assignment base[index] = rvalue.

        The lvalue argument is the base[index] expression.
        """
        self.try_infer_partial_type_from_indexed_assignment(lvalue, rvalue)
        basetype = self.expr_checker.accept(lvalue.base)
        if isinstance(basetype, TypedDictType):
            item_type = self.expr_checker.visit_typeddict_index_expr(basetype, lvalue.index)
            method_type = CallableType(
                arg_types=[self.named_type('builtins.str'), item_type],
                arg_kinds=[ARG_POS, ARG_POS],
                arg_names=[None, None],
                ret_type=NoneTyp(),
                fallback=self.named_type('builtins.function')
            )  # type: Type
        else:
            method_type = self.expr_checker.analyze_external_member_access(
                '__setitem__', basetype, context)
        lvalue.method_type = method_type
        self.expr_checker.check_call(method_type, [lvalue.index, rvalue],
                                     [nodes.ARG_POS, nodes.ARG_POS],
                                     context)

    def try_infer_partial_type_from_indexed_assignment(
            self, lvalue: IndexExpr, rvalue: Expression) -> None:
        # TODO: Should we share some of this with try_infer_partial_type?
        if isinstance(lvalue.base, RefExpr) and isinstance(lvalue.base.node, Var):
            var = lvalue.base.node
            if isinstance(var.type, PartialType):
                type_type = var.type.type
                if type_type is None:
                    return  # The partial type is None.
                partial_types = self.find_partial_types(var)
                if partial_types is None:
                    return
                typename = type_type.fullname()
                if typename == 'builtins.dict':
                    # TODO: Don't infer things twice.
                    key_type = self.expr_checker.accept(lvalue.index)
                    value_type = self.expr_checker.accept(rvalue)
                    full_key_type = UnionType.make_simplified_union(
                        [key_type, var.type.inner_types[0]])
                    full_value_type = UnionType.make_simplified_union(
                        [value_type, var.type.inner_types[1]])
                    if (is_valid_inferred_type(full_key_type) and
                            is_valid_inferred_type(full_value_type)):
                        if not self.current_node_deferred:
                            var.type = self.named_generic_type('builtins.dict',
                                                               [full_key_type, full_value_type])
                            del partial_types[var]

    def visit_expression_stmt(self, s: ExpressionStmt) -> None:
        self.expr_checker.accept(s.expr, allow_none_return=True, always_allow_any=True)

    def visit_return_stmt(self, s: ReturnStmt) -> None:
        """Type check a return statement."""
        self.check_return_stmt(s)
        self.binder.unreachable()

    def check_return_stmt(self, s: ReturnStmt) -> None:
        defn = self.scope.top_function()
        if defn is not None:
            if defn.is_generator:
                return_type = self.get_generator_return_type(self.return_types[-1],
                                                             defn.is_coroutine)
            else:
                return_type = self.return_types[-1]

            if isinstance(return_type, UninhabitedType):
                self.fail(messages.NO_RETURN_EXPECTED, s)
                return

            if s.expr:
                is_lambda = isinstance(self.scope.top_function(), LambdaExpr)
                declared_none_return = isinstance(return_type, NoneTyp)
                declared_any_return = isinstance(return_type, AnyType)

                # This controls whether or not we allow a function call that
                # returns None as the expression of this return statement.
                # E.g. `return f()` for some `f` that returns None.  We allow
                # this only if we're in a lambda or in a function that returns
                # `None` or `Any`.
                allow_none_func_call = is_lambda or declared_none_return or declared_any_return

                # Return with a value.
                typ = self.expr_checker.accept(s.expr,
                                               return_type,
                                               allow_none_return=allow_none_func_call)

                if defn.is_async_generator:
                    self.fail("'return' with value in async generator is not allowed", s)
                    return
                # Returning a value of type Any is always fine.
                if isinstance(typ, AnyType):
                    # (Unless you asked to be warned in that case, and the
                    # function is not declared to return Any)
                    if (self.options.warn_return_any and
                            not is_proper_subtype(AnyType(TypeOfAny.special_form), return_type)):
                        self.msg.incorrectly_returning_any(return_type, s)
                    return

                # Disallow return expressions in functions declared to return
                # None, subject to two exceptions below.
                if declared_none_return:
                    # Lambdas are allowed to have None returns.
                    # Functions returning a value of type None are allowed to have a None return.
                    if is_lambda or isinstance(typ, NoneTyp):
                        return
                    self.fail(messages.NO_RETURN_VALUE_EXPECTED, s)
                else:
                    self.check_subtype(
                        subtype_label='got',
                        subtype=typ,
                        supertype_label='expected',
                        supertype=return_type,
                        context=s,
                        msg=messages.INCOMPATIBLE_RETURN_VALUE_TYPE)
            else:
                # Empty returns are valid in Generators with Any typed returns, but not in
                # coroutines.
                if (defn.is_generator and not defn.is_coroutine and
                        isinstance(return_type, AnyType)):
                    return

                if isinstance(return_type, (NoneTyp, AnyType)):
                    return

                if self.in_checked_function():
                    self.fail(messages.RETURN_VALUE_EXPECTED, s)

    def visit_if_stmt(self, s: IfStmt) -> None:
        """Type check an if statement."""
        # This frame records the knowledge from previous if/elif clauses not being taken.
        # Fall-through to the original frame is handled explicitly in each block.
        with self.binder.frame_context(can_skip=False, fall_through=0):
            for e, b in zip(s.expr, s.body):
                t = self.expr_checker.accept(e)

                if isinstance(t, DeletedType):
                    self.msg.deleted_as_rvalue(t, s)

                if self.options.strict_boolean:
                    is_bool = isinstance(t, Instance) and t.type.fullname() == 'builtins.bool'
                    if not (is_bool or isinstance(t, AnyType)):
                        self.fail(messages.NON_BOOLEAN_IN_CONDITIONAL, e)

                if_map, else_map = self.find_isinstance_check(e)

                # XXX Issue a warning if condition is always False?
                with self.binder.frame_context(can_skip=True, fall_through=2):
                    self.push_type_map(if_map)
                    self.accept(b)

                # XXX Issue a warning if condition is always True?
                self.push_type_map(else_map)

            with self.binder.frame_context(can_skip=False, fall_through=2):
                if s.else_body:
                    self.accept(s.else_body)

    def visit_while_stmt(self, s: WhileStmt) -> None:
        """Type check a while statement."""
        if_stmt = IfStmt([s.expr], [s.body], None)
        if_stmt.set_line(s.get_line(), s.get_column())
        self.accept_loop(if_stmt, s.else_body,
                         exit_condition=s.expr)

    def visit_operator_assignment_stmt(self,
                                       s: OperatorAssignmentStmt) -> None:
        """Type check an operator assignment statement, e.g. x += 1."""
        lvalue_type = self.expr_checker.accept(s.lvalue)
        inplace, method = infer_operator_assignment_method(lvalue_type, s.op)
        if inplace:
            # There is __ifoo__, treat as x = x.__ifoo__(y)
            rvalue_type, method_type = self.expr_checker.check_op(
                method, lvalue_type, s.rvalue, s)
            if not is_subtype(rvalue_type, lvalue_type):
                self.msg.incompatible_operator_assignment(s.op, s)
        else:
            # There is no __ifoo__, treat as x = x <foo> y
            expr = OpExpr(s.op, s.lvalue, s.rvalue)
            expr.set_line(s)
            self.check_assignment(lvalue=s.lvalue, rvalue=expr,
                                  infer_lvalue_type=True, new_syntax=False)

    def visit_assert_stmt(self, s: AssertStmt) -> None:
        self.expr_checker.accept(s.expr)

        if s.msg is not None:
            self.expr_checker.accept(s.msg)

        if isinstance(s.expr, TupleExpr) and len(s.expr.items) > 0:
            self.warn(messages.MALFORMED_ASSERT, s)

        # If this is asserting some isinstance check, bind that type in the following code
        true_map, _ = self.find_isinstance_check(s.expr)
        self.push_type_map(true_map)

    def visit_raise_stmt(self, s: RaiseStmt) -> None:
        """Type check a raise statement."""
        if s.expr:
            self.type_check_raise(s.expr, s)
        if s.from_expr:
            self.type_check_raise(s.from_expr, s, True)
        self.binder.unreachable()

    def type_check_raise(self, e: Expression, s: RaiseStmt,
                         optional: bool = False) -> None:
        typ = self.expr_checker.accept(e)
        if isinstance(typ, FunctionLike):
            if typ.is_type_obj():
                # Cases like "raise/from ExceptionClass".
                typeinfo = typ.type_object()
                base = self.lookup_typeinfo('builtins.BaseException')
                if base in typeinfo.mro or typeinfo.fallback_to_any:
                    # Good!
                    return
                # Else fall back to the checks below (which will fail).
        if isinstance(typ, TupleType) and self.options.python_version[0] == 2:
            # allow `raise type, value, traceback`
            # https://docs.python.org/2/reference/simple_stmts.html#the-raise-statement
            # TODO: Also check tuple item types.
            if len(typ.items) in (2, 3):
                return
        if isinstance(typ, Instance) and typ.type.fallback_to_any:
            # OK!
            return
        expected_type = self.named_type('builtins.BaseException')  # type: Type
        if optional:
            expected_type = UnionType([expected_type, NoneTyp()])
        self.check_subtype(typ, expected_type, s, messages.INVALID_EXCEPTION)

    def visit_try_stmt(self, s: TryStmt) -> None:
        """Type check a try statement."""
        # Our enclosing frame will get the result if the try/except falls through.
        # This one gets all possible states after the try block exited abnormally
        # (by exception, return, break, etc.)
        with self.binder.frame_context(can_skip=False, fall_through=0):
            # Not only might the body of the try statement exit
            # abnormally, but so might an exception handler or else
            # clause. The finally clause runs in *all* cases, so we
            # need an outer try frame to catch all intermediate states
            # in case an exception is raised during an except or else
            # clause. As an optimization, only create the outer try
            # frame when there actually is a finally clause.
            self.visit_try_without_finally(s, try_frame=bool(s.finally_body))
            if s.finally_body:
                # First we check finally_body is type safe on all abnormal exit paths
                self.accept(s.finally_body)

        if s.finally_body:
            # Then we try again for the more restricted set of options
            # that can fall through. (Why do we need to check the
            # finally clause twice? Depending on whether the finally
            # clause was reached by the try clause falling off the end
            # or exiting abnormally, after completing the finally clause
            # either flow will continue to after the entire try statement
            # or the exception/return/etc. will be processed and control
            # flow will escape. We need to check that the finally clause
            # type checks in both contexts, but only the resulting types
            # from the latter context affect the type state in the code
            # that follows the try statement.)
            self.accept(s.finally_body)

    def visit_try_without_finally(self, s: TryStmt, try_frame: bool) -> None:
        """Type check a try statement, ignoring the finally block.

        On entry, the top frame should receive all flow that exits the
        try block abnormally (i.e., such that the else block does not
        execute), and its parent should receive all flow that exits
        the try block normally.
        """
        # This frame will run the else block if the try fell through.
        # In that case, control flow continues to the parent of what
        # was the top frame on entry.
        with self.binder.frame_context(can_skip=False, fall_through=2, try_frame=try_frame):
            # This frame receives exit via exception, and runs exception handlers
            with self.binder.frame_context(can_skip=False, fall_through=2):
                # Finally, the body of the try statement
                with self.binder.frame_context(can_skip=False, fall_through=2, try_frame=True):
                    self.accept(s.body)
                for i in range(len(s.handlers)):
                    with self.binder.frame_context(can_skip=True, fall_through=4):
                        typ = s.types[i]
                        if typ:
                            t = self.check_except_handler_test(typ)
                            var = s.vars[i]
                            if var:
                                # To support local variables, we make this a definition line,
                                # causing assignment to set the variable's type.
                                var.is_def = True
                                # We also temporarily set current_node_deferred to False to
                                # make sure the inference happens.
                                # TODO: Use a better solution, e.g. a
                                # separate Var for each except block.
                                am_deferring = self.current_node_deferred
                                self.current_node_deferred = False
                                self.check_assignment(var, self.temp_node(t, var))
                                self.current_node_deferred = am_deferring
                        self.accept(s.handlers[i])
                        var = s.vars[i]
                        if var:
                            # Exception variables are deleted in python 3 but not python 2.
                            # But, since it's bad form in python 2 and the type checking
                            # wouldn't work very well, we delete it anyway.

                            # Unfortunately, this doesn't let us detect usage before the
                            # try/except block.
                            if self.options.python_version[0] >= 3:
                                source = var.name
                            else:
                                source = ('(exception variable "{}", which we do not '
                                          'accept outside except: blocks even in '
                                          'python 2)'.format(var.name))
                            cast(Var, var.node).type = DeletedType(source=source)
                            self.binder.cleanse(var)
            if s.else_body:
                self.accept(s.else_body)

    def check_except_handler_test(self, n: Expression) -> Type:
        """Type check an exception handler test clause."""
        typ = self.expr_checker.accept(n)

        all_types = []  # type: List[Type]
        test_types = self.get_types_from_except_handler(typ, n)

        for ttype in test_types:
            if isinstance(ttype, AnyType):
                all_types.append(ttype)
                continue

            if isinstance(ttype, FunctionLike):
                item = ttype.items()[0]
                if not item.is_type_obj():
                    self.fail(messages.INVALID_EXCEPTION_TYPE, n)
                    return AnyType(TypeOfAny.from_error)
                exc_type = item.ret_type
            elif isinstance(ttype, TypeType):
                exc_type = ttype.item
            else:
                self.fail(messages.INVALID_EXCEPTION_TYPE, n)
                return AnyType(TypeOfAny.from_error)

            if not is_subtype(exc_type, self.named_type('builtins.BaseException')):
                self.fail(messages.INVALID_EXCEPTION_TYPE, n)
                return AnyType(TypeOfAny.from_error)

            all_types.append(exc_type)

        return UnionType.make_simplified_union(all_types)

    def get_types_from_except_handler(self, typ: Type, n: Expression) -> List[Type]:
        """Helper for check_except_handler_test to retrieve handler types."""
        if isinstance(typ, TupleType):
            return typ.items
        elif isinstance(typ, UnionType):
            return [
                union_typ
                for item in typ.relevant_items()
                for union_typ in self.get_types_from_except_handler(item, n)
            ]
        elif isinstance(typ, Instance) and is_named_instance(typ, 'builtins.tuple'):
            # variadic tuple
            return [typ.args[0]]
        else:
            return [typ]

    def visit_for_stmt(self, s: ForStmt) -> None:
        """Type check a for statement."""
        if s.is_async:
            item_type = self.analyze_async_iterable_item_type(s.expr)
        else:
            item_type = self.analyze_iterable_item_type(s.expr)
        self.analyze_index_variables(s.index, item_type, s.index_type is None, s)
        self.accept_loop(s.body, s.else_body)

    def analyze_async_iterable_item_type(self, expr: Expression) -> Type:
        """Analyse async iterable expression and return iterator item type."""
        echk = self.expr_checker
        iterable = echk.accept(expr)

        self.check_subtype(iterable,
                           self.named_generic_type('typing.AsyncIterable',
                                                   [AnyType(TypeOfAny.special_form)]),
                           expr, messages.ASYNC_ITERABLE_EXPECTED)

        method = echk.analyze_external_member_access('__aiter__', iterable, expr)
        iterator = echk.check_call(method, [], [], expr)[0]
        method = echk.analyze_external_member_access('__anext__', iterator, expr)
        awaitable = echk.check_call(method, [], [], expr)[0]
        return echk.check_awaitable_expr(awaitable, expr,
                                         messages.INCOMPATIBLE_TYPES_IN_ASYNC_FOR)

    def analyze_iterable_item_type(self, expr: Expression) -> Type:
        """Analyse iterable expression and return iterator item type."""
        echk = self.expr_checker
        iterable = echk.accept(expr)

        if isinstance(iterable, TupleType):
            joined = UninhabitedType()  # type: Type
            for item in iterable.items:
                joined = join_types(joined, item)
            return joined
        else:
            # Non-tuple iterable.
            self.check_subtype(iterable,
                               self.named_generic_type('typing.Iterable',
                                                       [AnyType(TypeOfAny.special_form)]),
                               expr, messages.ITERABLE_EXPECTED)

            method = echk.analyze_external_member_access('__iter__', iterable,
                                                         expr)
            iterator = echk.check_call(method, [], [], expr)[0]
            if self.options.python_version[0] >= 3:
                nextmethod = '__next__'
            else:
                nextmethod = 'next'
            method = echk.analyze_external_member_access(nextmethod, iterator,
                                                         expr)
            return echk.check_call(method, [], [], expr)[0]

    def analyze_index_variables(self, index: Expression, item_type: Type,
                                infer_lvalue_type: bool, context: Context) -> None:
        """Type check or infer for loop or list comprehension index vars."""
        self.check_assignment(index, self.temp_node(item_type, context), infer_lvalue_type)

    def visit_del_stmt(self, s: DelStmt) -> None:
        if isinstance(s.expr, IndexExpr):
            e = s.expr
            m = MemberExpr(e.base, '__delitem__')
            m.line = s.line
            c = CallExpr(m, [e.index], [nodes.ARG_POS], [None])
            c.line = s.line
            self.expr_checker.accept(c, allow_none_return=True)
        else:
            s.expr.accept(self.expr_checker)
            for elt in flatten(s.expr):
                if isinstance(elt, NameExpr):
                    self.binder.assign_type(elt, DeletedType(source=elt.name),
                                            get_declaration(elt), False)

    def visit_decorator(self, e: Decorator) -> None:
        for d in e.decorators:
            if isinstance(d, RefExpr):
                if d.fullname == 'typing.no_type_check':
                    e.var.type = AnyType(TypeOfAny.special_form)
                    e.var.is_ready = True
                    return

        self.check_func_item(e.func, name=e.func.name())

        # Process decorators from the inside out to determine decorated signature, which
        # may be different from the declared signature.
        sig = self.function_type(e.func)  # type: Type
        for d in reversed(e.decorators):
            if refers_to_fullname(d, 'typing.overload'):
                self.fail('Single overload definition, multiple required', e)
                continue
            dec = self.expr_checker.accept(d)
            temp = self.temp_node(sig)
            fullname = None
            if isinstance(d, RefExpr):
                fullname = d.fullname
            self.check_for_untyped_decorator(e.func, dec, d)
            sig, t2 = self.expr_checker.check_call(dec, [temp],
                                                   [nodes.ARG_POS], e,
                                                   callable_name=fullname)
        self.check_untyped_after_decorator(sig, e.func)
        sig = cast(FunctionLike, sig)
        sig = set_callable_name(sig, e.func)
        e.var.type = sig
        e.var.is_ready = True
        if e.func.is_property:
            self.check_incompatible_property_override(e)
        if e.func.info and not e.func.is_dynamic():
            self.check_method_override(e)

    def check_for_untyped_decorator(self,
                                    func: FuncDef,
                                    dec_type: Type,
                                    dec_expr: Expression) -> None:
        if (self.options.disallow_untyped_decorators and
                is_typed_callable(func.type) and
                is_untyped_decorator(dec_type)):
            self.msg.typed_function_untyped_decorator(func.name(), dec_expr)

    def check_incompatible_property_override(self, e: Decorator) -> None:
        if not e.var.is_settable_property and e.func.info is not None:
            name = e.func.name()
            for base in e.func.info.mro[1:]:
                base_attr = base.names.get(name)
                if not base_attr:
                    continue
                if (isinstance(base_attr.node, OverloadedFuncDef) and
                        base_attr.node.is_property and
                        cast(Decorator,
                             base_attr.node.items[0]).var.is_settable_property):
                    self.fail(messages.READ_ONLY_PROPERTY_OVERRIDES_READ_WRITE, e)

    def visit_with_stmt(self, s: WithStmt) -> None:
        for expr, target in zip(s.expr, s.target):
            if s.is_async:
                self.check_async_with_item(expr, target, s.target_type is None)
            else:
                self.check_with_item(expr, target, s.target_type is None)
        self.accept(s.body)

    def check_untyped_after_decorator(self, typ: Type, func: FuncDef) -> None:
        if 'decorated' not in self.options.disallow_any or self.is_stub:
            return

        if mypy.checkexpr.has_any_type(typ):
            self.msg.untyped_decorated_function(typ, func)

    def check_async_with_item(self, expr: Expression, target: Optional[Expression],
                              infer_lvalue_type: bool) -> None:
        echk = self.expr_checker
        ctx = echk.accept(expr)
        enter = echk.analyze_external_member_access('__aenter__', ctx, expr)
        obj = echk.check_call(enter, [], [], expr)[0]
        obj = echk.check_awaitable_expr(
            obj, expr, messages.INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AENTER)
        if target:
            self.check_assignment(target, self.temp_node(obj, expr), infer_lvalue_type)
        exit = echk.analyze_external_member_access('__aexit__', ctx, expr)
        arg = self.temp_node(AnyType(TypeOfAny.special_form), expr)
        res = echk.check_call(exit, [arg] * 3, [nodes.ARG_POS] * 3, expr)[0]
        echk.check_awaitable_expr(
            res, expr, messages.INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AEXIT)

    def check_with_item(self, expr: Expression, target: Optional[Expression],
                        infer_lvalue_type: bool) -> None:
        echk = self.expr_checker
        ctx = echk.accept(expr)
        enter = echk.analyze_external_member_access('__enter__', ctx, expr)
        obj = echk.check_call(enter, [], [], expr)[0]
        if target:
            self.check_assignment(target, self.temp_node(obj, expr), infer_lvalue_type)
        exit = echk.analyze_external_member_access('__exit__', ctx, expr)
        arg = self.temp_node(AnyType(TypeOfAny.special_form), expr)
        echk.check_call(exit, [arg] * 3, [nodes.ARG_POS] * 3, expr)

    def visit_print_stmt(self, s: PrintStmt) -> None:
        for arg in s.args:
            self.expr_checker.accept(arg)
        if s.target:
            target_type = self.expr_checker.accept(s.target)
            if not isinstance(target_type, NoneTyp):
                # TODO: Also verify the type of 'write'.
                self.expr_checker.analyze_external_member_access('write', target_type, s.target)

    def visit_break_stmt(self, s: BreakStmt) -> None:
        self.binder.handle_break()

    def visit_continue_stmt(self, s: ContinueStmt) -> None:
        self.binder.handle_continue()
        return None

    #
    # Helpers
    #

    def check_subtype(self, subtype: Type, supertype: Type, context: Context,
                      msg: str = messages.INCOMPATIBLE_TYPES,
                      subtype_label: Optional[str] = None,
                      supertype_label: Optional[str] = None) -> bool:
        """Generate an error if the subtype is not compatible with
        supertype."""
        if is_subtype(subtype, supertype):
            return True
        else:
            if self.should_suppress_optional_error([subtype]):
                return False
            extra_info = []  # type: List[str]
            note_msg = ''
            if subtype_label is not None or supertype_label is not None:
                subtype_str, supertype_str = self.msg.format_distinctly(subtype, supertype)
                if subtype_label is not None:
                    extra_info.append(subtype_label + ' ' + subtype_str)
                if supertype_label is not None:
                    extra_info.append(supertype_label + ' ' + supertype_str)
                note_msg = make_inferred_type_note(context, subtype,
                                                   supertype, supertype_str)
            if extra_info:
                msg += ' (' + ', '.join(extra_info) + ')'
            self.fail(msg, context)
            if note_msg:
                self.note(note_msg, context)
            if (isinstance(supertype, Instance) and supertype.type.is_protocol and
                    isinstance(subtype, (Instance, TupleType, TypedDictType))):
                self.msg.report_protocol_problems(subtype, supertype, context)
            if isinstance(supertype, CallableType) and isinstance(subtype, Instance):
                call = find_member('__call__', subtype, subtype)
                if call:
                    self.msg.note_call(subtype, call, context)
            return False

    def contains_none(self, t: Type) -> bool:
        return (
            isinstance(t, NoneTyp) or
            (isinstance(t, UnionType) and any(self.contains_none(ut) for ut in t.items)) or
            (isinstance(t, TupleType) and any(self.contains_none(tt) for tt in t.items)) or
            (isinstance(t, Instance) and bool(t.args)
             and any(self.contains_none(it) for it in t.args))
        )

    def should_suppress_optional_error(self, related_types: List[Type]) -> bool:
        return self.suppress_none_errors and any(self.contains_none(t) for t in related_types)

    def named_type(self, name: str) -> Instance:
        """Return an instance type with type given by the name and no
        type arguments. For example, named_type('builtins.object')
        produces the object type.
        """
        # Assume that the name refers to a type.
        sym = self.lookup_qualified(name)
        node = sym.node
        assert isinstance(node, TypeInfo)
        any_type = AnyType(TypeOfAny.from_omitted_generics)
        return Instance(node, [any_type] * len(node.defn.type_vars))

    def named_generic_type(self, name: str, args: List[Type]) -> Instance:
        """Return an instance with the given name and type arguments.

        Assume that the number of arguments is correct.  Assume that
        the name refers to a compatible generic type.
        """
        info = self.lookup_typeinfo(name)
        # TODO: assert len(args) == len(info.defn.type_vars)
        return Instance(info, args)

    def lookup_typeinfo(self, fullname: str) -> TypeInfo:
        # Assume that the name refers to a class.
        sym = self.lookup_qualified(fullname)
        node = sym.node
        assert isinstance(node, TypeInfo)
        return node

    def type_type(self) -> Instance:
        """Return instance type 'type'."""
        return self.named_type('builtins.type')

    def str_type(self) -> Instance:
        """Return instance type 'str'."""
        return self.named_type('builtins.str')

    def store_type(self, node: Expression, typ: Type) -> None:
        """Store the type of a node in the type map."""
        self.type_map[node] = typ

    def in_checked_function(self) -> bool:
        """Should we type-check the current function?

        - Yes if --check-untyped-defs is set.
        - Yes outside functions.
        - Yes in annotated functions.
        - No otherwise.
        """
        return (self.options.check_untyped_defs
                or not self.dynamic_funcs
                or not self.dynamic_funcs[-1])

    def lookup(self, name: str, kind: int) -> SymbolTableNode:
        """Look up a definition from the symbol table with the given name.
        TODO remove kind argument
        """
        if name in self.globals:
            return self.globals[name]
        else:
            b = self.globals.get('__builtins__', None)
            if b:
                table = cast(MypyFile, b.node).names
                if name in table:
                    return table[name]
            raise KeyError('Failed lookup: {}'.format(name))

    def lookup_qualified(self, name: str) -> SymbolTableNode:
        if '.' not in name:
            return self.lookup(name, GDEF)  # FIX kind
        else:
            parts = name.split('.')
            n = self.modules[parts[0]]
            for i in range(1, len(parts) - 1):
                sym = n.names.get(parts[i])
                assert sym is not None, "Internal error: attempted lookup of unknown name"
                n = cast(MypyFile, sym.node)
            last = parts[-1]
            if last in n.names:
                return n.names[last]
            elif len(parts) == 2 and parts[0] == 'builtins':
                raise KeyError("Could not find builtin symbol '{}'. (Are you running a "
                               "test case? If so, make sure to include a fixture that "
                               "defines this symbol.)".format(last))
            else:
                msg = "Failed qualified lookup: '{}' (fullname = '{}')."
                raise KeyError(msg.format(last, name))

    @contextmanager
    def enter_partial_types(self) -> Iterator[None]:
        """Enter a new scope for collecting partial types.

        Also report errors for variables which still have partial
        types, i.e. we couldn't infer a complete type.
        """
        self.partial_types.append({})
        yield

        partial_types = self.partial_types.pop()
        if not self.current_node_deferred:
            for var, context in partial_types.items():
                if isinstance(var.type, PartialType) and var.type.type is None:
                    # None partial type: assume variable is intended to have type None
                    var.type = NoneTyp()
                else:
                    if var not in self.partial_reported:
                        self.msg.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
                        self.partial_reported.add(var)
                    var.type = AnyType(TypeOfAny.from_error)

    def find_partial_types(self, var: Var) -> Optional[Dict[Var, Context]]:
        for partial_types in reversed(self.partial_types):
            if var in partial_types:
                return partial_types
        return None

    def temp_node(self, t: Type, context: Optional[Context] = None) -> TempNode:
        """Create a temporary node with the given, fixed type."""
        temp = TempNode(t)
        if context:
            temp.set_line(context.get_line())
        return temp

    def fail(self, msg: str, context: Context) -> None:
        """Produce an error message."""
        self.msg.fail(msg, context)

    def warn(self, msg: str, context: Context) -> None:
        """Produce a warning message."""
        self.msg.warn(msg, context)

    def note(self, msg: str, context: Context, offset: int = 0) -> None:
        """Produce a note."""
        self.msg.note(msg, context, offset=offset)

    def iterable_item_type(self, instance: Instance) -> Type:
        iterable = map_instance_to_supertype(
            instance,
            self.lookup_typeinfo('typing.Iterable'))
        item_type = iterable.args[0]
        if not isinstance(item_type, AnyType):
            # This relies on 'map_instance_to_supertype' returning 'Iterable[Any]'
            # in case there is no explicit base class.
            return item_type
        # Try also structural typing.
        iter_type = find_member('__iter__', instance, instance)
        if (iter_type and isinstance(iter_type, CallableType) and
                isinstance(iter_type.ret_type, Instance)):
            iterator = map_instance_to_supertype(iter_type.ret_type,
                                                 self.lookup_typeinfo('typing.Iterator'))
            item_type = iterator.args[0]
        return item_type

    def function_type(self, func: FuncBase) -> FunctionLike:
        return function_type(func, self.named_type('builtins.function'))

    # TODO: These next two functions should refer to TypeMap below
    def find_isinstance_check(self, n: Expression) -> Tuple[Optional[Dict[Expression, Type]],
                                                            Optional[Dict[Expression, Type]]]:
        return find_isinstance_check(n, self.type_map)

    def push_type_map(self, type_map: Optional[Dict[Expression, Type]]) -> None:
        if type_map is None:
            self.binder.unreachable()
        else:
            for expr, type in type_map.items():
                self.binder.put(expr, type)

# Data structure returned by find_isinstance_check representing
# information learned from the truth or falsehood of a condition.  The
# dict maps nodes representing expressions like 'a[0].x' to their
# refined types under the assumption that the condition has a
# particular truth value. A value of None means that the condition can
# never have that truth value.

# NB: The keys of this dict are nodes in the original source program,
# which are compared by reference equality--effectively, being *the
# same* expression of the program, not just two identical expressions
# (such as two references to the same variable). TODO: it would
# probably be better to have the dict keyed by the nodes' literal_hash
# field instead.


TypeMap = Optional[Dict[Expression, Type]]

# An object that represents either a precise type or a type with an upper bound;
# it is important for correct type inference with isinstance.
TypeRange = NamedTuple(
    'TypeRange',
    [
        ('item', Type),
        ('is_upper_bound', bool),  # False => precise type
    ])


def conditional_type_map(expr: Expression,
                         current_type: Optional[Type],
                         proposed_type_ranges: Optional[List[TypeRange]],
                         ) -> Tuple[TypeMap, TypeMap]:
    """Takes in an expression, the current type of the expression, and a
    proposed type of that expression.

    Returns a 2-tuple: The first element is a map from the expression to
    the proposed type, if the expression can be the proposed type.  The
    second element is a map from the expression to the type it would hold
    if it was not the proposed type, if any. None means bot, {} means top"""
    if proposed_type_ranges:
        if len(proposed_type_ranges) == 1:
            proposed_type = proposed_type_ranges[0].item  # Union with a single type breaks tests
        else:
            proposed_type = UnionType([type_range.item for type_range in proposed_type_ranges])
        if current_type:
            if (not any(type_range.is_upper_bound for type_range in proposed_type_ranges)
               and is_proper_subtype(current_type, proposed_type)):
                # Expression is always of one of the types in proposed_type_ranges
                return {}, None
            elif not is_overlapping_types(current_type, proposed_type):
                # Expression is never of any type in proposed_type_ranges
                return None, {}
            else:
                # we can only restrict when the type is precise, not bounded
                proposed_precise_type = UnionType([type_range.item
                                          for type_range in proposed_type_ranges
                                          if not type_range.is_upper_bound])
                remaining_type = restrict_subtype_away(current_type, proposed_precise_type)
                return {expr: proposed_type}, {expr: remaining_type}
        else:
            return {expr: proposed_type}, {}
    else:
        # An isinstance check, but we don't understand the type
        return {}, {}


def partition_by_callable(type: Type) -> Tuple[List[Type], List[Type]]:
    """Takes in a type and partitions that type into callable subtypes and
    uncallable subtypes.

    Thus, given:
    `callables, uncallables = partition_by_callable(type)`

    If we assert `callable(type)` then `type` has type Union[*callables], and
    If we assert `not callable(type)` then `type` has type Union[*uncallables]

    Guaranteed to not return [], []"""
    if isinstance(type, FunctionLike) or isinstance(type, TypeType):
        return [type], []

    if isinstance(type, AnyType):
        return [type], [type]

    if isinstance(type, UnionType):
        callables = []
        uncallables = []
        for subtype in type.relevant_items():
            subcallables, subuncallables = partition_by_callable(subtype)
            callables.extend(subcallables)
            uncallables.extend(subuncallables)
        return callables, uncallables

    if isinstance(type, TypeVarType):
        return partition_by_callable(type.erase_to_union_or_bound())

    if isinstance(type, Instance):
        method = type.type.get_method('__call__')
        if method and method.type:
            callables, uncallables = partition_by_callable(method.type)
            if len(callables) and not len(uncallables):
                # Only consider the type callable if its __call__ method is
                # definitely callable.
                return [type], []
        return [], [type]

    return [], [type]


def conditional_callable_type_map(expr: Expression,
                                  current_type: Optional[Type],
                                  ) -> Tuple[TypeMap, TypeMap]:
    """Takes in an expression and the current type of the expression.

    Returns a 2-tuple: The first element is a map from the expression to
    the restricted type if it were callable. The second element is a
    map from the expression to the type it would hold if it weren't
    callable."""
    if not current_type:
        return {}, {}

    if isinstance(current_type, AnyType):
        return {}, {}

    callables, uncallables = partition_by_callable(current_type)

    if len(callables) and len(uncallables):
        callable_map = {expr: UnionType.make_union(callables)} if len(callables) else None
        uncallable_map = {expr: UnionType.make_union(uncallables)} if len(uncallables) else None
        return callable_map, uncallable_map

    elif len(callables):
        return {}, None

    return None, {}


def is_true_literal(n: Expression) -> bool:
    return (refers_to_fullname(n, 'builtins.True')
            or isinstance(n, IntExpr) and n.value == 1)


def is_false_literal(n: Expression) -> bool:
    return (refers_to_fullname(n, 'builtins.False')
            or isinstance(n, IntExpr) and n.value == 0)


def is_literal_none(n: Expression) -> bool:
    return isinstance(n, NameExpr) and n.fullname == 'builtins.None'


def is_optional(t: Type) -> bool:
    return isinstance(t, UnionType) and any(isinstance(e, NoneTyp) for e in t.items)


def remove_optional(typ: Type) -> Type:
    if isinstance(typ, UnionType):
        return UnionType.make_union([t for t in typ.items if not isinstance(t, NoneTyp)])
    else:
        return typ


def builtin_item_type(tp: Type) -> Optional[Type]:
    """Get the item type of a builtin container.

    If 'tp' is not one of the built containers (these includes NamedTuple and TypedDict)
    or if the container is not parameterized (like List or List[Any])
    return None. This function is used to narrow optional types in situations like this:

        x: Optional[int]
        if x in (1, 2, 3):
            x + 42  # OK

    Note: this is only OK for built-in containers, where we know the behavior
    of __contains__.
    """
    if isinstance(tp, Instance):
        if tp.type.fullname() in ['builtins.list', 'builtins.tuple', 'builtins.dict',
                                  'builtins.set', 'builtins.frozenset']:
            if not tp.args:
                # TODO: fix tuple in lib-stub/builtins.pyi (it should be generic).
                return None
            if not isinstance(tp.args[0], AnyType):
                return tp.args[0]
    elif isinstance(tp, TupleType) and all(not isinstance(it, AnyType) for it in tp.items):
        return UnionType.make_simplified_union(tp.items)  # this type is not externally visible
    elif isinstance(tp, TypedDictType):
        # TypedDict always has non-optional string keys.
        if tp.fallback.type.fullname() == 'typing.Mapping':
            return tp.fallback.args[0]
        elif tp.fallback.type.bases[0].type.fullname() == 'typing.Mapping':
            return tp.fallback.type.bases[0].args[0]
    return None


def and_conditional_maps(m1: TypeMap, m2: TypeMap) -> TypeMap:
    """Calculate what information we can learn from the truth of (e1 and e2)
    in terms of the information that we can learn from the truth of e1 and
    the truth of e2.
    """

    if m1 is None or m2 is None:
        # One of the conditions can never be true.
        return None
    # Both conditions can be true; combine the information. Anything
    # we learn from either conditions's truth is valid. If the same
    # expression's type is refined by both conditions, we somewhat
    # arbitrarily give precedence to m2. (In the future, we could use
    # an intersection type.)
    result = m2.copy()
    m2_keys = set(literal_hash(n2) for n2 in m2)
    for n1 in m1:
        if literal_hash(n1) not in m2_keys:
            result[n1] = m1[n1]
    return result


def or_conditional_maps(m1: TypeMap, m2: TypeMap) -> TypeMap:
    """Calculate what information we can learn from the truth of (e1 or e2)
    in terms of the information that we can learn from the truth of e1 and
    the truth of e2.
    """

    if m1 is None:
        return m2
    if m2 is None:
        return m1
    # Both conditions can be true. Combine information about
    # expressions whose type is refined by both conditions. (We do not
    # learn anything about expressions whose type is refined by only
    # one condition.)
    result = {}
    for n1 in m1:
        for n2 in m2:
            if literal_hash(n1) == literal_hash(n2):
                result[n1] = UnionType.make_simplified_union([m1[n1], m2[n2]])
    return result


def convert_to_typetype(type_map: TypeMap) -> TypeMap:
    converted_type_map = {}  # type: Dict[Expression, Type]
    if type_map is None:
        return None
    for expr, typ in type_map.items():
        if not isinstance(typ, (UnionType, Instance)):
            # unknown type; error was likely reported earlier
            return {}
        converted_type_map[expr] = TypeType.make_normalized(typ)
    return converted_type_map


def find_isinstance_check(node: Expression,
                          type_map: Dict[Expression, Type],
                          ) -> Tuple[TypeMap, TypeMap]:
    """Find any isinstance checks (within a chain of ands).  Includes
    implicit and explicit checks for None and calls to callable.

    Return value is a map of variables to their types if the condition
    is true and a map of variables to their types if the condition is false.

    If either of the values in the tuple is None, then that particular
    branch can never occur.

    Guaranteed to not return None, None. (But may return {}, {})
    """
    if is_true_literal(node):
        return {}, None
    elif is_false_literal(node):
        return None, {}
    elif isinstance(node, CallExpr):
        if refers_to_fullname(node.callee, 'builtins.isinstance'):
            if len(node.args) != 2:  # the error will be reported later
                return {}, {}
            expr = node.args[0]
            if literal(expr) == LITERAL_TYPE:
                vartype = type_map[expr]
                type = get_isinstance_type(node.args[1], type_map)
                return conditional_type_map(expr, vartype, type)
        elif refers_to_fullname(node.callee, 'builtins.issubclass'):
            expr = node.args[0]
            if literal(expr) == LITERAL_TYPE:
                vartype = type_map[expr]
                type = get_isinstance_type(node.args[1], type_map)
                if isinstance(vartype, UnionType):
                    union_list = []
                    for t in vartype.items:
                        if isinstance(t, TypeType):
                            union_list.append(t.item)
                        else:
                            #  this is an error that should be reported earlier
                            #  if we reach here, we refuse to do any type inference
                            return {}, {}
                    vartype = UnionType(union_list)
                elif isinstance(vartype, TypeType):
                    vartype = vartype.item
                else:
                    # any other object whose type we don't know precisely
                    # for example, Any or Instance of type type
                    return {}, {}  # unknown type
                yes_map, no_map = conditional_type_map(expr, vartype, type)
                yes_map, no_map = map(convert_to_typetype, (yes_map, no_map))
                return yes_map, no_map
        elif refers_to_fullname(node.callee, 'builtins.callable'):
            expr = node.args[0]
            if literal(expr) == LITERAL_TYPE:
                vartype = type_map[expr]
                return conditional_callable_type_map(expr, vartype)
    elif isinstance(node, ComparisonExpr) and experiments.STRICT_OPTIONAL:
        # Check for `x is None` and `x is not None`.
        is_not = node.operators == ['is not']
        if any(is_literal_none(n) for n in node.operands) and (is_not or node.operators == ['is']):
            if_vars = {}  # type: TypeMap
            else_vars = {}  # type: TypeMap
            for expr in node.operands:
                if (literal(expr) == LITERAL_TYPE and not is_literal_none(expr)
                        and expr in type_map):
                    # This should only be true at most once: there should be
                    # two elements in node.operands, and at least one of them
                    # should represent a None.
                    vartype = type_map[expr]
                    none_typ = [TypeRange(NoneTyp(), is_upper_bound=False)]
                    if_vars, else_vars = conditional_type_map(expr, vartype, none_typ)
                    break

            if is_not:
                if_vars, else_vars = else_vars, if_vars
            return if_vars, else_vars
        # Check for `x == y` where x is of type Optional[T] and y is of type T
        # or a type that overlaps with T (or vice versa).
        elif node.operators == ['==']:
            first_type = type_map[node.operands[0]]
            second_type = type_map[node.operands[1]]
            if is_optional(first_type) != is_optional(second_type):
                if is_optional(first_type):
                    optional_type, comp_type = first_type, second_type
                    optional_expr = node.operands[0]
                else:
                    optional_type, comp_type = second_type, first_type
                    optional_expr = node.operands[1]
                if is_overlapping_types(optional_type, comp_type):
                    return {optional_expr: remove_optional(optional_type)}, {}
        elif node.operators in [['in'], ['not in']]:
            expr = node.operands[0]
            left_type = type_map[expr]
            right_type = builtin_item_type(type_map[node.operands[1]])
            right_ok = right_type and (not is_optional(right_type) and
                                       (not isinstance(right_type, Instance) or
                                        right_type.type.fullname() != 'builtins.object'))
            if (right_type and right_ok and is_optional(left_type) and
                    literal(expr) == LITERAL_TYPE and not is_literal_none(expr) and
                    is_overlapping_types(left_type, right_type)):
                if node.operators == ['in']:
                    return {expr: remove_optional(left_type)}, {}
                if node.operators == ['not in']:
                    return {}, {expr: remove_optional(left_type)}
    elif isinstance(node, RefExpr):
        # Restrict the type of the variable to True-ish/False-ish in the if and else branches
        # respectively
        vartype = type_map[node]
        if_type = true_only(vartype)
        else_type = false_only(vartype)
        ref = node  # type: Expression
        if_map = {ref: if_type} if not isinstance(if_type, UninhabitedType) else None
        else_map = {ref: else_type} if not isinstance(else_type, UninhabitedType) else None
        return if_map, else_map
    elif isinstance(node, OpExpr) and node.op == 'and':
        left_if_vars, left_else_vars = find_isinstance_check(node.left, type_map)
        right_if_vars, right_else_vars = find_isinstance_check(node.right, type_map)

        # (e1 and e2) is true if both e1 and e2 are true,
        # and false if at least one of e1 and e2 is false.
        return (and_conditional_maps(left_if_vars, right_if_vars),
                or_conditional_maps(left_else_vars, right_else_vars))
    elif isinstance(node, OpExpr) and node.op == 'or':
        left_if_vars, left_else_vars = find_isinstance_check(node.left, type_map)
        right_if_vars, right_else_vars = find_isinstance_check(node.right, type_map)

        # (e1 or e2) is true if at least one of e1 or e2 is true,
        # and false if both e1 and e2 are false.
        return (or_conditional_maps(left_if_vars, right_if_vars),
                and_conditional_maps(left_else_vars, right_else_vars))
    elif isinstance(node, UnaryExpr) and node.op == 'not':
        left, right = find_isinstance_check(node.expr, type_map)
        return right, left

    # Not a supported isinstance check
    return {}, {}


def flatten(t: Expression) -> List[Expression]:
    """Flatten a nested sequence of tuples/lists into one list of nodes."""
    if isinstance(t, TupleExpr) or isinstance(t, ListExpr):
        return [b for a in t.items for b in flatten(a)]
    else:
        return [t]


def flatten_types(t: Type) -> List[Type]:
    """Flatten a nested sequence of tuples into one list of nodes."""
    if isinstance(t, TupleType):
        return [b for a in t.items for b in flatten_types(a)]
    else:
        return [t]


def get_isinstance_type(expr: Expression,
                        type_map: Dict[Expression, Type]) -> Optional[List[TypeRange]]:
    all_types = flatten_types(type_map[expr])
    types = []  # type: List[TypeRange]
    for typ in all_types:
        if isinstance(typ, FunctionLike) and typ.is_type_obj():
            # Type variables may be present -- erase them, which is the best
            # we can do (outside disallowing them here).
            typ = erase_typevars(typ.items()[0].ret_type)
            types.append(TypeRange(typ, is_upper_bound=False))
        elif isinstance(typ, TypeType):
            # Type[A] means "any type that is a subtype of A" rather than "precisely type A"
            # we indicate this by setting is_upper_bound flag
            types.append(TypeRange(typ.item, is_upper_bound=True))
        elif isinstance(typ, Instance) and typ.type.fullname() == 'builtins.type':
            object_type = Instance(typ.type.mro[-1], [])
            types.append(TypeRange(object_type, is_upper_bound=True))
        else:  # we didn't see an actual type, but rather a variable whose value is unknown to us
            return None
    if not types:
        # this can happen if someone has empty tuple as 2nd argument to isinstance
        # strictly speaking, we should return UninhabitedType but for simplicity we will simply
        # refuse to do any type inference for now
        return None
    return types


def expand_func(defn: FuncItem, map: Dict[TypeVarId, Type]) -> FuncItem:
    visitor = TypeTransformVisitor(map)
    ret = defn.accept(visitor)
    assert isinstance(ret, FuncItem)
    return ret


class TypeTransformVisitor(TransformVisitor):
    def __init__(self, map: Dict[TypeVarId, Type]) -> None:
        super().__init__()
        self.map = map

    def type(self, type: Type) -> Type:
        return expand_type(type, self.map)


def is_unsafe_overlapping_signatures(signature: Type, other: Type) -> bool:
    """Check if two signatures may be unsafely overlapping.

    Two signatures s and t are overlapping if both can be valid for the same
    statically typed values and the return types are incompatible.

    Assume calls are first checked against 'signature', then against 'other'.
    Thus if 'signature' is more general than 'other', there is no unsafe
    overlapping.

    TODO If argument types vary covariantly, the return type may vary
         covariantly as well.
    """
    if isinstance(signature, CallableType):
        if isinstance(other, CallableType):
            # TODO varargs
            # TODO keyword args
            # TODO erasure
            # TODO allow to vary covariantly
            # Check if the argument counts are overlapping.
            min_args = max(signature.min_args, other.min_args)
            max_args = min(len(signature.arg_types), len(other.arg_types))
            if min_args > max_args:
                # Argument counts are not overlapping.
                return False
            # Signatures are overlapping iff if they are overlapping for the
            # smallest common argument count.
            for i in range(min_args):
                t1 = signature.arg_types[i]
                t2 = other.arg_types[i]
                if not is_overlapping_types(t1, t2):
                    return False
            # All arguments types for the smallest common argument count are
            # overlapping => the signature is overlapping. The overlapping is
            # safe if the return types are identical.
            if is_same_type(signature.ret_type, other.ret_type):
                return False
            # If the first signature has more general argument types, the
            # latter will never be called
            if is_more_general_arg_prefix(signature, other):
                return False
            # Special case: all args are subtypes, and returns are subtypes
            if (all(is_proper_subtype(s, o)
                    for (s, o) in zip(signature.arg_types, other.arg_types)) and
                    is_proper_subtype(signature.ret_type, other.ret_type)):
                return False
            return not is_more_precise_signature(signature, other)
    return True


def is_more_general_arg_prefix(t: FunctionLike, s: FunctionLike) -> bool:
    """Does t have wider arguments than s?"""
    # TODO should an overload with additional items be allowed to be more
    #      general than one with fewer items (or just one item)?
    # TODO check argument kinds and otherwise make more general
    if isinstance(t, CallableType):
        if isinstance(s, CallableType):
            t, s = unify_generic_callables(t, s)
            return all(is_proper_subtype(args, argt)
                       for argt, args in zip(t.arg_types, s.arg_types))
    elif isinstance(t, FunctionLike):
        if isinstance(s, FunctionLike):
            if len(t.items()) == len(s.items()):
                return all(is_same_arg_prefix(items, itemt)
                           for items, itemt in zip(t.items(), s.items()))
    return False


def unify_generic_callables(t: CallableType,
                            s: CallableType) -> Tuple[CallableType,
                                                      CallableType]:
    """Make type variables in generic callables the same if possible.

    Return updated callables. If we can't unify the type variables,
    return the unmodified arguments.
    """
    # TODO: Use this elsewhere when comparing generic callables.
    if t.is_generic() and s.is_generic():
        t_substitutions = {}
        s_substitutions = {}
        for tv1, tv2 in zip(t.variables, s.variables):
            # Are these something we can unify?
            if tv1.id != tv2.id and is_equivalent_type_var_def(tv1, tv2):
                newdef = TypeVarDef.new_unification_variable(tv2)
                t_substitutions[tv1.id] = TypeVarType(newdef)
                s_substitutions[tv2.id] = TypeVarType(newdef)
        return (cast(CallableType, expand_type(t, t_substitutions)),
                cast(CallableType, expand_type(s, s_substitutions)))
    return t, s


def is_equivalent_type_var_def(tv1: TypeVarDef, tv2: TypeVarDef) -> bool:
    """Are type variable definitions equivalent?

    Ignore ids, locations in source file and names.
    """
    return (
        tv1.variance == tv2.variance
        and is_same_types(tv1.values, tv2.values)
        and ((tv1.upper_bound is None and tv2.upper_bound is None)
             or (tv1.upper_bound is not None
                 and tv2.upper_bound is not None
                 and is_same_type(tv1.upper_bound, tv2.upper_bound))))


def is_same_arg_prefix(t: CallableType, s: CallableType) -> bool:
    # TODO check argument kinds
    return all(is_same_type(argt, args)
               for argt, args in zip(t.arg_types, s.arg_types))


def is_more_precise_signature(t: CallableType, s: CallableType) -> bool:
    """Is t more precise than s?

    A signature t is more precise than s if all argument types and the return
    type of t are more precise than the corresponding types in s.

    Assume that the argument kinds and names are compatible, and that the
    argument counts are overlapping.
    """
    # TODO generic function types
    # Only consider the common prefix of argument types.
    for argt, args in zip(t.arg_types, s.arg_types):
        if not is_more_precise(argt, args):
            return False
    return is_more_precise(t.ret_type, s.ret_type)


def infer_operator_assignment_method(typ: Type, operator: str) -> Tuple[bool, str]:
    """Determine if operator assignment on given value type is in-place, and the method name.

    For example, if operator is '+', return (True, '__iadd__') or (False, '__add__')
    depending on which method is supported by the type.
    """
    method = nodes.op_methods[operator]
    if isinstance(typ, Instance):
        if operator in nodes.ops_with_inplace_method:
            inplace_method = '__i' + method[2:]
            if typ.type.has_readable_member(inplace_method):
                return True, inplace_method
    return False, method


def is_valid_inferred_type(typ: Type) -> bool:
    """Is an inferred type valid?

    Examples of invalid types include the None type or List[<uninhabited>].

    When not doing strict Optional checking, all types containing None are
    invalid.  When doing strict Optional checking, only None and types that are
    incompletely defined (i.e. contain UninhabitedType) are invalid.
    """
    if isinstance(typ, (NoneTyp, UninhabitedType)):
        # With strict Optional checking, we *may* eventually infer NoneTyp when
        # the initializer is None, but we only do that if we can't infer a
        # specific Optional type.  This resolution happens in
        # leave_partial_types when we pop a partial types scope.
        return False
    return is_valid_inferred_type_component(typ)


def is_valid_inferred_type_component(typ: Type) -> bool:
    """Is this part of a type a valid inferred type?

    In strict Optional mode this excludes bare None types, as otherwise every
    type containing None would be invalid.
    """
    if is_same_type(typ, UninhabitedType()):
        return False
    elif isinstance(typ, Instance):
        for arg in typ.args:
            if not is_valid_inferred_type_component(arg):
                return False
    elif isinstance(typ, TupleType):
        for item in typ.items:
            if not is_valid_inferred_type_component(item):
                return False
    return True


def is_node_static(node: Optional[Node]) -> Optional[bool]:
    """Find out if a node describes a static function method."""

    if isinstance(node, FuncDef):
        return node.is_static

    if isinstance(node, Var):
        return node.is_staticmethod

    return None


class Scope:
    # We keep two stacks combined, to maintain the relative order
    stack = None  # type: List[Union[TypeInfo, FuncItem, MypyFile]]

    def __init__(self, module: MypyFile) -> None:
        self.stack = [module]

    def top_function(self) -> Optional[FuncItem]:
        for e in reversed(self.stack):
            if isinstance(e, FuncItem):
                return e
        return None

    def active_class(self) -> Optional[TypeInfo]:
        if isinstance(self.stack[-1], TypeInfo):
            return self.stack[-1]
        return None

    def enclosing_class(self) -> Optional[TypeInfo]:
        top = self.top_function()
        assert top, "This method must be called from inside a function"
        index = self.stack.index(top)
        assert index, "Scope stack must always start with a module"
        enclosing = self.stack[index - 1]
        if isinstance(enclosing, TypeInfo):
            return enclosing
        return None

    def active_self_type(self) -> Optional[Union[Instance, TupleType]]:
        info = self.active_class()
        if info:
            return fill_typevars(info)
        return None

    @contextmanager
    def push_function(self, item: FuncItem) -> Iterator[None]:
        self.stack.append(item)
        yield
        self.stack.pop()

    @contextmanager
    def push_class(self, info: TypeInfo) -> Iterator[None]:
        self.stack.append(info)
        yield
        self.stack.pop()


@contextmanager
def nothing() -> Iterator[None]:
    yield


def is_typed_callable(c: Optional[Type]) -> bool:
    if not c or not isinstance(c, CallableType):
        return False
    return not all(isinstance(t, AnyType) and t.type_of_any == TypeOfAny.unannotated
                   for t in c.arg_types + [c.ret_type])


def is_untyped_decorator(typ: Optional[Type]) -> bool:
    if not typ or not isinstance(typ, CallableType):
        return True
    return typ.implicit


def is_static(func: Union[FuncBase, Decorator]) -> bool:
    if isinstance(func, Decorator):
        return is_static(func.func)
    elif isinstance(func, OverloadedFuncDef):
        return any(is_static(item) for item in func.items)
    elif isinstance(func, FuncItem):
        return func.is_static
    return False
