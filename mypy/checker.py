"""Mypy type checker."""

import itertools
import contextlib
import fnmatch
import os
import os.path

from typing import (
    Any, Dict, Set, List, cast, Tuple, TypeVar, Union, Optional, NamedTuple
)

from mypy.errors import Errors, report_internal_error
from mypy.nodes import (
    SymbolTable, Node, MypyFile, Var, Expression,
    OverloadedFuncDef, FuncDef, FuncItem, FuncBase, TypeInfo,
    ClassDef, GDEF, Block, AssignmentStmt, NameExpr, MemberExpr, IndexExpr,
    TupleExpr, ListExpr, ExpressionStmt, ReturnStmt, IfStmt,
    WhileStmt, OperatorAssignmentStmt, WithStmt, AssertStmt,
    RaiseStmt, TryStmt, ForStmt, DelStmt, CallExpr, IntExpr, StrExpr,
    BytesExpr, UnicodeExpr, FloatExpr, OpExpr, UnaryExpr, CastExpr, RevealTypeExpr, SuperExpr,
    TypeApplication, DictExpr, SliceExpr, FuncExpr, TempNode, SymbolTableNode,
    Context, ListComprehension, ConditionalExpr, GeneratorExpr,
    Decorator, SetExpr, TypeVarExpr, NewTypeExpr, PrintStmt,
    LITERAL_TYPE, BreakStmt, ContinueStmt, ComparisonExpr, StarExpr,
    YieldFromExpr, NamedTupleExpr, SetComprehension,
    DictionaryComprehension, ComplexExpr, EllipsisExpr, TypeAliasExpr,
    RefExpr, YieldExpr, BackquoteExpr, ImportFrom, ImportAll, ImportBase,
    AwaitExpr,
    CONTRAVARIANT, COVARIANT
)
from mypy.nodes import function_type, method_type, method_type_with_fallback
from mypy import nodes
from mypy.types import (
    Type, AnyType, CallableType, Void, FunctionLike, Overloaded, TupleType,
    Instance, NoneTyp, ErrorType, strip_type,
    UnionType, TypeVarId, TypeVarType, PartialType, DeletedType, UninhabitedType,
    true_only, false_only
)
from mypy.sametypes import is_same_type
from mypy.messages import MessageBuilder
import mypy.checkexpr
from mypy.checkmember import map_type_from_supertype
from mypy import defaults
from mypy import messages
from mypy.subtypes import (
    is_subtype, is_equivalent, is_proper_subtype,
    is_more_precise, restrict_subtype_away
)
from mypy.maptype import map_instance_to_supertype
from mypy.semanal import self_type, set_callable_name, refers_to_fullname
from mypy.erasetype import erase_typevars
from mypy.expandtype import expand_type_by_instance, expand_type
from mypy.visitor import NodeVisitor
from mypy.join import join_types
from mypy.treetransform import TransformVisitor
from mypy.meet import meet_simple, nearest_builtin_ancestor, is_overlapping_types
from mypy.binder import ConditionalTypeBinder
from mypy.options import Options

from mypy import experiments


T = TypeVar('T')


# A node which is postponed to be type checked during the next pass.
DeferredNode = NamedTuple(
    'DeferredNode',
    [
        ('node', Node),
        ('context_type_name', Optional[str]),  # Name of the surrounding class (for error messages)
    ])


