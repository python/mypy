"""Mypy type checker."""

import itertools
import contextlib

from typing import (
    Any, Dict, Set, List, cast, Tuple, TypeVar, Union, Optional, NamedTuple
)

from mypy.errors import Errors, report_internal_error
from mypy.nodes import (
    SymbolTable, Node, MypyFile, Var,
    OverloadedFuncDef, FuncDef, FuncItem, FuncBase, TypeInfo,
    ClassDef, GDEF, Block, AssignmentStmt, NameExpr, MemberExpr, IndexExpr,
    TupleExpr, ListExpr, ExpressionStmt, ReturnStmt, IfStmt,
    WhileStmt, OperatorAssignmentStmt, WithStmt, AssertStmt,
    RaiseStmt, TryStmt, ForStmt, DelStmt, CallExpr, IntExpr, StrExpr,
    BytesExpr, UnicodeExpr, FloatExpr, OpExpr, UnaryExpr, CastExpr, SuperExpr,
    TypeApplication, DictExpr, SliceExpr, FuncExpr, TempNode, SymbolTableNode,
    Context, ListComprehension, ConditionalExpr, GeneratorExpr,
    Decorator, SetExpr, TypeVarExpr, PrintStmt,
    LITERAL_TYPE, BreakStmt, ContinueStmt, ComparisonExpr, StarExpr,
    YieldFromExpr, NamedTupleExpr, SetComprehension,
    DictionaryComprehension, ComplexExpr, EllipsisExpr, TypeAliasExpr,
    RefExpr, YieldExpr, BackquoteExpr, ImportFrom, ImportAll, ImportBase,
    CONTRAVARIANT, COVARIANT
)
from mypy.nodes import function_type, method_type, method_type_with_fallback
from mypy import nodes
from mypy.types import (
    Type, AnyType, CallableType, Void, FunctionLike, Overloaded, TupleType,
    Instance, NoneTyp, ErrorType, strip_type,
    UnionType, TypeVarType, PartialType, DeletedType
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
from mypy.join import join_simple, join_types
from mypy.treetransform import TransformVisitor
from mypy.meet import meet_simple, nearest_builtin_ancestor, is_overlapping_types


T = TypeVar('T')


def min_with_None_large(x: T, y: T) -> T:
    """Return min(x, y) but with  a < None for all variables a that are not None"""
    if x is None:
        return y
    return min(x, x if y is None else y)


class Frame(Dict[Any, Type]):
    pass


class Key(AnyType):
    pass


class ConditionalTypeBinder:
    """Keep track of conditional types of variables."""

    def __init__(self) -> None:
        self.frames = []  # type: List[Frame]
        # The first frame is special: it's the declared types of variables.
        self.frames.append(Frame())
        # Set of other keys to invalidate if a key is changed.
        self.dependencies = {}  # type: Dict[Key, Set[Key]]
        # Set of keys with dependencies added already.
        self._added_dependencies = set()  # type: Set[Key]

        self.frames_on_escape = {}  # type: Dict[int, List[Frame]]

        self.try_frames = set()  # type: Set[int]
        self.loop_frames = []  # type: List[int]

    def _add_dependencies(self, key: Key, value: Key = None) -> None:
        if value is None:
            value = key
            if value in self._added_dependencies:
                return
            self._added_dependencies.add(value)
        if isinstance(key, tuple):
            key = cast(Any, key)   # XXX sad
            if key != value:
                self.dependencies[key] = set()
                self.dependencies.setdefault(key, set()).add(value)
            for elt in cast(Any, key):
                self._add_dependencies(elt, value)

    def push_frame(self) -> Frame:
        d = Frame()
        self.frames.append(d)
        return d

    def _push(self, key: Key, type: Type, index: int=-1) -> None:
        self._add_dependencies(key)
        self.frames[index][key] = type

    def _get(self, key: Key, index: int=-1) -> Type:
        if index < 0:
            index += len(self.frames)
        for i in range(index, -1, -1):
            if key in self.frames[i]:
                return self.frames[i][key]
        return None

    def push(self, expr: Node, typ: Type) -> None:
        if not expr.literal:
            return
        key = expr.literal_hash
        self.frames[0][key] = self.get_declaration(expr)
        self._push(key, typ)

    def get(self, expr: Node) -> Type:
        return self._get(expr.literal_hash)

    def cleanse(self, expr: Node) -> None:
        """Remove all references to a Node from the binder."""
        key = expr.literal_hash
        for frame in self.frames:
            if key in frame:
                del frame[key]

    def update_from_options(self, frames: List[Frame]) -> bool:
        """Update the frame to reflect that each key will be updated
        as in one of the frames.  Return whether any item changes.

        If a key is declared as AnyType, only update it if all the
        options are the same.
        """

        changed = False
        keys = set(key for f in frames for key in f)

        for key in keys:
            current_value = self._get(key)
            resulting_values = [f.get(key, current_value) for f in frames]
            if any(x is None for x in resulting_values):
                continue

            if isinstance(self.frames[0].get(key), AnyType):
                type = resulting_values[0]
                if not all(is_same_type(type, t) for t in resulting_values[1:]):
                    type = AnyType()
            else:
                type = resulting_values[0]
                for other in resulting_values[1:]:
                    type = join_simple(self.frames[0][key], type, other)
            if not is_same_type(type, current_value):
                self._push(key, type)
                changed = True

        return changed

    def update_expand(self, frame: Frame, index: int = -1) -> bool:
        """Update frame to include another one, if that other one is larger than the current value.

        Return whether anything changed."""
        result = False

        for key in frame:
            old_type = self._get(key, index)
            if old_type is None:
                continue
            replacement = join_simple(self.frames[0][key], old_type, frame[key])

            if not is_same_type(replacement, old_type):
                self._push(key, replacement, index)
                result = True
        return result

    def pop_frame(self, canskip=True, fallthrough=False) -> Tuple[bool, Frame]:
        """Pop a frame.

        If canskip, then allow types to skip all the inner frame
        blocks.  That is, changes that happened in the inner frames
        are not necessarily reflected in the outer frame (for example,
        an if block that may be skipped).

        If fallthrough, then allow types to escape from the inner
        frame to the resulting frame.  That is, the state of types at
        the end of the last frame are allowed to fall through into the
        enclosing frame.

        Return whether the newly innermost frame was modified since it
        was last on top, and what it would be if the block had run to
        completion.
        """
        result = self.frames.pop()

        options = self.frames_on_escape.pop(len(self.frames) - 1, [])
        if canskip:
            options.append(self.frames[-1])
        if fallthrough:
            options.append(result)

        changed = self.update_from_options(options)

        return (changed, result)

    def get_declaration(self, expr: Any) -> Type:
        if hasattr(expr, 'node') and isinstance(expr.node, Var):
            type = expr.node.type
            if isinstance(type, PartialType):
                return None
            return type
        else:
            return self.frames[0].get(expr.literal_hash)

    def assign_type(self, expr: Node, type: Type,
                    restrict_any: bool = False) -> None:
        if not expr.literal:
            return
        self.invalidate_dependencies(expr)

        declared_type = self.get_declaration(expr)

        if declared_type is None:
            # Not sure why this happens.  It seems to mainly happen in
            # member initialization.
            return
        if not is_subtype(type, declared_type):
            # Pretty sure this is only happens when there's a type error.

            # Ideally this function wouldn't be called if the
            # expression has a type error, though -- do other kinds of
            # errors cause this function to get called at invalid
            # times?
            return

        # If x is Any and y is int, after x = y we do not infer that x is int.
        # This could be changed.
        # Eric: I'm changing it in weak typing mode, since Any is so common.

        if (isinstance(self.most_recent_enclosing_type(expr, type), AnyType)
                and not restrict_any):
            pass
        elif isinstance(type, AnyType):
            self.push(expr, declared_type)
        else:
            self.push(expr, type)

        for i in self.try_frames:
            # XXX This should probably not copy the entire frame, but
            # just copy this variable into a single stored frame.
            self.allow_jump(i)

    def invalidate_dependencies(self, expr: Node) -> None:
        """Invalidate knowledge of types that include expr, but not expr itself.

        For example, when expr is foo.bar, invalidate foo.bar.baz and
        foo.bar[0].

        It is overly conservative: it invalidates globally, including
        in code paths unreachable from here.
        """
        for dep in self.dependencies.get(expr.literal_hash, set()):
            for f in self.frames:
                if dep in f:
                    del f[dep]

    def most_recent_enclosing_type(self, expr: Node, type: Type) -> Type:
        if isinstance(type, AnyType):
            return self.get_declaration(expr)
        key = expr.literal_hash
        enclosers = ([self.get_declaration(expr)] +
                     [f[key] for f in self.frames
                      if key in f and is_subtype(type, f[key])])
        return enclosers[-1]

    def allow_jump(self, index: int) -> None:
        new_frame = Frame()
        for f in self.frames[index + 1:]:
            for k in f:
                new_frame[k] = f[k]

        self.frames_on_escape.setdefault(index, []).append(new_frame)

    def push_loop_frame(self):
        self.loop_frames.append(len(self.frames) - 1)

    def pop_loop_frame(self):
        self.loop_frames.pop()

    def __enter__(self) -> None:
        self.push_frame()

    def __exit__(self, *args: Any) -> None:
        self.pop_frame()


def meet_frames(*frames: Frame) -> Frame:
    answer = Frame()
    for f in frames:
        for key in f:
            if key in answer:
                answer[key] = meet_simple(answer[key], f[key])
            else:
                answer[key] = f[key]
    return answer


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

    # Target Python version
    pyversion = defaults.PYTHON3_VERSION
    # Are we type checking a stub?
    is_stub = False
    # Error message reporter
    errors = None  # type: Errors
    # Utility for generating messages
    msg = None  # type: MessageBuilder
    # Types of type checked nodes
    type_map = None  # type: Dict[Node, Type]

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
    # Set to True on return/break/raise, False on blocks that can block any of them
    breaking_out = False
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
    # This makes it an error to call an untyped function from a typed one
    disallow_untyped_calls = False
    # This makes it an error to define an untyped or partially-typed function
    disallow_untyped_defs = False
    # Should we check untyped function defs?
    check_untyped_defs = False

    def __init__(self, errors: Errors, modules: Dict[str, MypyFile],
                 pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
                 disallow_untyped_calls=False, disallow_untyped_defs=False,
                 check_untyped_defs=False) -> None:
        """Construct a type checker.

        Use errors to report type check errors.
        """
        self.errors = errors
        self.modules = modules
        self.pyversion = pyversion
        self.msg = MessageBuilder(errors, modules)
        self.type_map = {}
        self.binder = ConditionalTypeBinder()
        self.binder.push_frame()
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
        self.disallow_untyped_calls = disallow_untyped_calls
        self.disallow_untyped_defs = disallow_untyped_defs
        self.check_untyped_defs = check_untyped_defs

    def visit_file(self, file_node: MypyFile, path: str) -> None:
        """Type check a mypy file with the given path."""
        self.pass_num = 0
        self.is_stub = file_node.is_stub
        self.errors.set_file(path)
        self.errors.set_ignored_lines(file_node.ignored_lines)
        self.globals = file_node.names
        self.weak_opts = file_node.weak_opts
        self.enter_partial_types()

        for d in file_node.defs:
            self.accept(d)

        self.leave_partial_types()

        if self.deferred_nodes:
            self.check_second_pass()

        self.errors.set_ignored_lines(set())
        self.current_node_deferred = False

    def check_second_pass(self):
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
            report_internal_error(err, self.errors.file, node.line)
        self.type_context.pop()
        self.store_type(node, typ)
        if self.typing_mode_none():
            return AnyType()
        else:
            return typ

    def accept_in_frame(self, node: Node, type_context: Type = None,
                        repeat_till_fixed: bool = False) -> Type:
        """Type check a node in the given type context in a new frame of inferred types."""
        while True:
            self.binder.push_frame()
            answer = self.accept(node, type_context)
            changed, _ = self.binder.pop_frame(True, True)
            self.breaking_out = False
            if not repeat_till_fixed or not changed:
                return answer

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

    def is_generator_return_type(self, typ: Type) -> bool:
        return is_subtype(self.named_generic_type('typing.Generator',
                                                  [AnyType(), AnyType(), AnyType()]),
                          typ)

    def get_generator_yield_type(self, return_type: Type) -> Type:
        if isinstance(return_type, AnyType):
            return AnyType()
        elif not self.is_generator_return_type(return_type):
            # If the function doesn't have a proper Generator (or superclass) return type, anything
            # is permissible.
            return AnyType()
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType()
        elif return_type.args:
            return return_type.args[0]
        else:
            # If the function's declared supertype of Generator has no type
            # parameters (i.e. is `object`), then the yielded values can't
            # be accessed so any type is acceptable.
            return AnyType()

    def get_generator_receive_type(self, return_type: Type) -> Type:
        if isinstance(return_type, AnyType):
            return AnyType()
        elif not self.is_generator_return_type(return_type):
            # If the function doesn't have a proper Generator (or superclass) return type, anything
            # is permissible.
            return AnyType()
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType()
        elif return_type.type.fullname() == 'typing.Generator':
            # Generator is the only type which specifies the type of values it can receive.
            return return_type.args[1]
        else:
            # `return_type` is a supertype of Generator, so callers won't be able to send it
            # values.
            return Void()

    def get_generator_return_type(self, return_type: Type) -> Type:
        if isinstance(return_type, AnyType):
            return AnyType()
        elif not self.is_generator_return_type(return_type):
            # If the function doesn't have a proper Generator (or superclass) return type, anything
            # is permissible.
            return AnyType()
        elif not isinstance(return_type, Instance):
            # Same as above, but written as a separate branch so the typechecker can understand.
            return AnyType()
        elif return_type.type.fullname() == 'typing.Generator':
            # Generator is the only type which specifies the type of values it returns into
            # `yield from` expressions.
            return return_type.args[2]
        else:
            # `return_type` is supertype of Generator, so callers won't be able to see the return
            # type when used in a `yield from` expression.
            return AnyType()

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
            self.binder.push_frame()
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
                        not isinstance(typ.ret_type, Void) and
                        not self.dynamic_funcs[-1]):
                    self.fail(messages.INIT_MUST_HAVE_NONE_RETURN_TYPE,
                              item.type)

                if self.disallow_untyped_defs:
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
                if not self.is_generator_return_type(typ.ret_type):
                    self.fail(messages.INVALID_RETURN_TYPE_FOR_GENERATOR, typ)

                # Python 2 generators aren't allowed to return values.
                if (self.pyversion[0] == 2 and
                        isinstance(typ.ret_type, Instance) and
                        typ.ret_type.type.fullname() == 'typing.Generator'):
                    if not (isinstance(typ.ret_type.args[2], Void)
                            or isinstance(typ.ret_type.args[2], AnyType)):
                        self.fail(messages.INVALID_GENERATOR_RETURN_ITEM_TYPE, typ)

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

            # Clear out the default assignments from the binder
            self.binder.pop_frame()
            self.binder.push_frame()
            # Type check body in a new scope.
            self.accept_in_frame(item.body)

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
        subst = []  # type: List[List[Tuple[int, Type]]]
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
                    # An inplace overator method such as __iadd__ might not be
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
            if original_type is None and isinstance(base_attr.node,
                                                    FuncDef):
                original_type = self.function_type(base_attr.node)
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
                assert original_type is not None
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
        if (isinstance(override, Overloaded) or
                isinstance(original, Overloaded) or
                len(cast(CallableType, override).arg_types) !=
                len(cast(CallableType, original).arg_types) or
                cast(CallableType, override).min_args !=
                cast(CallableType, original).min_args):
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
                self.msg.signature_incompatible_with_supertype(
                    name, name_in_super, supertype, node)
            return
        else:
            # Give more detailed messages for the common case of both
            # signatures having the same number of arguments and no
            # overloads.

            coverride = cast(CallableType, override)
            coriginal = cast(CallableType, original)

            for i in range(len(coverride.arg_types)):
                if not is_subtype(coriginal.arg_types[i],
                                  coverride.arg_types[i]):
                    self.msg.argument_incompatible_with_supertype(
                        i + 1, name, name_in_super, supertype, node)

            if not is_subtype(coverride.ret_type, coriginal.ret_type):
                self.msg.return_type_incompatible_with_supertype(
                    name, name_in_super, supertype, node)

    def visit_class_def(self, defn: ClassDef) -> Type:
        """Type check a class definition."""
        typ = defn.info
        self.errors.push_type(defn.name)
        self.enter_partial_types()
        old_binder = self.binder
        self.binder = ConditionalTypeBinder()
        self.binder.push_frame()
        self.accept(defn.defs)
        self.binder = old_binder
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
            if self.breaking_out:
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
            ltuple = cast(Union[TupleExpr, ListExpr], lvalue)

            self.check_assignment_to_multiple_lvalues(ltuple.items, rvalue, lvalue,
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
                                var.type = rvalue_type
                            else:
                                var.type = None
                            del partial_types[var]
                    # Try to infer a partial type. No need to check the return value, as
                    # an error will be reported elsewhere.
                    self.infer_partial_type(lvalue_type.var, lvalue, rvalue_type)
                    return
                rvalue_type = self.check_simple_assignment(lvalue_type, rvalue, lvalue)

                if rvalue_type and infer_lvalue_type:
                    self.binder.assign_type(lvalue, rvalue_type,
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

            rvalues = cast(Union[TupleExpr, ListExpr], rvalue).items

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
            lv = cast(Union[TupleExpr, ListExpr], lvalue)
            types = [self.check_lvalue(sub_expr)[0] for sub_expr in lv.items]
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
            self.binder.assign_type(lvalue, init_type, True)
        elif isinstance(init_type, Void):
            self.check_not_void(init_type, context)
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
        if isinstance(init_type, NoneTyp):
            partial_type = PartialType(None, name)
        elif isinstance(init_type, Instance):
            fullname = init_type.type.fullname()
            if ((fullname == 'builtins.list' or fullname == 'builtins.set' or
                 fullname == 'builtins.dict')
                    and isinstance(init_type.args[0], NoneTyp)
                    and (fullname != 'builtins.dict' or isinstance(init_type.args[1], NoneTyp))
                    and isinstance(lvalue, NameExpr)):
                partial_type = PartialType(init_type.type, name)
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
        if context.get_line() in self.errors.ignored_lines:
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
            var = cast(Var, lvalue.base.node)
            if var is not None and isinstance(var.type, PartialType):
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
                    if is_valid_inferred_type(key_type) and is_valid_inferred_type(value_type):
                        if not self.current_node_deferred:
                            var.type = self.named_generic_type('builtins.dict',
                                                               [key_type, value_type])
                        del partial_types[var]

    def visit_expression_stmt(self, s: ExpressionStmt) -> Type:
        self.accept(s.expr)

    def visit_return_stmt(self, s: ReturnStmt) -> Type:
        """Type check a return statement."""
        self.breaking_out = True
        if self.is_within_function():
            if self.function_stack[-1].is_generator:
                return_type = self.get_generator_return_type(self.return_types[-1])
            else:
                return_type = self.return_types[-1]

            if s.expr:
                # Return with a value.
                typ = self.accept(s.expr, return_type)
                # Returning a value of type Any is always fine.
                if isinstance(typ, AnyType):
                    return None

                if isinstance(return_type, Void):
                    # Lambdas are allowed to have a Void return.
                    # Functions returning a value of type None are allowed to have a Void return.
                    if isinstance(self.function_stack[-1], FuncExpr) or isinstance(typ, NoneTyp):
                        return None
                    self.fail(messages.NO_RETURN_VALUE_EXPECTED, s)
                else:
                    self.check_subtype(
                        typ, return_type, s,
                        messages.INCOMPATIBLE_RETURN_VALUE_TYPE
                        + ": expected {}, got {}".format(return_type, typ)
                    )
            else:
                # Empty returns are valid in Generators with Any typed returns.
                if (self.function_stack[-1].is_generator and isinstance(return_type, AnyType)):
                    return None

                if isinstance(return_type, Void):
                    return None

                if isinstance(return_type, AnyType):
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
        broken = True
        ending_frames = []  # type: List[Frame]
        clauses_frame = self.binder.push_frame()
        for e, b in zip(s.expr, s.body):
            t = self.accept(e)
            self.check_not_void(t, e)
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
                self.binder.push_frame()
                if if_map:
                    for var, type in if_map.items():
                        self.binder.push(var, type)

                self.accept(b)
                _, frame = self.binder.pop_frame()
                if not self.breaking_out:
                    broken = False
                    ending_frames.append(meet_frames(clauses_frame, frame))

                self.breaking_out = False

                if else_map:
                    for var, type in else_map.items():
                        self.binder.push(var, type)
            if else_map is None:
                # The condition is always true => remaining elif/else blocks
                # can never be reached.

                # Might also want to issue a warning
                # print("Warning: isinstance always true")
                if broken:
                    self.binder.pop_frame()
                    self.breaking_out = True
                    return None
                break
        else:
            if s.else_body:
                self.accept(s.else_body)

                if self.breaking_out and broken:
                    self.binder.pop_frame()
                    return None

                if not self.breaking_out:
                    ending_frames.append(clauses_frame)

                self.breaking_out = False
            else:
                ending_frames.append(clauses_frame)

        self.binder.pop_frame()
        self.binder.update_from_options(ending_frames)

    def visit_while_stmt(self, s: WhileStmt) -> Type:
        """Type check a while statement."""
        self.binder.push_frame()
        self.binder.push_loop_frame()
        self.accept_in_frame(IfStmt([s.expr], [s.body], None),
                             repeat_till_fixed=True)
        self.binder.pop_loop_frame()
        if s.else_body:
            self.accept(s.else_body)
        self.binder.pop_frame(False, True)

    def visit_operator_assignment_stmt(self,
                                       s: OperatorAssignmentStmt) -> Type:
        """Type check an operator assignment statement, e.g. x += 1."""
        lvalue_type = self.accept(s.lvalue)
        method = infer_operator_assignment_method(lvalue_type, s.op)
        rvalue_type, method_type = self.expr_checker.check_op(
            method, lvalue_type, s.rvalue, s)

        if isinstance(s.lvalue, IndexExpr):
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
        self.breaking_out = True
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
        if isinstance(typ, TupleType) and self.pyversion[0] == 2:
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
        completed_frames = []  # type: List[Frame]
        self.binder.push_frame()
        self.binder.try_frames.add(len(self.binder.frames) - 2)
        self.accept(s.body)
        self.binder.try_frames.remove(len(self.binder.frames) - 2)
        self.breaking_out = False
        changed, frame_on_completion = self.binder.pop_frame()
        completed_frames.append(frame_on_completion)

        for i in range(len(s.handlers)):
            self.binder.push_frame()
            if s.types[i]:
                t = self.exception_type(s.types[i])
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
                if self.pyversion[0] >= 3:
                    source = s.vars[i].name
                else:
                    source = ('(exception variable "{}", which we do not accept '
                              'outside except: blocks even in python 2)'.format(s.vars[i].name))
                var = cast(Var, s.vars[i].node)
                var.type = DeletedType(source=source)
                self.binder.cleanse(s.vars[i])

            self.breaking_out = False
            changed, frame_on_completion = self.binder.pop_frame()
            completed_frames.append(frame_on_completion)

        # Do the else block similar to the way we do except blocks.
        if s.else_body:
            self.binder.push_frame()
            self.accept(s.else_body)
            self.breaking_out = False
            changed, frame_on_completion = self.binder.pop_frame()
            completed_frames.append(frame_on_completion)

        self.binder.update_from_options(completed_frames)

        if s.finally_body:
            self.accept(s.finally_body)

    def exception_type(self, n: Node) -> Type:
        if isinstance(n, TupleExpr):
            t = None  # type: Type
            for item in n.items:
                tt = self.exception_type(item)
                if t:
                    t = join_types(t, tt)
                else:
                    t = tt
            return t
        else:
            # A single exception type; should evaluate to a type object type.
            type = self.accept(n)
            return self.check_exception_type(type, n)
        self.fail('Unsupported exception', n)
        return AnyType()

    def check_exception_type(self, type: Type, context: Context) -> Type:
        if isinstance(type, FunctionLike):
            item = type.items()[0]
            ret = item.ret_type
            if (is_subtype(ret, self.named_type('builtins.BaseException'))
                    and item.is_type_obj()):
                return ret
            else:
                self.fail(messages.INVALID_EXCEPTION_TYPE, context)
                return AnyType()
        elif isinstance(type, AnyType):
            return AnyType()
        else:
            self.fail(messages.INVALID_EXCEPTION_TYPE, context)
            return AnyType()

    def visit_for_stmt(self, s: ForStmt) -> Type:
        """Type check a for statement."""
        item_type = self.analyze_iterable_item_type(s.expr)
        self.analyze_index_variables(s.index, item_type, s)
        self.binder.push_frame()
        self.binder.push_loop_frame()
        self.accept_in_frame(s.body, repeat_till_fixed=True)
        self.binder.pop_loop_frame()
        if s.else_body:
            self.accept(s.else_body)
        self.binder.pop_frame(False, True)

    def analyze_iterable_item_type(self, expr: Node) -> Type:
        """Analyse iterable expression and return iterator item type."""
        iterable = self.accept(expr)

        self.check_not_void(iterable, expr)
        if isinstance(iterable, TupleType):
            joined = NoneTyp()  # type: Type
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
            if self.pyversion[0] >= 3:
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
                    t = cast(Union[TupleExpr, ListExpr], t)
                    return [b for a in t.items for b in flatten(a)]
                else:
                    return [t]

            s.expr.accept(self)
            for elt in flatten(s.expr):
                if isinstance(elt, NameExpr):
                    self.binder.assign_type(elt, DeletedType(source=elt.name),
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
            dec = self.accept(e.decorators[n])
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
        echk = self.expr_checker
        for expr, target in zip(s.expr, s.target):
            ctx = self.accept(expr)
            enter = echk.analyze_external_member_access('__enter__', ctx, expr)
            obj = echk.check_call(enter, [], [], expr)[0]
            if target:
                self.check_assignment(target, self.temp_node(obj, expr))
            exit = echk.analyze_external_member_access('__exit__', ctx, expr)
            arg = self.temp_node(AnyType(), expr)
            echk.check_call(exit, [arg] * 3, [nodes.ARG_POS] * 3, expr)
        self.accept(s.body)

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
        return_type = self.return_types[-1]
        subexpr_type = self.accept(e.expr, return_type)
        iter_type = None  # type: Type

        # Check that the expr is an instance of Iterable and get the type of the iterator produced
        # by __iter__.
        if isinstance(subexpr_type, AnyType):
            iter_type = AnyType()
        elif (isinstance(subexpr_type, Instance) and
                is_subtype(subexpr_type, self.named_type('typing.Iterable'))):
            iter_method_type = self.expr_checker.analyze_external_member_access(
                '__iter__',
                subexpr_type,
                AnyType())

            generic_generator_type = self.named_generic_type('typing.Generator',
                                                             [AnyType(), AnyType(), AnyType()])
            iter_type, _ = self.expr_checker.check_call(iter_method_type, [], [],
                                                        context=generic_generator_type)
        else:
            self.msg.yield_from_invalid_operand_type(subexpr_type, e)
            iter_type = AnyType()

        # Check that the iterator's item type matches the type yielded by the Generator function
        # containing this `yield from` expression.
        expected_item_type = self.get_generator_yield_type(return_type)
        actual_item_type = self.get_generator_yield_type(iter_type)

        self.check_subtype(actual_item_type, expected_item_type, e,
                           messages.INCOMPATIBLE_TYPES_IN_YIELD_FROM,
                           'actual type', 'expected type')

        # Determine the type of the entire yield from expression.
        if (isinstance(iter_type, Instance) and
                iter_type.type.fullname() == 'typing.Generator'):
            return self.get_generator_return_type(iter_type)
        else:
            # Non-Generators don't return anything from `yield from` expressions.
            return Void()

    def visit_member_expr(self, e: MemberExpr) -> Type:
        return self.expr_checker.visit_member_expr(e)

    def visit_break_stmt(self, s: BreakStmt) -> Type:
        self.breaking_out = True
        self.binder.allow_jump(self.binder.loop_frames[-1] - 1)
        return None

    def visit_continue_stmt(self, s: ContinueStmt) -> Type:
        self.breaking_out = True
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

    def visit_super_expr(self, e: SuperExpr) -> Type:
        return self.expr_checker.visit_super_expr(e)

    def visit_type_application(self, e: TypeApplication) -> Type:
        return self.expr_checker.visit_type_application(e)

    def visit_type_alias_expr(self, e: TypeAliasExpr) -> Type:
        return self.expr_checker.visit_type_alias_expr(e)

    def visit_type_var_expr(self, e: TypeVarExpr) -> Type:
        # TODO: Perhaps return a special type used for type variables only?
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
        expected_item_type = self.get_generator_yield_type(return_type)
        if e.expr is None:
            if (not (isinstance(expected_item_type, Void) or
                     isinstance(expected_item_type, AnyType))
                    and self.typing_mode_full()):
                self.fail(messages.YIELD_VALUE_EXPECTED, e)
        else:
            actual_item_type = self.accept(e.expr, expected_item_type)
            self.check_subtype(actual_item_type, expected_item_type, e,
                            messages.INCOMPATIBLE_TYPES_IN_YIELD,
                            'actual type', 'expected type')
        return self.get_generator_receive_type(return_type)

    #
    # Helpers
    #

    def check_subtype(self, subtype: Type, supertype: Type, context: Context,
                      msg: str = messages.INCOMPATIBLE_TYPES,
                      subtype_label: str = None,
                      supertype_label: str = None) -> None:
        """Generate an error if the subtype is not compatible with
        supertype."""
        if not is_subtype(subtype, supertype):
            if isinstance(subtype, Void):
                self.msg.does_not_return_value(subtype, context)
            else:
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

    def typing_mode_none(self) -> bool:
        if self.is_dynamic_function() and not self.check_untyped_defs:
            return not self.weak_opts
        elif self.function_stack:
            return False
        else:
            return False

    def typing_mode_weak(self) -> bool:
        if self.is_dynamic_function() and not self.check_untyped_defs:
            return bool(self.weak_opts)
        elif self.function_stack:
            return False
        else:
            return 'global' in self.weak_opts

    def typing_mode_full(self) -> bool:
        if self.is_dynamic_function() and not self.check_untyped_defs:
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
            return n.names[parts[-1]]

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

    def check_not_void(self, typ: Type, context: Context) -> None:
        """Generate an error if the type is Void."""
        if isinstance(typ, Void):
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


def find_isinstance_check(node: Node,
                          type_map: Dict[Node, Type],
                          weak: bool=False) \
        -> Tuple[Optional[Dict[Node, Type]], Optional[Dict[Node, Type]]]:
    """Find any isinstance checks (within a chain of ands).

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
                if type:
                    elsetype = vartype
                    if vartype:
                        if is_proper_subtype(vartype, type):
                            return {expr: type}, None
                        elif not is_overlapping_types(vartype, type):
                            return None, {expr: elsetype}
                        else:
                            elsetype = restrict_subtype_away(vartype, type)
                    return {expr: type}, {expr: elsetype}
                else:
                    # An isinstance check, but we don't understand the type
                    if weak:
                        return {expr: AnyType()}, {expr: vartype}
    elif isinstance(node, OpExpr) and node.op == 'and':
        left_if_vars, right_else_vars = find_isinstance_check(
            node.left,
            type_map,
            weak,
        )

        right_if_vars, right_else_vars = find_isinstance_check(
            node.right,
            type_map,
            weak,
        )
        if left_if_vars:
            if right_if_vars is not None:
                left_if_vars.update(right_if_vars)
            else:
                left_if_vars = None
        else:
            left_if_vars = right_if_vars

        # Make no claim about the types in else
        return left_if_vars, {}
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


def expand_node(defn: Node, map: Dict[int, Type]) -> Node:
    visitor = TypeTransformVisitor(map)
    return defn.accept(visitor)


def expand_func(defn: FuncItem, map: Dict[int, Type]) -> FuncItem:
    return cast(FuncItem, expand_node(defn, map))


class TypeTransformVisitor(TransformVisitor):
    def __init__(self, map: Dict[int, Type]) -> None:
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


def infer_operator_assignment_method(type: Type, operator: str) -> str:
    """Return the method used for operator assignment for given value type.

    For example, if operator is '+', return '__iadd__' or '__add__' depending
    on which method is supported by the type.
    """
    method = nodes.op_methods[operator]
    if isinstance(type, Instance):
        if operator in nodes.ops_with_inplace_method:
            inplace = '__i' + method[2:]
            if type.type.has_readable_member(inplace):
                method = inplace
    return method


def is_valid_inferred_type(typ: Type) -> bool:
    """Is an inferred type valid?

    Examples of invalid types include the None type or a type with a None component.
    """
    if is_same_type(typ, NoneTyp()):
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