class TypeChecker(NodeVisitor[Type]):
    """Mypy type checker.

    Type check mypy source files that have been semantically analyzed.
    """

    # Are we type checking a stub?
    is_stub = False
    # Error message reporter
    errors = None  # type: Errors
    # Utility for generating messages
    msg = None  # type: MessageBuilder
    # Types of type checked nodes
    type_map = None  # type: Dict[Node, Type]
    # Types of type checked nodes within this specific module
    module_type_map = None  # type: Dict[Node, Type]

    # Helper for managing conditional types
    binder = None  # type: ConditionalTypeBinder
    # Helper for type checking expressions
    expr_checker = None  # type: mypy.checkexpr.ExpressionChecker

    # Stack of function return types
    return_types = None  # type: List[Type]
    # Type context for type inference
    type_context = None  # type: List[Type]
    # Flags; true for dynamically typed functions
    dynamic_funcs = None  # type: List[bool]
    # Stack of functions being type checked
    function_stack = None  # type: List[FuncItem]
    # Do weak type checking in this file
    weak_opts = set()        # type: Set[str]
    # Stack of collections of variables with partial types
    partial_types = None  # type: List[Dict[Var, Context]]
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
    suppress_none_errors = False
    options = None  # type: Options

    # The set of all dependencies (suppressed or not) that this module accesses, either
    # directly or indirectly.
    module_refs = None  # type: Set[str]

    def __init__(self, errors: Errors, modules: Dict[str, MypyFile], options: Options) -> None:
        """Construct a type checker.

        Use errors to report type check errors.
        """
        self.errors = errors
        self.modules = modules
        self.options = options
        self.msg = MessageBuilder(errors, modules)
        self.type_map = {}
        self.module_type_map = {}
        self.binder = ConditionalTypeBinder()
        self.expr_checker = mypy.checkexpr.ExpressionChecker(self, self.msg)
        self.return_types = []
        self.type_context = []
        self.dynamic_funcs = []
        self.function_stack = []
        self.weak_opts = set()  # type: Set[str]
        self.partial_types = []
        self.deferred_nodes = []
        self.pass_num = 0
        self.current_node_deferred = False
        self.module_refs = set()

    def visit_file(self, file_node: MypyFile, path: str) -> None:
        """Type check a mypy file with the given path."""
        self.pass_num = 0
        self.is_stub = file_node.is_stub
        self.errors.set_file(path)
        self.globals = file_node.names
        self.weak_opts = file_node.weak_opts
        self.enter_partial_types()
        self.is_typeshed_stub = self.errors.is_typeshed_file(path)
        self.module_type_map = {}
        self.module_refs = set()
        if self.options.strict_optional_whitelist is None:
            self.suppress_none_errors = False
        else:
            self.suppress_none_errors = not any(fnmatch.fnmatch(path, pattern)
                                                for pattern
                                                in self.options.strict_optional_whitelist)

        for d in file_node.defs:
            self.accept(d)

        self.leave_partial_types()

        if self.deferred_nodes:
            self.check_second_pass()

        self.current_node_deferred = False

        all_ = self.globals.get('__all__')
        if all_ is not None and all_.type is not None:
            seq_str = self.named_generic_type('typing.Sequence',
                                              [self.named_type('builtins.str')])
            if not is_subtype(all_.type, seq_str):
                str_seq_s, all_s = self.msg.format_distinctly(seq_str, all_.type)
                self.fail(messages.ALL_MUST_BE_SEQ_STR.format(str_seq_s, all_s),
                          all_.node)

    def check_second_pass(self) -> None:
        """Run second pass of type checking which goes through deferred nodes."""
        self.pass_num = 1
        for node, type_name in self.deferred_nodes:
            if type_name:
                self.errors.push_type(type_name)
            self.accept(node)
            if type_name:
                self.errors.pop_type()
        self.deferred_nodes = []

    def handle_cannot_determine_type(self, name: str, context: Context) -> None:
        if self.pass_num == 0 and self.function_stack:
            # Don't report an error yet. Just defer.
            node = self.function_stack[-1]
            if self.errors.type_name:
                type_name = self.errors.type_name[-1]
            else:
                type_name = None
            self.deferred_nodes.append(DeferredNode(node, type_name))
            # Set a marker so that we won't infer additional types in this
            # function. Any inferred types could be bogus, because there's at
            # least one type that we don't know.
            self.current_node_deferred = True
        else:
            self.msg.cannot_determine_type(name, context)

    def accept(self, node: Node, type_context: Type = None) -> Type:
        """Type check a node in the given type context."""
        self.type_context.append(type_context)
        try:
            typ = node.accept(self)
        except Exception as err:
            report_internal_error(err, self.errors.file, node.line, self.errors)
        self.type_context.pop()
        self.store_type(node, typ)
        if self.typing_mode_none():
            return AnyType()
        else:
            return typ

    def accept_loop(self, body: Node, else_body: Node = None) -> Type:
        """Repeatedly type check a loop body until the frame doesn't change.

        Then check the else_body.
        """
        # The outer frame accumulates the results of all iterations
        with self.binder.frame_context(1) as outer_frame:
            self.binder.push_loop_frame()
            while True:
                with self.binder.frame_context(1):
                    # We may skip each iteration
                    self.binder.options_on_return[-1].append(outer_frame)
                    self.accept(body)
                if not self.binder.last_pop_changed:
                    break
            self.binder.pop_loop_frame()
            if else_body:
                self.accept(else_body)

    #
    # Definitions
    #

    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> Type:
        num_abstract = 0
        if defn.is_property:
            # HACK: Infer the type of the property.
            self.visit_decorator(defn.items[0])
        for fdef in defn.items:
            self.check_func_item(fdef.func, name=fdef.func.name())
            if fdef.func.is_abstract:
                num_abstract += 1
        if num_abstract not in (0, len(defn.items)):
            self.fail(messages.INCONSISTENT_ABSTRACT_OVERLOAD, defn)
        if defn.info:
            self.check_method_override(defn)
            self.check_inplace_operator_method(defn)
        self.check_overlapping_overloads(defn)

    def check_overlapping_overloads(self, defn: OverloadedFuncDef) -> None:
        for i, item in enumerate(defn.items):
            for j, item2 in enumerate(defn.items[i + 1:]):
                # TODO overloads involving decorators
                sig1 = self.function_type(item.func)
                sig2 = self.function_type(item2.func)
                if is_unsafe_overlapping_signatures(sig1, sig2):
                    self.msg.overloaded_signatures_overlap(i + 1, i + j + 2,
                                                           item.func)

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
    # object or Any).  If tc/tr are not given, both are Void.
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
    # There are several useful methods, each taking a type t and a
    # flag c indicating whether it's for a generator or coroutine:
    #
    # - is_generator_return_type(t, c) returns whether t is a Generator,
    #   Iterator, Iterable (if not c), or Awaitable (if c), or
    #   AwaitableGenerator (regardless of c).
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
            at = self.named_generic_type('typing.Awaitable', [AnyType()])
            if is_subtype(at, typ):
                return True
        else:
            gt = self.named_generic_type('typing.Generator', [AnyType(), AnyType(), AnyType()])
            if is_subtype(gt, typ):
                return True
        return isinstance(typ, Instance) and typ.type.fullname() == 'typing.AwaitableGenerator'

    def get_generator_yield_type(self, return_type: Type, is_coroutine: bool) -> Type:
        """Given the declared return type of a generator (t), return the type it yields (ty)."""
        if isinstance(return_type, AnyType):
            return AnyType()
        elif not self.is_generator_return_type(return_type, is_coroutine):
            # If the function doesn't have a proper Generator (or
            # Awaitable) return type, anything is permissible.
            return AnyType()
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType()
        elif return_type.type.fullname() == 'typing.Awaitable':
            # Awaitable: ty is Any.
            return AnyType()
        elif return_type.args:
            # AwaitableGenerator, Generator, Iterator, or Iterable; ty is args[0].
            ret_type = return_type.args[0]
            # TODO not best fix, better have dedicated yield token
            if isinstance(ret_type, NoneTyp):
                if experiments.STRICT_OPTIONAL:
                    return NoneTyp(is_ret_type=True)
                else:
                    return Void()
            return ret_type
        else:
            # If the function's declared supertype of Generator has no type
            # parameters (i.e. is `object`), then the yielded values can't
            # be accessed so any type is acceptable.  IOW, ty is Any.
            # (However, see https://github.com/python/mypy/issues/1933)
            return AnyType()

    def get_generator_receive_type(self, return_type: Type, is_coroutine: bool) -> Type:
        """Given a declared generator return type (t), return the type its yield receives (tc)."""
        if isinstance(return_type, AnyType):
            return AnyType()
        elif not self.is_generator_return_type(return_type, is_coroutine):
            # If the function doesn't have a proper Generator (or
            # Awaitable) return type, anything is permissible.
            return AnyType()
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType()
        elif return_type.type.fullname() == 'typing.Awaitable':
            # Awaitable, AwaitableGenerator: tc is Any.
            return AnyType()
        elif (return_type.type.fullname() in ('typing.Generator', 'typing.AwaitableGenerator')
              and len(return_type.args) >= 3):
            # Generator: tc is args[1].
            return return_type.args[1]
        else:
            # `return_type` is a supertype of Generator, so callers won't be able to send it
            # values.  IOW, tc is None.
            if experiments.STRICT_OPTIONAL:
                return NoneTyp(is_ret_type=True)
            else:
                return Void()

    def get_generator_return_type(self, return_type: Type, is_coroutine: bool) -> Type:
        """Given the declared return type of a generator (t), return the type it returns (tr)."""
        if isinstance(return_type, AnyType):
            return AnyType()
        elif not self.is_generator_return_type(return_type, is_coroutine):
            # If the function doesn't have a proper Generator (or
            # Awaitable) return type, anything is permissible.
            return AnyType()
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType()
        elif return_type.type.fullname() == 'typing.Awaitable' and len(return_type.args) == 1:
            # Awaitable: tr is args[0].
            return return_type.args[0]
        elif (return_type.type.fullname() in ('typing.Generator', 'typing.AwaitableGenerator')
              and len(return_type.args) >= 3):
            # AwaitableGenerator, Generator: tr is args[2].
            return return_type.args[2]
        else:
            # Supertype of Generator (Iterator, Iterable, object): tr is any.
            return AnyType()

    def check_awaitable_expr(self, t: Type, ctx: Context, msg: str) -> Type:
        """Check the argument to `await` and extract the type of value.

        Also used by `async for` and `async with`.
        """
        if not self.check_subtype(t, self.named_type('typing.Awaitable'), ctx,
                                  msg, 'actual type', 'expected type'):
            return AnyType()
        else:
            echk = self.expr_checker
            method = echk.analyze_external_member_access('__await__', t, ctx)
            generator = echk.check_call(method, [], [], ctx)[0]
            return self.get_generator_return_type(generator, False)

    def visit_func_def(self, defn: FuncDef) -> Type:
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
                    return None
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
                        type_override: CallableType = None,
                        name: str = None) -> Type:
        """Type check a function.

        If type_override is provided, use it as the function type.
        """
        # We may be checking a function definition or an anonymous function. In
        # the first case, set up another reference with the precise type.
        fdef = None  # type: FuncDef
        if isinstance(defn, FuncDef):
            fdef = defn

        self.function_stack.append(defn)
        self.dynamic_funcs.append(defn.is_dynamic() and not type_override)

        if fdef:
            self.errors.push_function(fdef.name())

        self.enter_partial_types()

        typ = self.function_type(defn)
        if type_override:
            typ = type_override
        if isinstance(typ, CallableType):
            self.check_func_def(defn, typ, name)
        else:
            raise RuntimeError('Not supported')

        self.leave_partial_types()

        if fdef:
            self.errors.pop_function()

        self.dynamic_funcs.pop()
        self.function_stack.pop()
        self.current_node_deferred = False

    def check_func_def(self, defn: FuncItem, typ: CallableType, name: str) -> None:
        """Type check a function definition."""
        # Expand type variables with value restrictions to ordinary types.
        for item, typ in self.expand_typevars(defn, typ):
            old_binder = self.binder
            self.binder = ConditionalTypeBinder()
            with self.binder.frame_context():
                defn.expanded.append(item)

                # We may be checking a function definition or an anonymous
                # function. In the first case, set up another reference with the
                # precise type.
                if isinstance(item, FuncDef):
                    fdef = item
                else:
                    fdef = None

                if fdef:
                    # Check if __init__ has an invalid, non-None return type.
                    if (fdef.info and fdef.name() == '__init__' and
                            not isinstance(typ.ret_type, (Void, NoneTyp)) and
                            not self.dynamic_funcs[-1]):
                        self.fail(messages.INIT_MUST_HAVE_NONE_RETURN_TYPE,
                                  item.type)

                    show_untyped = not self.is_typeshed_stub or self.options.warn_incomplete_stub
                    if self.options.disallow_untyped_defs and show_untyped:
                        # Check for functions with unspecified/not fully specified types.
                        def is_implicit_any(t: Type) -> bool:
                            return isinstance(t, AnyType) and t.implicit

                        if fdef.type is None:
                            self.fail(messages.FUNCTION_TYPE_EXPECTED, fdef)
                        elif isinstance(fdef.type, CallableType):
                            if is_implicit_any(fdef.type.ret_type):
                                self.fail(messages.RETURN_TYPE_EXPECTED, fdef)
                            if any(is_implicit_any(t) for t in fdef.type.arg_types):
                                self.fail(messages.ARGUMENT_TYPE_EXPECTED, fdef)

                if name in nodes.reverse_op_method_set:
                    self.check_reverse_op_method(item, typ, name)
                elif name == '__getattr__':
                    self.check_getattr_method(typ, defn)

                # Refuse contravariant return type variable
                if isinstance(typ.ret_type, TypeVarType):
                    if typ.ret_type.variance == CONTRAVARIANT:
                        self.fail(messages.RETURN_TYPE_CANNOT_BE_CONTRAVARIANT,
                             typ.ret_type)

                # Check that Generator functions have the appropriate return type.
                if defn.is_generator:
                    if not self.is_generator_return_type(typ.ret_type, defn.is_coroutine):
                        self.fail(messages.INVALID_RETURN_TYPE_FOR_GENERATOR, typ)

                    # Python 2 generators aren't allowed to return values.
                    if (self.options.python_version[0] == 2 and
                            isinstance(typ.ret_type, Instance) and
                            typ.ret_type.type.fullname() == 'typing.Generator'):
                        if not isinstance(typ.ret_type.args[2], (Void, NoneTyp, AnyType)):
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

                    # Refuse covariant parameter type variables
                    if isinstance(arg_type, TypeVarType):
                        if arg_type.variance == COVARIANT:
                            self.fail(messages.FUNCTION_PARAMETER_CANNOT_BE_COVARIANT,
                                      arg_type)

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
                    init = arg.initialization_statement
                    if init:
                        self.accept(init)

            # Type check body in a new scope.
            with self.binder.frame_context():
                self.accept(item.body)

            self.return_types.pop()

            self.binder = old_binder

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

        if isinstance(forward_type, CallableType):
            # TODO check argument kinds
            if len(forward_type.arg_types) < 1:
                # Not a valid operator method -- can't succeed anyway.
                return

            # Construct normalized function signatures corresponding to the
            # operator methods. The first argument is the left operand and the
            # second operand is the right argument -- we switch the order of
            # the arguments of the reverse method.
            forward_tweaked = CallableType(
                [forward_base, forward_type.arg_types[0]],
                [nodes.ARG_POS] * 2,
                [None] * 2,
                forward_type.ret_type,
                forward_type.fallback,
                name=forward_type.name)
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
        elif isinstance(forward_type, Overloaded):
            for item in forward_type.items():
                self.check_overlapping_op_methods(
                    reverse_type, reverse_name, reverse_class,
                    item, forward_name, forward_base, context)
        elif not isinstance(forward_type, AnyType):
            self.msg.forward_operator_not_callable(forward_name, context)

    def check_inplace_operator_method(self, defn: FuncBase) -> None:
        """Check an inplace operator method such as __iadd__.

        They cannot arbitrarily overlap with __add__.
        """
        method = defn.name()
        if method not in nodes.inplace_operator_methods:
            return
        typ = self.method_type(defn)
        cls = defn.info
        other_method = '__' + method[3:]
        if cls.has_readable_member(other_method):
            instance = self_type(cls)
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

    def check_getattr_method(self, typ: CallableType, context: Context) -> None:
        method_type = CallableType([AnyType(), self.named_type('builtins.str')],
                                   [nodes.ARG_POS, nodes.ARG_POS],
                                   [None],
                                   AnyType(),
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

    def check_method_override(self, defn: FuncBase) -> None:
        """Check if function definition is compatible with base classes."""
        # Check against definitions in base classes.
        for base in defn.info.mro[1:]:
            self.check_method_or_accessor_override_for_base(defn, base)

    def check_method_or_accessor_override_for_base(self, defn: FuncBase,
                                                   base: TypeInfo) -> None:
        """Check if method definition is compatible with a base class."""
        if base:
            name = defn.name()
            if name not in ('__init__', '__new__'):
                # Check method override (__init__ and __new__ are special).
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
            self, defn: FuncBase, name: str, base: TypeInfo) -> None:
        base_attr = base.names.get(name)
        if base_attr:
            # The name of the method is defined in the base class.

            # Construct the type of the overriding method.
            typ = self.method_type(defn)
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
            if isinstance(original_type, FunctionLike):
                original = map_type_from_supertype(
                    method_type(original_type),
                    defn.info, base)
                # Check that the types are compatible.
                # TODO overloaded signatures
                self.check_override(typ,
                                    cast(FunctionLike, original),
                                    defn.name(),
                                    name,
                                    base.name(),
                                    defn)
            else:
                self.msg.signature_incompatible_with_supertype(
                    defn.name(), name, base.name(), defn)

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
        if not is_subtype(override, original):
            fail = True
        elif (not isinstance(original, Overloaded) and
              isinstance(override, Overloaded) and
              name in nodes.reverse_op_methods.keys()):
            # Operator method overrides cannot introduce overloading, as
            # this could be unsafe with reverse operator methods.
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
                # are erased, then it is definitely an incompatiblity.

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

    def visit_class_def(self, defn: ClassDef) -> Type:
        """Type check a class definition."""
        typ = defn.info
        self.errors.push_type(defn.name)
        self.enter_partial_types()
        old_binder = self.binder
        self.binder = ConditionalTypeBinder()
        with self.binder.frame_context():
            self.accept(defn.defs)
        self.binder = old_binder
        if not defn.has_incompatible_baseclass:
            # Otherwise we've already found errors; more errors are not useful
            self.check_multiple_inheritance(typ)
        self.leave_partial_types()
        self.errors.pop_type()

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
        # Verify that base class layouts are compatible.
        builtin_bases = [nearest_builtin_ancestor(base.type)
                         for base in typ.bases]
        for base1 in builtin_bases:
            for base2 in builtin_bases:
                if not (base1 in base2.mro or base2 in base1.mro):
                    self.fail(messages.INSTANCE_LAYOUT_CONFLICT, typ)

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
            first_sig = method_type(first_type)
            second_sig = method_type(second_type)
            ok = is_subtype(first_sig, second_sig)
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

    def visit_import_from(self, node: ImportFrom) -> Type:
        self.check_import(node)

    def visit_import_all(self, node: ImportAll) -> Type:
        self.check_import(node)

    def check_import(self, node: ImportBase) -> Type:
        for assign in node.assignments:
            lvalue = assign.lvalues[0]
            lvalue_type, _, __ = self.check_lvalue(lvalue)
            if lvalue_type is None:
                # TODO: This is broken.
                lvalue_type = AnyType()
            message = '{} "{}"'.format(messages.INCOMPATIBLE_IMPORT_OF,
                                       cast(NameExpr, assign.rvalue).name)
            self.check_simple_assignment(lvalue_type, assign.rvalue, node,
                                         msg=message, lvalue_name='local name',
                                         rvalue_name='imported name')

    #
    # Statements
    #

    def visit_block(self, b: Block) -> Type:
        if b.is_unreachable:
            return None
        for s in b.body:
            self.accept(s)
            if self.binder.breaking_out:
                break

    def visit_assignment_stmt(self, s: AssignmentStmt) -> Type:
        """Type check an assignment statement.

        Handle all kinds of assignment statements (simple, indexed, multiple).
        """
        self.check_assignment(s.lvalues[-1], s.rvalue, s.type is None)

        if len(s.lvalues) > 1:
            # Chained assignment (e.g. x = y = ...).
            # Make sure that rvalue type will not be reinferred.
            if s.rvalue not in self.type_map:
                self.accept(s.rvalue)
            rvalue = self.temp_node(self.type_map[s.rvalue], s)
            for lv in s.lvalues[:-1]:
                self.check_assignment(lv, rvalue, s.type is None)

    def check_assignment(self, lvalue: Node, rvalue: Node, infer_lvalue_type: bool = True) -> None:
        """Type check a single assignment: lvalue = rvalue."""
        if isinstance(lvalue, TupleExpr) or isinstance(lvalue, ListExpr):
            self.check_assignment_to_multiple_lvalues(lvalue.items, rvalue, lvalue,
                                                      infer_lvalue_type)
        else:
            lvalue_type, index_lvalue, inferred = self.check_lvalue(lvalue)
            if lvalue_type:
                if isinstance(lvalue_type, PartialType) and lvalue_type.type is None:
                    # Try to infer a proper type for a variable with a partial None type.
                    rvalue_type = self.accept(rvalue)
                    if isinstance(rvalue_type, NoneTyp):
                        # This doesn't actually provide any additional information -- multiple
                        # None initializers preserve the partial None type.
                        return

                    if is_valid_inferred_type(rvalue_type):
                        var = lvalue_type.var
                        partial_types = self.find_partial_types(var)
                        if partial_types is not None:
                            if not self.current_node_deferred:
                                if experiments.STRICT_OPTIONAL:
                                    var.type = UnionType.make_simplified_union(
                                        [rvalue_type, NoneTyp()])
                                else:
                                    var.type = rvalue_type
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
                        lvalue.node.is_initialized_in_class):
                    # Allow None's to be assigned to class variables with non-Optional types.
                    rvalue_type = lvalue_type
                else:
                    rvalue_type = self.check_simple_assignment(lvalue_type, rvalue, lvalue)

                if rvalue_type and infer_lvalue_type:
                    self.binder.assign_type(lvalue,
                                            rvalue_type,
                                            lvalue_type,
                                            self.typing_mode_weak())
            elif index_lvalue:
                self.check_indexed_assignment(index_lvalue, rvalue, rvalue)

            if inferred:
                self.infer_variable_type(inferred, lvalue, self.accept(rvalue),
                                         rvalue)

    def check_assignment_to_multiple_lvalues(self, lvalues: List[Node], rvalue: Node,
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

    def check_rvalue_count_in_assignment(self, lvalues: List[Node], rvalue_count: int,
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

    def check_multi_assignment(self, lvalues: List[Node],
                               rvalue: Node,
                               context: Context,
                               infer_lvalue_type: bool = True,
                               msg: str = None) -> None:
        """Check the assignment of one rvalue to a number of lvalues."""

        # Infer the type of an ordinary rvalue expression.
        rvalue_type = self.accept(rvalue)  # TODO maybe elsewhere; redundant
        undefined_rvalue = False

        if isinstance(rvalue_type, AnyType):
            for lv in lvalues:
                if isinstance(lv, StarExpr):
                    lv = lv.expr
                self.check_assignment(lv, self.temp_node(AnyType(), context), infer_lvalue_type)
        elif isinstance(rvalue_type, TupleType):
            self.check_multi_assignment_from_tuple(lvalues, rvalue, rvalue_type,
                                                  context, undefined_rvalue, infer_lvalue_type)
        else:
            self.check_multi_assignment_from_iterable(lvalues, rvalue_type,
                                                     context, infer_lvalue_type)

    def check_multi_assignment_from_tuple(self, lvalues: List[Node], rvalue: Node,
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
                rvalue_type = cast(TupleType, self.accept(rvalue, lvalue_type))

            left_rv_types, star_rv_types, right_rv_types = self.split_around_star(
                rvalue_type.items, star_index, len(lvalues))

            for lv, rv_type in zip(left_lvs, left_rv_types):
                self.check_assignment(lv, self.temp_node(rv_type, context), infer_lvalue_type)
            if star_lv:
                nodes = [self.temp_node(rv_type, context) for rv_type in star_rv_types]
                list_expr = ListExpr(nodes)
                list_expr.set_line(context.get_line())
                self.check_assignment(star_lv.expr, list_expr, infer_lvalue_type)
            for lv, rv_type in zip(right_lvs, right_rv_types):
                self.check_assignment(lv, self.temp_node(rv_type, context), infer_lvalue_type)

    def lvalue_type_for_inference(self, lvalues: List[Node], rvalue_type: TupleType) -> Type:
        star_index = next((i for i, lv in enumerate(lvalues)
                           if isinstance(lv, StarExpr)), len(lvalues))
        left_lvs = lvalues[:star_index]
        star_lv = cast(StarExpr, lvalues[star_index]) if star_index != len(lvalues) else None
        right_lvs = lvalues[star_index + 1:]
        left_rv_types, star_rv_types, right_rv_types = self.split_around_star(
            rvalue_type.items, star_index, len(lvalues))

        type_parameters = []  # type: List[Type]

        def append_types_for_inference(lvs: List[Node], rv_types: List[Type]) -> None:
            for lv, rv_type in zip(lvs, rv_types):
                sub_lvalue_type, index_expr, inferred = self.check_lvalue(lv)
                if sub_lvalue_type:
                    type_parameters.append(sub_lvalue_type)
                else:  # index lvalue
                    # TODO Figure out more precise type context, probably
                    #      based on the type signature of the _set method.
                    type_parameters.append(rv_type)

        append_types_for_inference(left_lvs, left_rv_types)

        if star_lv:
            sub_lvalue_type, index_expr, inferred = self.check_lvalue(star_lv.expr)
            if sub_lvalue_type:
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
        right_index = nr_right_of_star if -nr_right_of_star != 0 else len(items)
        left = items[:star_index]
        star = items[star_index:right_index]
        right = items[right_index:]
        return (left, star, right)

    def type_is_iterable(self, type: Type) -> bool:
        return (is_subtype(type, self.named_generic_type('typing.Iterable',
                                                        [AnyType()])) and
                isinstance(type, Instance))

    def check_multi_assignment_from_iterable(self, lvalues: List[Node], rvalue_type: Type,
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

    def check_lvalue(self, lvalue: Node) -> Tuple[Type, IndexExpr, Var]:
        lvalue_type = None  # type: Type
        index_lvalue = None  # type: IndexExpr
        inferred = None  # type: Var

        if self.is_definition(lvalue):
            if isinstance(lvalue, NameExpr):
                inferred = cast(Var, lvalue.node)
                assert isinstance(inferred, Var)
            else:
                m = cast(MemberExpr, lvalue)
                self.accept(m.expr)
                inferred = m.def_var
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
            types = [self.check_lvalue(sub_expr)[0] for sub_expr in lvalue.items]
            lvalue_type = TupleType(types, self.named_type('builtins.tuple'))
        else:
            lvalue_type = self.accept(lvalue)

        return lvalue_type, index_lvalue, inferred

    def is_definition(self, s: Node) -> bool:
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

    def infer_variable_type(self, name: Var, lvalue: Node,
                            init_type: Type, context: Context) -> None:
        """Infer the type of initialized variables from initializer type."""
        if self.typing_mode_weak():
            self.set_inferred_type(name, lvalue, AnyType())
            self.binder.assign_type(lvalue, init_type, self.binder.get_declaration(lvalue), True)
        elif self.is_unusable_type(init_type):
            self.check_usable_type(init_type, context)
            self.set_inference_error_fallback_type(name, lvalue, init_type, context)
        elif isinstance(init_type, DeletedType):
            self.msg.deleted_as_rvalue(init_type, context)
        elif not is_valid_inferred_type(init_type):
            # We cannot use the type of the initialization expression for full type
            # inference (it's not specific enough), but we might be able to give
            # partial type which will be made more specific later. A partial type
            # gets generated in assignment like 'x = []' where item type is not known.
            if not self.infer_partial_type(name, lvalue, init_type):
                self.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
                self.set_inference_error_fallback_type(name, lvalue, init_type, context)
        else:
            # Infer type of the target.

            # Make the type more general (strip away function names etc.).
            init_type = strip_type(init_type)

            self.set_inferred_type(name, lvalue, init_type)

    def infer_partial_type(self, name: Var, lvalue: Node, init_type: Type) -> bool:
        if isinstance(init_type, (NoneTyp, UninhabitedType)):
            partial_type = PartialType(None, name, [init_type])
        elif isinstance(init_type, Instance):
            fullname = init_type.type.fullname()
            if (isinstance(lvalue, NameExpr) and
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

    def set_inferred_type(self, var: Var, lvalue: Node, type: Type) -> None:
        """Store inferred variable type.

        Store the type to both the variable node and the expression node that
        refers to the variable (lvalue). If var is None, do nothing.
        """
        if var and not self.current_node_deferred:
            var.type = type
            self.store_type(lvalue, type)

    def set_inference_error_fallback_type(self, var: Var, lvalue: Node, type: Type,
                                          context: Context) -> None:
        """If errors on context line are ignored, store dummy type for variable.

        If a program ignores error on type inference error, the variable should get some
        inferred type so that if can used later on in the program. Example:

          x = []  # type: ignore
          x.append(1)   # Should be ok!

        We implement this here by giving x a valid type (Any).
        """
        if context.get_line() in self.errors.ignored_lines[self.errors.file]:
            self.set_inferred_type(var, lvalue, AnyType())

    def narrow_type_from_binder(self, expr: Node, known_type: Type) -> Type:
        if expr.literal >= LITERAL_TYPE:
            restriction = self.binder.get(expr)
            if restriction:
                ans = meet_simple(known_type, restriction)
                return ans
        return known_type

    def check_simple_assignment(self, lvalue_type: Type, rvalue: Node,
                                context: Node,
                                msg: str = messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT,
                                lvalue_name: str = 'variable',
                                rvalue_name: str = 'expression') -> Type:
        if self.is_stub and isinstance(rvalue, EllipsisExpr):
            # '...' is always a valid initializer in a stub.
            return AnyType()
        else:
            rvalue_type = self.accept(rvalue, lvalue_type)
            if isinstance(rvalue_type, DeletedType):
                self.msg.deleted_as_rvalue(rvalue_type, context)
            if self.typing_mode_weak():
                return rvalue_type
            if isinstance(lvalue_type, DeletedType):
                self.msg.deleted_as_lvalue(lvalue_type, context)
            else:
                self.check_subtype(rvalue_type, lvalue_type, context, msg,
                                   '{} has type'.format(rvalue_name),
                                   '{} has type'.format(lvalue_name))
            return rvalue_type

    def check_indexed_assignment(self, lvalue: IndexExpr,
                                 rvalue: Node, context: Context) -> None:
        """Type check indexed assignment base[index] = rvalue.

        The lvalue argument is the base[index] expression.
        """
        self.try_infer_partial_type_from_indexed_assignment(lvalue, rvalue)
        basetype = self.accept(lvalue.base)
        method_type = self.expr_checker.analyze_external_member_access(
            '__setitem__', basetype, context)
        lvalue.method_type = method_type
        self.expr_checker.check_call(method_type, [lvalue.index, rvalue],
                                     [nodes.ARG_POS, nodes.ARG_POS],
                                     context)

    def try_infer_partial_type_from_indexed_assignment(
            self, lvalue: IndexExpr, rvalue: Node) -> None:
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
                    key_type = self.accept(lvalue.index)
                    value_type = self.accept(rvalue)
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

    def visit_expression_stmt(self, s: ExpressionStmt) -> Type:
        self.accept(s.expr)

    def visit_return_stmt(self, s: ReturnStmt) -> Type:
        """Type check a return statement."""
        self.binder.breaking_out = True
        if self.is_within_function():
            defn = self.function_stack[-1]
            if defn.is_generator:
                return_type = self.get_generator_return_type(self.return_types[-1],
                                                             defn.is_coroutine)
            else:
                return_type = self.return_types[-1]

            if s.expr:
                # Return with a value.
                typ = self.accept(s.expr, return_type)
                # Returning a value of type Any is always fine.
                if isinstance(typ, AnyType):
                    return None

                if self.is_unusable_type(return_type):
                    # Lambdas are allowed to have a unusable returns.
                    # Functions returning a value of type None are allowed to have a Void return.
                    if isinstance(self.function_stack[-1], FuncExpr) or isinstance(typ, NoneTyp):
                        return None
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
                # Empty returns are valid in Generators with Any typed returns.
                if (self.function_stack[-1].is_generator and isinstance(return_type, AnyType)):
                    return None

                if isinstance(return_type, (Void, NoneTyp, AnyType)):
                    return None

                if self.typing_mode_full():
                    self.fail(messages.RETURN_VALUE_EXPECTED, s)

    def wrap_generic_type(self, typ: Instance, rtyp: Instance, check_type:
                          str, context: Context) -> Type:
        n_diff = self.count_nested_types(rtyp, check_type) - self.count_nested_types(typ,
                                                                                     check_type)
        if n_diff == 1:
            return self.named_generic_type(check_type, [typ])
        elif n_diff == 0 or n_diff > 1:
            self.fail(messages.INCOMPATIBLE_RETURN_VALUE_TYPE
                + ": expected {}, got {}".format(rtyp, typ), context)
            return typ
        return typ

    def count_nested_types(self, typ: Instance, check_type: str) -> int:
        c = 0
        while is_subtype(typ, self.named_type(check_type)):
            c += 1
            typ = map_instance_to_supertype(self.named_generic_type(check_type, typ.args),
                                            self.lookup_typeinfo(check_type))
            if typ.args:
                typ = cast(Instance, typ.args[0])
            else:
                return c
        return c

    def visit_if_stmt(self, s: IfStmt) -> Type:
        """Type check an if statement."""
        breaking_out = True
        # This frame records the knowledge from previous if/elif clauses not being taken.
        with self.binder.frame_context():
            for e, b in zip(s.expr, s.body):
                t = self.accept(e)
                self.check_usable_type(t, e)
                if_map, else_map = find_isinstance_check(
                    e, self.type_map,
                    self.typing_mode_weak()
                )
                if if_map is None:
                    # The condition is always false
                    # XXX should issue a warning?
                    pass
                else:
                    # Only type check body if the if condition can be true.
                    with self.binder.frame_context(2):
                        if if_map:
                            for var, type in if_map.items():
                                self.binder.push(var, type)

                        self.accept(b)
                    breaking_out = breaking_out and self.binder.last_pop_breaking_out

                    if else_map:
                        for var, type in else_map.items():
                            self.binder.push(var, type)
                if else_map is None:
                    # The condition is always true => remaining elif/else blocks
                    # can never be reached.

                    # Might also want to issue a warning
                    # print("Warning: isinstance always true")
                    break
            else:  # Didn't break => can't prove one of the conditions is always true
                with self.binder.frame_context(2):
                    if s.else_body:
                        self.accept(s.else_body)
                breaking_out = breaking_out and self.binder.last_pop_breaking_out
        if breaking_out:
            self.binder.breaking_out = True
        return None

    def visit_while_stmt(self, s: WhileStmt) -> Type:
        """Type check a while statement."""
        self.accept_loop(IfStmt([s.expr], [s.body], None), s.else_body)

    def visit_operator_assignment_stmt(self,
                                       s: OperatorAssignmentStmt) -> Type:
        """Type check an operator assignment statement, e.g. x += 1."""
        lvalue_type = self.accept(s.lvalue)
        inplace, method = infer_operator_assignment_method(lvalue_type, s.op)
        rvalue_type, method_type = self.expr_checker.check_op(
            method, lvalue_type, s.rvalue, s)

        if isinstance(s.lvalue, IndexExpr) and not inplace:
            self.check_indexed_assignment(s.lvalue, s.rvalue, s.rvalue)
        else:
            if not is_subtype(rvalue_type, lvalue_type):
                self.msg.incompatible_operator_assignment(s.op, s)

    def visit_assert_stmt(self, s: AssertStmt) -> Type:
        self.accept(s.expr)

        # If this is asserting some isinstance check, bind that type in the following code
        true_map, _ = find_isinstance_check(
            s.expr, self.type_map,
            self.typing_mode_weak()
        )

        if true_map:
            for var, type in true_map.items():
                self.binder.push(var, type)

    def visit_raise_stmt(self, s: RaiseStmt) -> Type:
        """Type check a raise statement."""
        self.binder.breaking_out = True
        if s.expr:
            self.type_check_raise(s.expr, s)
        if s.from_expr:
            self.type_check_raise(s.from_expr, s)

    def type_check_raise(self, e: Node, s: RaiseStmt) -> None:
        typ = self.accept(e)
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
        self.check_subtype(typ,
                           self.named_type('builtins.BaseException'), s,
                           messages.INVALID_EXCEPTION)

    def visit_try_stmt(self, s: TryStmt) -> Type:
        """Type check a try statement."""
        # Our enclosing frame will get the result if the try/except falls through.
        # This one gets all possible intermediate states
        with self.binder.frame_context():
            if s.finally_body:
                self.binder.try_frames.add(len(self.binder.frames) - 1)
                breaking_out = self.visit_try_without_finally(s)
                self.binder.try_frames.remove(len(self.binder.frames) - 1)
                # First we check finally_body is type safe for all intermediate frames
                self.accept(s.finally_body)
                breaking_out = breaking_out or self.binder.breaking_out
            else:
                breaking_out = self.visit_try_without_finally(s)

        if not breaking_out and s.finally_body:
            # Then we try again for the more restricted set of options that can fall through
            self.accept(s.finally_body)
        self.binder.breaking_out = breaking_out
        return None

    def visit_try_without_finally(self, s: TryStmt) -> bool:
        """Type check a try statement, ignoring the finally block.

        Return whether we are guaranteed to be breaking out.
        Otherwise, it will place the results possible frames of
        that don't break out into self.binder.frames[-2].
        """
        breaking_out = True
        # This frame records the possible states that exceptions can leave variables in
        # during the try: block
        with self.binder.frame_context():
            with self.binder.frame_context(3):
                self.binder.try_frames.add(len(self.binder.frames) - 2)
                self.accept(s.body)
                self.binder.try_frames.remove(len(self.binder.frames) - 2)
                if s.else_body:
                    self.accept(s.else_body)
            breaking_out = breaking_out and self.binder.last_pop_breaking_out
            for i in range(len(s.handlers)):
                with self.binder.frame_context(3):
                    if s.types[i]:
                        t = self.visit_except_handler_test(s.types[i])
                        if s.vars[i]:
                            # To support local variables, we make this a definition line,
                            # causing assignment to set the variable's type.
                            s.vars[i].is_def = True
                            self.check_assignment(s.vars[i], self.temp_node(t, s.vars[i]))
                    self.accept(s.handlers[i])
                    if s.vars[i]:
                        # Exception variables are deleted in python 3 but not python 2.
                        # But, since it's bad form in python 2 and the type checking
                        # wouldn't work very well, we delete it anyway.

                        # Unfortunately, this doesn't let us detect usage before the
                        # try/except block.
                        if self.options.python_version[0] >= 3:
                            source = s.vars[i].name
                        else:
                            source = ('(exception variable "{}", which we do not accept outside'
                                      'except: blocks even in python 2)'.format(s.vars[i].name))
                        var = cast(Var, s.vars[i].node)
                        var.type = DeletedType(source=source)
                        self.binder.cleanse(s.vars[i])
                breaking_out = breaking_out and self.binder.last_pop_breaking_out
        return breaking_out

    def visit_except_handler_test(self, n: Node) -> Type:
        """Type check an exception handler test clause."""
        type = self.accept(n)

        all_types = []  # type: List[Type]
        test_types = type.items if isinstance(type, TupleType) else [type]

        for ttype in test_types:
            if isinstance(ttype, AnyType):
                all_types.append(ttype)
                continue

            if not isinstance(ttype, FunctionLike):
                self.fail(messages.INVALID_EXCEPTION_TYPE, n)
                return AnyType()

            item = ttype.items()[0]
            ret_type = item.ret_type
            if not (is_subtype(ret_type, self.named_type('builtins.BaseException'))
                    and item.is_type_obj()):
                self.fail(messages.INVALID_EXCEPTION_TYPE, n)
                return AnyType()

            all_types.append(ret_type)

        return UnionType.make_simplified_union(all_types)

    def visit_for_stmt(self, s: ForStmt) -> Type:
        """Type check a for statement."""
        if s.is_async:
            item_type = self.analyze_async_iterable_item_type(s.expr)
        else:
            item_type = self.analyze_iterable_item_type(s.expr)
        self.analyze_index_variables(s.index, item_type, s)
        self.accept_loop(s.body, s.else_body)

    def analyze_async_iterable_item_type(self, expr: Node) -> Type:
        """Analyse async iterable expression and return iterator item type."""
        iterable = self.accept(expr)

        self.check_usable_type(iterable, expr)

        self.check_subtype(iterable,
                           self.named_generic_type('typing.AsyncIterable',
                                                   [AnyType()]),
                           expr, messages.ASYNC_ITERABLE_EXPECTED)

        echk = self.expr_checker
        method = echk.analyze_external_member_access('__aiter__', iterable, expr)
        iterator = echk.check_call(method, [], [], expr)[0]
        method = echk.analyze_external_member_access('__anext__', iterator, expr)
        awaitable = echk.check_call(method, [], [], expr)[0]
        return self.check_awaitable_expr(awaitable, expr,
                                         messages.INCOMPATIBLE_TYPES_IN_ASYNC_FOR)

    def analyze_iterable_item_type(self, expr: Node) -> Type:
        """Analyse iterable expression and return iterator item type."""
        iterable = self.accept(expr)

        self.check_usable_type(iterable, expr)
        if isinstance(iterable, TupleType):
            if experiments.STRICT_OPTIONAL:
                joined = UninhabitedType()  # type: Type
            else:
                joined = NoneTyp()
            for item in iterable.items:
                joined = join_types(joined, item)
            if isinstance(joined, ErrorType):
                self.fail(messages.CANNOT_INFER_ITEM_TYPE, expr)
                return AnyType()
            return joined
        else:
            # Non-tuple iterable.
            self.check_subtype(iterable,
                               self.named_generic_type('typing.Iterable',
                                                       [AnyType()]),
                               expr, messages.ITERABLE_EXPECTED)

            echk = self.expr_checker
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

    def analyze_index_variables(self, index: Node, item_type: Type,
                                context: Context) -> None:
        """Type check or infer for loop or list comprehension index vars."""
        self.check_assignment(index, self.temp_node(item_type, context))

    def visit_del_stmt(self, s: DelStmt) -> Type:
        if isinstance(s.expr, IndexExpr):
            e = s.expr
            m = MemberExpr(e.base, '__delitem__')
            m.line = s.line
            c = CallExpr(m, [e.index], [nodes.ARG_POS], [None])
            c.line = s.line
            return c.accept(self)
        else:
            def flatten(t: Node) -> List[Node]:
                """Flatten a nested sequence of tuples/lists into one list of nodes."""
                if isinstance(t, TupleExpr) or isinstance(t, ListExpr):
                    return [b for a in t.items for b in flatten(a)]
                else:
                    return [t]

            s.expr.accept(self)
            for elt in flatten(s.expr):
                if isinstance(elt, NameExpr):
                    self.binder.assign_type(elt,
                                            DeletedType(source=elt.name),
                                            self.binder.get_declaration(elt),
                                            self.typing_mode_weak())
            return None

    def visit_decorator(self, e: Decorator) -> Type:
        for d in e.decorators:
            if isinstance(d, RefExpr):
                if d.fullname == 'typing.no_type_check':
                    e.var.type = AnyType()
                    e.var.is_ready = True
                    return NoneTyp()

        e.func.accept(self)
        sig = self.function_type(e.func)  # type: Type
        # Process decorators from the inside out.
        for i in range(len(e.decorators)):
            n = len(e.decorators) - 1 - i
            d = e.decorators[n]
            if isinstance(d, NameExpr) and d.fullname == 'typing.overload':
                self.fail('Single overload definition, multiple required', e)
                continue
            dec = self.accept(d)
            temp = self.temp_node(sig)
            sig, t2 = self.expr_checker.check_call(dec, [temp],
                                                   [nodes.ARG_POS], e)
        sig = cast(FunctionLike, sig)
        sig = set_callable_name(sig, e.func)
        e.var.type = sig
        e.var.is_ready = True
        if e.func.is_property:
            self.check_incompatible_property_override(e)

    def check_incompatible_property_override(self, e: Decorator) -> None:
        if not e.var.is_settable_property and e.func.info is not None:
            name = e.func.name()
            for base in e.func.info.mro[1:]:
                base_attr = base.names.get(name)
                if not base_attr:
                    continue
                if (isinstance(base_attr.node, OverloadedFuncDef) and
                        base_attr.node.is_property and
                        base_attr.node.items[0].var.is_settable_property):
                    self.fail(messages.READ_ONLY_PROPERTY_OVERRIDES_READ_WRITE, e)

    def visit_with_stmt(self, s: WithStmt) -> Type:
        for expr, target in zip(s.expr, s.target):
            if s.is_async:
                self.check_async_with_item(expr, target)
            else:
                self.check_with_item(expr, target)
        self.accept(s.body)

    def check_async_with_item(self, expr: Expression, target: Expression) -> None:
        echk = self.expr_checker
        ctx = self.accept(expr)
        enter = echk.analyze_external_member_access('__aenter__', ctx, expr)
        obj = echk.check_call(enter, [], [], expr)[0]
        obj = self.check_awaitable_expr(
            obj, expr, messages.INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AENTER)
        if target:
            self.check_assignment(target, self.temp_node(obj, expr))
        exit = echk.analyze_external_member_access('__aexit__', ctx, expr)
        arg = self.temp_node(AnyType(), expr)
        res = echk.check_call(exit, [arg] * 3, [nodes.ARG_POS] * 3, expr)[0]
        self.check_awaitable_expr(
            res, expr, messages.INCOMPATIBLE_TYPES_IN_ASYNC_WITH_AEXIT)

    def check_with_item(self, expr: Expression, target: Expression) -> None:
        echk = self.expr_checker
        ctx = self.accept(expr)
        enter = echk.analyze_external_member_access('__enter__', ctx, expr)
        obj = echk.check_call(enter, [], [], expr)[0]
        if target:
            self.check_assignment(target, self.temp_node(obj, expr))
        exit = echk.analyze_external_member_access('__exit__', ctx, expr)
        arg = self.temp_node(AnyType(), expr)
        echk.check_call(exit, [arg] * 3, [nodes.ARG_POS] * 3, expr)

    def visit_print_stmt(self, s: PrintStmt) -> Type:
        for arg in s.args:
            self.accept(arg)
        if s.target:
            target_type = self.accept(s.target)
            if not isinstance(target_type, NoneTyp):
                # TODO: Also verify the type of 'write'.
                self.expr_checker.analyze_external_member_access('write', target_type, s.target)

    #
    # Expressions
    #

    def visit_name_expr(self, e: NameExpr) -> Type:
        return self.expr_checker.visit_name_expr(e)

    def visit_call_expr(self, e: CallExpr) -> Type:
        return self.expr_checker.visit_call_expr(e)

    def visit_yield_from_expr(self, e: YieldFromExpr) -> Type:
        # NOTE: Whether `yield from` accepts an `async def` decorated
        # with `@types.coroutine` (or `@asyncio.coroutine`) depends on
        # whether the generator containing the `yield from` is itself
        # thus decorated.  But it accepts a generator regardless of
        # how it's decorated.
        return_type = self.return_types[-1]
        subexpr_type = self.accept(e.expr, return_type)
        iter_type = None  # type: Type

        # Check that the expr is an instance of Iterable and get the type of the iterator produced
        # by __iter__.
        if isinstance(subexpr_type, AnyType):
            iter_type = AnyType()
        elif (isinstance(subexpr_type, Instance) and
                is_subtype(subexpr_type, self.named_type('typing.Iterable'))):
            if self.is_async_def(subexpr_type) and not self.has_coroutine_decorator(return_type):
                self.msg.yield_from_invalid_operand_type(subexpr_type, e)
            iter_method_type = self.expr_checker.analyze_external_member_access(
                '__iter__',
                subexpr_type,
                AnyType())

            generic_generator_type = self.named_generic_type('typing.Generator',
                                                             [AnyType(), AnyType(), AnyType()])
            iter_type, _ = self.expr_checker.check_call(iter_method_type, [], [],
                                                        context=generic_generator_type)
        else:
            if not (self.is_async_def(subexpr_type) and self.has_coroutine_decorator(return_type)):
                self.msg.yield_from_invalid_operand_type(subexpr_type, e)
                iter_type = AnyType()
            else:
                iter_type = self.check_awaitable_expr(subexpr_type, e,
                                                      messages.INCOMPATIBLE_TYPES_IN_YIELD_FROM)

        # Check that the iterator's item type matches the type yielded by the Generator function
        # containing this `yield from` expression.
        expected_item_type = self.get_generator_yield_type(return_type, False)
        actual_item_type = self.get_generator_yield_type(iter_type, False)

        self.check_subtype(actual_item_type, expected_item_type, e,
                           messages.INCOMPATIBLE_TYPES_IN_YIELD_FROM,
                           'actual type', 'expected type')

        # Determine the type of the entire yield from expression.
        if (isinstance(iter_type, Instance) and
                iter_type.type.fullname() == 'typing.Generator'):
            return self.get_generator_return_type(iter_type, False)
        else:
            # Non-Generators don't return anything from `yield from` expressions.
            # However special-case Any (which might be produced by an error).
            if isinstance(actual_item_type, AnyType):
                return AnyType()
            else:
                if experiments.STRICT_OPTIONAL:
                    return NoneTyp(is_ret_type=True)
                else:
                    return Void()

    def has_coroutine_decorator(self, t: Type) -> bool:
        """Whether t came from a function decorated with `@coroutine`."""
        return isinstance(t, Instance) and t.type.fullname() == 'typing.AwaitableGenerator'

    def is_async_def(self, t: Type) -> bool:
        """Whether t came from a function defined using `async def`."""
        # In check_func_def(), when we see a function decorated with
        # `@typing.coroutine` or `@async.coroutine`, we change the
        # return type to typing.AwaitableGenerator[...], so that its
        # type is compatible with either Generator or Awaitable.
        # But for the check here we need to know whether the original
        # function (before decoration) was an `async def`.  The
        # AwaitableGenerator type conveniently preserves the original
        # type as its 4th parameter (3rd when using 0-origin indexing
        # :-), so that we can recover that information here.
        # (We really need to see whether the original, undecorated
        # function was an `async def`, which is orthogonal to its
        # decorations.)
        if (isinstance(t, Instance)
                and t.type.fullname() == 'typing.AwaitableGenerator'
                and len(t.args) >= 4):
            t = t.args[3]
        return isinstance(t, Instance) and t.type.fullname() == 'typing.Awaitable'

    def visit_member_expr(self, e: MemberExpr) -> Type:
        return self.expr_checker.visit_member_expr(e)

    def visit_break_stmt(self, s: BreakStmt) -> Type:
        self.binder.breaking_out = True
        self.binder.allow_jump(self.binder.loop_frames[-1] - 1)
        return None

    def visit_continue_stmt(self, s: ContinueStmt) -> Type:
        self.binder.breaking_out = True
        self.binder.allow_jump(self.binder.loop_frames[-1])
        return None

    def visit_int_expr(self, e: IntExpr) -> Type:
        return self.expr_checker.visit_int_expr(e)

    def visit_str_expr(self, e: StrExpr) -> Type:
        return self.expr_checker.visit_str_expr(e)

    def visit_bytes_expr(self, e: BytesExpr) -> Type:
        return self.expr_checker.visit_bytes_expr(e)

    def visit_unicode_expr(self, e: UnicodeExpr) -> Type:
        return self.expr_checker.visit_unicode_expr(e)

    def visit_float_expr(self, e: FloatExpr) -> Type:
        return self.expr_checker.visit_float_expr(e)

    def visit_complex_expr(self, e: ComplexExpr) -> Type:
        return self.expr_checker.visit_complex_expr(e)

    def visit_ellipsis(self, e: EllipsisExpr) -> Type:
        return self.expr_checker.visit_ellipsis(e)

    def visit_op_expr(self, e: OpExpr) -> Type:
        return self.expr_checker.visit_op_expr(e)

    def visit_comparison_expr(self, e: ComparisonExpr) -> Type:
        return self.expr_checker.visit_comparison_expr(e)

    def visit_unary_expr(self, e: UnaryExpr) -> Type:
        return self.expr_checker.visit_unary_expr(e)

    def visit_index_expr(self, e: IndexExpr) -> Type:
        return self.expr_checker.visit_index_expr(e)

    def visit_cast_expr(self, e: CastExpr) -> Type:
        return self.expr_checker.visit_cast_expr(e)

    def visit_reveal_type_expr(self, e: RevealTypeExpr) -> Type:
        return self.expr_checker.visit_reveal_type_expr(e)

    def visit_super_expr(self, e: SuperExpr) -> Type:
        return self.expr_checker.visit_super_expr(e)

    def visit_type_application(self, e: TypeApplication) -> Type:
        return self.expr_checker.visit_type_application(e)

    def visit_type_alias_expr(self, e: TypeAliasExpr) -> Type:
        return self.expr_checker.visit_type_alias_expr(e)

    def visit_type_var_expr(self, e: TypeVarExpr) -> Type:
        # TODO: Perhaps return a special type used for type variables only?
        return AnyType()

    def visit_newtype_expr(self, e: NewTypeExpr) -> Type:
        return AnyType()

    def visit_namedtuple_expr(self, e: NamedTupleExpr) -> Type:
        # TODO: Perhaps return a type object type?
        return AnyType()

    def visit_list_expr(self, e: ListExpr) -> Type:
        return self.expr_checker.visit_list_expr(e)

    def visit_set_expr(self, e: SetExpr) -> Type:
        return self.expr_checker.visit_set_expr(e)

    def visit_tuple_expr(self, e: TupleExpr) -> Type:
        return self.expr_checker.visit_tuple_expr(e)

    def visit_dict_expr(self, e: DictExpr) -> Type:
        return self.expr_checker.visit_dict_expr(e)

    def visit_slice_expr(self, e: SliceExpr) -> Type:
        return self.expr_checker.visit_slice_expr(e)

    def visit_func_expr(self, e: FuncExpr) -> Type:
        return self.expr_checker.visit_func_expr(e)

    def visit_list_comprehension(self, e: ListComprehension) -> Type:
        return self.expr_checker.visit_list_comprehension(e)

    def visit_set_comprehension(self, e: SetComprehension) -> Type:
        return self.expr_checker.visit_set_comprehension(e)

    def visit_generator_expr(self, e: GeneratorExpr) -> Type:
        return self.expr_checker.visit_generator_expr(e)

    def visit_dictionary_comprehension(self, e: DictionaryComprehension) -> Type:
        return self.expr_checker.visit_dictionary_comprehension(e)

    def visit_temp_node(self, e: TempNode) -> Type:
        return e.type

    def visit_conditional_expr(self, e: ConditionalExpr) -> Type:
        return self.expr_checker.visit_conditional_expr(e)

    def visit_backquote_expr(self, e: BackquoteExpr) -> Type:
        return self.expr_checker.visit_backquote_expr(e)

    def visit_yield_expr(self, e: YieldExpr) -> Type:
        return_type = self.return_types[-1]
        expected_item_type = self.get_generator_yield_type(return_type, False)
        if e.expr is None:
            if (not isinstance(expected_item_type, (Void, NoneTyp, AnyType))
                    and self.typing_mode_full()):
                self.fail(messages.YIELD_VALUE_EXPECTED, e)
        else:
            actual_item_type = self.accept(e.expr, expected_item_type)
            self.check_subtype(actual_item_type, expected_item_type, e,
                            messages.INCOMPATIBLE_TYPES_IN_YIELD,
                            'actual type', 'expected type')
        return self.get_generator_receive_type(return_type, False)

    def visit_await_expr(self, e: AwaitExpr) -> Type:
        expected_type = self.type_context[-1]
        if expected_type is not None:
            expected_type = self.named_generic_type('typing.Awaitable', [expected_type])
        actual_type = self.accept(e.expr, expected_type)
        if isinstance(actual_type, AnyType):
            return AnyType()
        return self.check_awaitable_expr(actual_type, e, messages.INCOMPATIBLE_TYPES_IN_AWAIT)

    #
    # Helpers
    #

    def check_subtype(self, subtype: Type, supertype: Type, context: Context,
                      msg: str = messages.INCOMPATIBLE_TYPES,
                      subtype_label: str = None,
                      supertype_label: str = None) -> bool:
        """Generate an error if the subtype is not compatible with
        supertype."""
        if is_subtype(subtype, supertype):
            return True
        else:
            if self.is_unusable_type(subtype):
                self.msg.does_not_return_value(subtype, context)
            else:
                if self.should_suppress_optional_error([subtype]):
                    return False
                extra_info = []  # type: List[str]
                if subtype_label is not None or supertype_label is not None:
                    subtype_str, supertype_str = self.msg.format_distinctly(subtype, supertype)
                    if subtype_label is not None:
                        extra_info.append(subtype_label + ' ' + subtype_str)
                    if supertype_label is not None:
                        extra_info.append(supertype_label + ' ' + supertype_str)
                if extra_info:
                    msg += ' (' + ', '.join(extra_info) + ')'
                self.fail(msg, context)
            return False

    def contains_none(self, t: Type):
        return (
            isinstance(t, NoneTyp) or
            (isinstance(t, UnionType) and any(self.contains_none(ut) for ut in t.items)) or
            (isinstance(t, TupleType) and any(self.contains_none(tt) for tt in t.items)) or
            (isinstance(t, Instance) and t.args and any(self.contains_none(it) for it in t.args))
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
        return Instance(cast(TypeInfo, sym.node), [])

    def named_generic_type(self, name: str, args: List[Type]) -> Instance:
        """Return an instance with the given name and type arguments.

        Assume that the number of arguments is correct.  Assume that
        the name refers to a compatible generic type.
        """
        return Instance(self.lookup_typeinfo(name), args)

    def lookup_typeinfo(self, fullname: str) -> TypeInfo:
        # Assume that the name refers to a class.
        sym = self.lookup_qualified(fullname)
        return cast(TypeInfo, sym.node)

    def type_type(self) -> Instance:
        """Return instance type 'type'."""
        return self.named_type('builtins.type')

    def object_type(self) -> Instance:
        """Return instance type 'object'."""
        return self.named_type('builtins.object')

    def bool_type(self) -> Instance:
        """Return instance type 'bool'."""
        return self.named_type('builtins.bool')

    def str_type(self) -> Instance:
        """Return instance type 'str'."""
        return self.named_type('builtins.str')

    def check_type_equivalency(self, t1: Type, t2: Type, node: Context,
                               msg: str = messages.INCOMPATIBLE_TYPES) -> None:
        """Generate an error if the types are not equivalent. The
        dynamic type is equivalent with all types.
        """
        if not is_equivalent(t1, t2):
            self.fail(msg, node)

    def store_type(self, node: Node, typ: Type) -> None:
        """Store the type of a node in the type map."""
        self.type_map[node] = typ
        if typ is not None:
            self.module_type_map[node] = typ

    def typing_mode_none(self) -> bool:
        if self.is_dynamic_function() and not self.options.check_untyped_defs:
            return not self.weak_opts
        elif self.function_stack:
            return False
        else:
            return False

    def typing_mode_weak(self) -> bool:
        if self.is_dynamic_function() and not self.options.check_untyped_defs:
            return bool(self.weak_opts)
        elif self.function_stack:
            return False
        else:
            return 'global' in self.weak_opts

    def typing_mode_full(self) -> bool:
        if self.is_dynamic_function() and not self.options.check_untyped_defs:
            return False
        elif self.function_stack:
            return True
        else:
            return 'global' not in self.weak_opts

    def is_dynamic_function(self) -> bool:
        return len(self.dynamic_funcs) > 0 and self.dynamic_funcs[-1]

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
                n = cast(MypyFile, n.names.get(parts[i], None).node)
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

    def enter_partial_types(self) -> None:
        """Push a new scope for collecting partial types."""
        self.partial_types.append({})

    def leave_partial_types(self) -> None:
        """Pop partial type scope.

        Also report errors for variables which still have partial
        types, i.e. we couldn't infer a complete type.
        """
        partial_types = self.partial_types.pop()
        if not self.current_node_deferred:
            for var, context in partial_types.items():
                if (experiments.STRICT_OPTIONAL and
                        isinstance(var.type, PartialType) and var.type.type is None):
                    # None partial type: assume variable is intended to have type None
                    var.type = NoneTyp()
                else:
                    self.msg.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
                    var.type = AnyType()

    def find_partial_types(self, var: Var) -> Optional[Dict[Var, Context]]:
        for partial_types in reversed(self.partial_types):
            if var in partial_types:
                return partial_types
        return None

    def is_within_function(self) -> bool:
        """Are we currently type checking within a function?

        I.e. not at class body or at the top level.
        """
        return self.return_types != []

    def is_unusable_type(self, typ: Type):
        """Is this type an unusable type?

        The two unusable types are Void and NoneTyp(is_ret_type=True).
        """
        return isinstance(typ, Void) or (isinstance(typ, NoneTyp) and typ.is_ret_type)

    def check_usable_type(self, typ: Type, context: Context) -> None:
        """Generate an error if the type is not a usable type."""
        if self.is_unusable_type(typ):
            self.msg.does_not_return_value(typ, context)

    def temp_node(self, t: Type, context: Context = None) -> Node:
        """Create a temporary node with the given, fixed type."""
        temp = TempNode(t)
        if context:
            temp.set_line(context.get_line())
        return temp

    def fail(self, msg: str, context: Context) -> None:
        """Produce an error message."""
        self.msg.fail(msg, context)

    def iterable_item_type(self, instance: Instance) -> Type:
        iterable = map_instance_to_supertype(
            instance,
            self.lookup_typeinfo('typing.Iterable'))
        return iterable.args[0]

    def function_type(self, func: FuncBase) -> FunctionLike:
        return function_type(func, self.named_type('builtins.function'))

    def method_type(self, func: FuncBase) -> FunctionLike:
        return method_type_with_fallback(func, self.named_type('builtins.function'))


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

# NB: This should be `TypeMap = Optional[Dict[Node, Type]]`!
# But see https://github.com/python/mypy/issues/1637
TypeMap = Dict[Node, Type]


def conditional_type_map(expr: Node,
                         current_type: Optional[Type],
                         proposed_type: Optional[Type],
                         *,
                         weak: bool = False
                         ) -> Tuple[TypeMap, TypeMap]:
    """Takes in an expression, the current type of the expression, and a
    proposed type of that expression.

    Returns a 2-tuple: The first element is a map from the expression to
    the proposed type, if the expression can be the proposed type.  The
    second element is a map from the expression to the type it would hold
    if it was not the proposed type, if any."""
    if proposed_type:
        if current_type:
            if is_proper_subtype(current_type, proposed_type):
                return {expr: proposed_type}, None
            elif not is_overlapping_types(current_type, proposed_type):
                return None, {expr: current_type}
            else:
                remaining_type = restrict_subtype_away(current_type, proposed_type)
                return {expr: proposed_type}, {expr: remaining_type}
        else:
            return {expr: proposed_type}, {}
    else:
        # An isinstance check, but we don't understand the type
        if weak:
            return {expr: AnyType()}, {expr: current_type}
        else:
            return {}, {}


def is_literal_none(n: Node) -> bool:
    return isinstance(n, NameExpr) and n.fullname == 'builtins.None'


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
    m2_keys = set(n2.literal_hash for n2 in m2)
    for n1 in m1:
        if n1.literal_hash not in m2_keys:
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
            if n1.literal_hash == n2.literal_hash:
                result[n1] = UnionType.make_simplified_union([m1[n1], m2[n2]])
    return result


def find_isinstance_check(node: Node,
                          type_map: Dict[Node, Type],
                          weak: bool=False
                          ) -> Tuple[TypeMap, TypeMap]:
    """Find any isinstance checks (within a chain of ands).  Includes
    implicit and explicit checks for None.

    Return value is a map of variables to their types if the condition
    is true and a map of variables to their types if the condition is false.

    If either of the values in the tuple is None, then that particular
    branch can never occur.

    Guaranteed to not return None, None. (But may return {}, {})
    """
    if isinstance(node, CallExpr):
        if refers_to_fullname(node.callee, 'builtins.isinstance'):
            expr = node.args[0]
            if expr.literal == LITERAL_TYPE:
                vartype = type_map[expr]
                type = get_isinstance_type(node.args[1], type_map)
                return conditional_type_map(expr, vartype, type, weak=weak)
    elif (isinstance(node, ComparisonExpr) and any(is_literal_none(n) for n in node.operands) and
          experiments.STRICT_OPTIONAL):
        # Check for `x is None` and `x is not None`.
        is_not = node.operators == ['is not']
        if is_not or node.operators == ['is']:
            if_vars = {}  # type: Dict[Node, Type]
            else_vars = {}  # type: Dict[Node, Type]
            for expr in node.operands:
                if expr.literal == LITERAL_TYPE and not is_literal_none(expr) and expr in type_map:
                    # This should only be true at most once: there should be
                    # two elements in node.operands, and at least one of them
                    # should represent a None.
                    vartype = type_map[expr]
                    if_vars, else_vars = conditional_type_map(expr, vartype, NoneTyp(), weak=weak)
                    break

            if is_not:
                if_vars, else_vars = else_vars, if_vars
            return if_vars, else_vars
    elif isinstance(node, RefExpr):
        # Restrict the type of the variable to True-ish/False-ish in the if and else branches
        # respectively
        vartype = type_map[node]
        if_type = true_only(vartype)
        else_type = false_only(vartype)
        ref = node  # type: Node
        if_map = {ref: if_type} if not isinstance(if_type, UninhabitedType) else None
        else_map = {ref: else_type} if not isinstance(else_type, UninhabitedType) else None
        return if_map, else_map
    elif isinstance(node, OpExpr) and node.op == 'and':
        left_if_vars, left_else_vars = find_isinstance_check(
            node.left,
            type_map,
            weak,
        )

        right_if_vars, right_else_vars = find_isinstance_check(
            node.right,
            type_map,
            weak,
        )

        # (e1 and e2) is true if both e1 and e2 are true,
        # and false if at least one of e1 and e2 is false.
        return (and_conditional_maps(left_if_vars, right_if_vars),
                or_conditional_maps(left_else_vars, right_else_vars))
    elif isinstance(node, OpExpr) and node.op == 'or':
        left_if_vars, left_else_vars = find_isinstance_check(
            node.left,
            type_map,
            weak,
        )

        right_if_vars, right_else_vars = find_isinstance_check(
            node.right,
            type_map,
            weak,
        )

        # (e1 or e2) is true if at least one of e1 or e2 is true,
        # and false if both e1 and e2 are false.
        return (or_conditional_maps(left_if_vars, right_if_vars),
                and_conditional_maps(left_else_vars, right_else_vars))
    elif isinstance(node, UnaryExpr) and node.op == 'not':
        left, right = find_isinstance_check(node.expr, type_map, weak)
        return right, left

    # Not a supported isinstance check
    return {}, {}


def get_isinstance_type(node: Node, type_map: Dict[Node, Type]) -> Type:
    type = type_map[node]

    if isinstance(type, TupleType):
        all_types = type.items
    else:
        all_types = [type]

    types = []  # type: List[Type]

    for type in all_types:
        if isinstance(type, FunctionLike):
            if type.is_type_obj():
                # Type variables may be present -- erase them, which is the best
                # we can do (outside disallowing them here).
                type = erase_typevars(type.items()[0].ret_type)

            types.append(type)

    if len(types) == 0:
        return None
    elif len(types) == 1:
        return types[0]
    else:
        return UnionType(types)


def expand_node(defn: Node, map: Dict[TypeVarId, Type]) -> Node:
    visitor = TypeTransformVisitor(map)
    return defn.accept(visitor)


def expand_func(defn: FuncItem, map: Dict[TypeVarId, Type]) -> FuncItem:
    return cast(FuncItem, expand_node(defn, map))


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
            return not is_more_precise_signature(signature, other)
    return True


def is_more_general_arg_prefix(t: FunctionLike, s: FunctionLike) -> bool:
    """Does t have wider arguments than s?"""
    # TODO should an overload with additional items be allowed to be more
    #      general than one with fewer items (or just one item)?
    # TODO check argument kinds
    if isinstance(t, CallableType):
        if isinstance(s, CallableType):
            return all(is_proper_subtype(args, argt)
                       for argt, args in zip(t.arg_types, s.arg_types))
    elif isinstance(t, FunctionLike):
        if isinstance(s, FunctionLike):
            if len(t.items()) == len(s.items()):
                return all(is_same_arg_prefix(items, itemt)
                           for items, itemt in zip(t.items(), s.items()))
    return False


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


def infer_operator_assignment_method(type: Type, operator: str) -> Tuple[bool, str]:
    """Determine if operator assignment on given value type is in-place, and the method name.

    For example, if operator is '+', return (True, '__iadd__') or (False, '__add__')
    depending on which method is supported by the type.
    """
    method = nodes.op_methods[operator]
    if isinstance(type, Instance):
        if operator in nodes.ops_with_inplace_method:
            inplace_method = '__i' + method[2:]
            if type.type.has_readable_member(inplace_method):
                return True, inplace_method
    return False, method


def is_valid_inferred_type(typ: Type) -> bool:
    """Is an inferred type valid?

    Examples of invalid types include the None type or a type with a None component.
    """
    if is_same_type(typ, NoneTyp()):
        # With strict Optional checking, we *may* eventually infer NoneTyp, but
        # we only do that if we can't infer a specific Optional type.  This
        # resolution happens in leave_partial_types when we pop a partial types
        # scope.
        return False
    if is_same_type(typ, UninhabitedType()):
        return False
    elif isinstance(typ, Instance):
        for arg in typ.args:
            if not is_valid_inferred_type(arg):
                return False
    elif isinstance(typ, TupleType):
        for item in typ.items:
            if not is_valid_inferred_type(item):
                return False
    return True
