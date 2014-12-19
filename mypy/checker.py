"""Mypy type checker."""

import itertools

from typing import Undefined, Any, Dict, Set, List, cast, overload, Tuple, Function, typevar, Union

from mypy.errors import Errors
from mypy.nodes import (
    SymbolTable, Node, MypyFile, VarDef, LDEF, Var,
    OverloadedFuncDef, FuncDef, FuncItem, FuncBase, TypeInfo,
    ClassDef, GDEF, Block, AssignmentStmt, NameExpr, MemberExpr, IndexExpr,
    TupleExpr, ListExpr, ParenExpr, ExpressionStmt, ReturnStmt, IfStmt,
    WhileStmt, OperatorAssignmentStmt, YieldStmt, WithStmt, AssertStmt,
    RaiseStmt, TryStmt, ForStmt, DelStmt, CallExpr, IntExpr, StrExpr,
    BytesExpr, UnicodeExpr, FloatExpr, OpExpr, UnaryExpr, CastExpr, SuperExpr,
    TypeApplication, DictExpr, SliceExpr, FuncExpr, TempNode, SymbolTableNode,
    Context, ListComprehension, ConditionalExpr, GeneratorExpr,
    Decorator, SetExpr, PassStmt, TypeVarExpr, UndefinedExpr, PrintStmt,
    LITERAL_TYPE, BreakStmt, ContinueStmt, ComparisonExpr, StarExpr,
    YieldFromExpr, YieldFromStmt, NamedTupleExpr, SetComprehension,
    DictionaryComprehension, ComplexExpr, EllipsisNode
)
from mypy.nodes import function_type, method_type
from mypy import nodes
from mypy.types import (
    Type, AnyType, Callable, Void, FunctionLike, Overloaded, TupleType,
    Instance, NoneTyp, UnboundType, ErrorType, TypeTranslator, strip_type, UnionType
)
from mypy.sametypes import is_same_type
from mypy.messages import MessageBuilder
import mypy.checkexpr
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
from mypy.meet import meet_simple, meet_simple_away, nearest_builtin_ancestor, is_overlapping_types


# Kinds of isinstance checks.
ISINSTANCE_OVERLAPPING = 0
ISINSTANCE_ALWAYS_TRUE = 1
ISINSTANCE_ALWAYS_FALSE = 2

T = typevar('T')


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
        self.frames = List[Frame]()
        # The first frame is special: it's the declared types of variables.
        self.frames.append(Frame())
        self.dependencies = Dict[Key, Set[Key]]()  # Set of other keys to invalidate if a key
                                                   # is changed
        self._added_dependencies = Set[Key]()      # Set of keys with dependencies added already

        self.frames_on_escape = Dict[int, List[Frame]]()

        self.try_frames = Set[int]()
        self.loop_frames = List[int]()

    def _add_dependencies(self, key: Key, value: Key = None) -> None:
        if value is None:
            value = key
            if value in self._added_dependencies:
                return
            self._added_dependencies.add(value)
        if isinstance(key, tuple):
            key = cast(Any, key)   # XXX sad
            if key != value:
                self.dependencies[key] = Set[Key]()
                self.dependencies.setdefault(key, Set[Key]()).add(value)
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

    def push(self, expr: Node, type: Type) -> None:
        if not expr.literal:
            return
        key = expr.literal_hash
        self.frames[0][key] = self.get_declaration(expr)
        self._push(key, type)

    def get(self, expr: Node) -> Type:
        return self._get(expr.literal_hash)

    def update_from_options(self, frames: List[Frame]) -> bool:
        """Update the frame to reflect that each key will be updated
        as in one of the frames.  Return whether any item changes."""

        changed = False
        keys = set(key for f in frames for key in f)

        for key in keys:
            current_value = self._get(key)
            resulting_values = [f.get(key, current_value) for f in frames]
            if any(x is None for x in resulting_values):
                continue

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
        blocks.

        If fallthrough, then allow types to escape from the inner
        frame to the resulting frame.

        Return whether the newly innermost frame was modified since it
        was last on top, and what it would be if the block had run to
        completion.
        """
        result = self.frames.pop()

        options = self.frames_on_escape.get(len(self.frames) - 1, [])
        if canskip:
            options.append(self.frames[-1])
        if fallthrough:
            options.append(result)

        changed = self.update_from_options(options)

        return (changed, result)

    def get_declaration(self, expr: Any) -> Type:
        if hasattr(expr, 'node') and isinstance(expr.node, Var):
            return expr.node.type
        else:
            return self.frames[0].get(expr.literal_hash)

    def assign_type(self, expr: Node, type: Type) -> None:
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

        if isinstance(self.most_recent_enclosing_type(expr, type), AnyType):
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
        for dep in self.dependencies.get(expr.literal_hash, Set[Key]()):
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


def meet_frames(*frames: Frame) -> Frame:
    answer = Frame()
    for f in frames:
        for key in f:
            if key in answer:
                answer[key] = meet_simple(answer[key], f[key])
            else:
                answer[key] = f[key]
    return answer


class TypeChecker(NodeVisitor[Type]):
    """Mypy type checker.

    Type check mypy source files that have been semantically analysed.
    """

    # Target Python major version
    pyversion = 3
    # Error message reporting
    errors = Undefined(Errors)
    # SymbolNode table for the whole program
    symtable = Undefined(SymbolTable)
    # Utility for generating messages
    msg = Undefined(MessageBuilder)
    # Types of type checked nodes
    type_map = Undefined(Dict[Node, Type])

    # Helper for managing conditional types
    binder = Undefined(ConditionalTypeBinder)
    # Helper for type checking expressions
    expr_checker = Undefined('mypy.checkexpr.ExpressionChecker')

    # Stack of function return types
    return_types = Undefined(List[Type])
    # Type context for type inference
    type_context = Undefined(List[Type])
    # Flags; true for dynamically typed functions
    dynamic_funcs = Undefined(List[bool])
    # Stack of functions being type checked
    function_stack = Undefined(List[FuncItem])
    # Set to True on return/break/raise, False on blocks that can block any of them
    breaking_out = False

    globals = Undefined(SymbolTable)
    locals = Undefined(SymbolTable)
    modules = Undefined(Dict[str, MypyFile])

    def __init__(self, errors: Errors, modules: Dict[str, MypyFile],
                 pyversion: int = 3) -> None:
        """Construct a type checker.

        Use errors to report type check errors. Assume symtable has been
        populated by the semantic analyzer.
        """
        self.expr_checker
        self.errors = errors
        self.modules = modules
        self.pyversion = pyversion
        self.msg = MessageBuilder(errors)
        self.type_map = {}
        self.binder = ConditionalTypeBinder()
        self.binder.push_frame()
        self.expr_checker = mypy.checkexpr.ExpressionChecker(self, self.msg)
        self.return_types = []
        self.type_context = []
        self.dynamic_funcs = []
        self.function_stack = []

    def visit_file(self, file_node: MypyFile, path: str) -> None:
        """Type check a mypy file with the given path."""
        self.errors.set_file(path)
        self.globals = file_node.names
        self.locals = None

        for d in file_node.defs:
            self.accept(d)

    def accept(self, node: Node, type_context: Type = None) -> Type:
        """Type check a node in the given type context."""
        self.type_context.append(type_context)
        typ = node.accept(self)
        self.type_context.pop()
        self.store_type(node, typ)
        if self.is_dynamic_function():
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
                break

        return answer

    #
    # Definitions
    #

    def visit_var_def(self, defn: VarDef) -> Type:
        """Type check a variable definition.

        It can be of any kind: local, member or global.
        """
        # Type check initializer.
        if defn.init:
            # There is an initializer.
            if defn.items[0].type:
                # Explicit types.
                if len(defn.items) == 1:
                    self.check_simple_assignment(defn.items[0].type,
                                                 defn.init, defn.init)
                else:
                    # Multiple assignment.
                    lv = List[Node]()
                    for v in defn.items:
                        lv.append(self.temp_node(v.type, v))
                    self.check_multi_assignment(lv, defn.init, defn.init)
            else:
                init_type = self.accept(defn.init)
                if defn.kind == LDEF and not defn.is_top_level:
                    # Infer local variable type if there is an initializer
                    # except if the definition is at the top level (outside a
                    # function).
                    self.infer_local_variable_type(defn.items, init_type, defn)
        else:
            # No initializer
            if (defn.kind == LDEF and not defn.items[0].type and
                    not defn.is_top_level and not self.is_dynamic_function()):
                self.fail(messages.NEED_ANNOTATION_FOR_VAR, defn)

    def infer_local_variable_type(self, x, y, z):
        # TODO
        raise RuntimeError('Not implemented')

    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> Type:
        num_abstract = 0
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
                    self.msg.overloaded_signatures_overlap(i + 1, j + 2,
                                                           item.func)

    def visit_func_def(self, defn: FuncDef) -> Type:
        """Type check a function definition."""
        self.check_func_item(defn, name=defn.name())
        if defn.info:
            self.check_method_override(defn)
            self.check_inplace_operator_method(defn)
        if defn.original_def:
            if not is_same_type(self.function_type(defn),
                                self.function_type(defn.original_def)):
                self.msg.incompatible_conditional_function_def(defn)

    def check_func_item(self, defn: FuncItem,
                        type_override: Callable = None,
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
        self.dynamic_funcs.append(defn.type is None and not type_override)

        if fdef:
            self.errors.push_function(fdef.name())

        typ = self.function_type(defn)
        if type_override:
            typ = type_override
        if isinstance(typ, Callable):
            self.check_func_def(defn, typ, name)
        else:
            raise RuntimeError('Not supported')

        if fdef:
            self.errors.pop_function()

        self.dynamic_funcs.pop()
        self.function_stack.pop()

    def check_func_def(self, defn: FuncItem, typ: Callable, name: str) -> None:
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

            self.enter()

            if fdef:
                # Check if __init__ has an invalid, non-None return type.
                if (fdef.info and fdef.name() == '__init__' and
                        not isinstance(typ.ret_type, Void) and
                        not self.dynamic_funcs[-1]):
                    self.fail(messages.INIT_MUST_NOT_HAVE_RETURN_TYPE,
                              item.type)

            if name in nodes.reverse_op_method_set:
                self.check_reverse_op_method(item, typ, name)
            elif name == '__getattr__':
                self.check_getattr_method(typ, defn)

            # Push return type.
            self.return_types.append(typ.ret_type)

            # Store argument types.
            nargs = len(item.args)
            for i in range(len(typ.arg_types)):
                arg_type = typ.arg_types[i]
                if typ.arg_kinds[i] == nodes.ARG_STAR:
                    arg_type = self.named_generic_type('builtins.list',
                                                       [arg_type])
                elif typ.arg_kinds[i] == nodes.ARG_STAR2:
                    arg_type = self.named_generic_type('builtins.dict',
                                                       [self.str_type(),
                                                        arg_type])
                item.args[i].type = arg_type

            # Type check initialization expressions.
            for j in range(len(item.init)):
                if item.init[j]:
                    self.accept(item.init[j])

            # Clear out the default assignments from the binder
            self.binder.pop_frame()
            self.binder.push_frame()
            # Type check body in a new scope.
            self.accept_in_frame(item.body)

            self.return_types.pop()

            self.leave()
            self.binder = old_binder

    def check_reverse_op_method(self, defn: FuncItem, typ: Callable,
                                method: str) -> None:
        """Check a reverse operator method such as __radd__."""

        # If the argument of a reverse operator method such as __radd__
        # does not define the corresponding non-reverse method such as __add__
        # the return type of __radd__ may not reliably represent the value of
        # the corresponding operation even in a fully statically typed program.
        #
        # This example illustrates the issue:
        #
        #   class A: pass
        #   class B:
        #       def __radd__(self, x: A) -> int: # Note that A does not define
        #           return 1                     # __add__!
        #   class C(A):
        #       def __add__(self, x: Any) -> str: return 'x'
        #   a = Undefined(A)
        #   a = C()
        #   a + B()  # Result would be 'x', even though static type seems to
        #            # be int!

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
            fail = False
            if isinstance(arg_type, Instance):
                if not arg_type.type.has_readable_member(other_method):
                    fail = True
            elif isinstance(arg_type, AnyType):
                self.msg.reverse_operator_method_with_any_arg_must_return_any(
                    method, defn)
                return
            elif isinstance(arg_type, UnionType):
                if not arg_type.has_readable_member(other_method):
                    fail = True
            else:
                fail = True
            if fail:
                self.msg.invalid_reverse_operator_signature(
                    method, other_method, defn)
                return

            typ2 = self.expr_checker.analyse_external_member_access(
                other_method, arg_type, defn)
            self.check_overlapping_op_methods(
                typ, method, defn.info,
                typ2, other_method, cast(Instance, arg_type),
                defn)

    def check_overlapping_op_methods(self,
                                     reverse_type: Callable,
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
        #   b = Undefined(B)
        #   b = C()
        #   A() + b # Result is 1, even though static type seems to be str!
        #
        # The reason for the problem is that B and X are overlapping
        # types, and the return types are different. Also, if the type
        # of x in __radd__ would not be A, the methods could be
        # non-overlapping.

        if isinstance(forward_type, Callable):
            # TODO check argument kinds
            if len(forward_type.arg_types) < 1:
                # Not a valid operator method -- can't succeed anyway.
                return

            # Construct normalized function signatures corresponding to the
            # operator methods. The first argument is the left operand and the
            # second operand is the right argument -- we switch the order of
            # the arguments of the reverse method.
            forward_tweaked = Callable([forward_base,
                                        forward_type.arg_types[0]],
                                       [nodes.ARG_POS] * 2,
                                       [None] * 2,
                                       forward_type.ret_type,
                                       forward_type.fallback,
                                       name=forward_type.name)
            reverse_args = reverse_type.arg_types
            reverse_tweaked = Callable([reverse_args[1], reverse_args[0]],
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
        else:
            # TODO what about this?
            assert False, 'Forward operator method type is not Callable'

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
            typ2 = self.expr_checker.analyse_external_member_access(
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

    def check_getattr_method(self, typ: Callable, context: Context) -> None:
        method_type = Callable([AnyType(), self.named_type('builtins.str')],
                               [nodes.ARG_POS, nodes.ARG_POS],
                               [None],
                               AnyType(),
                               self.named_type('builtins.function'))
        if not is_subtype(typ, method_type):
            self.msg.invalid_signature(typ, context)

    def expand_typevars(self, defn: FuncItem,
                        typ: Callable) -> List[Tuple[FuncItem, Callable]]:
        # TODO use generator
        subst = List[List[Tuple[int, Type]]]()
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
            result = List[Tuple[FuncItem, Callable]]()
            for substitutions in itertools.product(*subst):
                mapping = dict(substitutions)
                expanded = cast(Callable, expand_type(typ, mapping))
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
            if name != '__init__':
                # Check method override (__init__ is special).
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
                original_type = self.function_type(cast(FuncDef,
                                                        base_attr.node))
            if isinstance(original_type, FunctionLike):
                original = map_type_from_supertype(
                    method_type(original_type),
                    defn.info, base)
                # Check that the types are compatible.
                # TODO overloaded signatures
                self.check_override(cast(FunctionLike, typ),
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
                len(cast(Callable, override).arg_types) !=
                len(cast(Callable, original).arg_types) or
                cast(Callable, override).min_args !=
                cast(Callable, original).min_args):
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

            coverride = cast(Callable, override)
            coriginal = cast(Callable, original)

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
        old_binder = self.binder
        self.binder = ConditionalTypeBinder()
        self.binder.push_frame()
        self.accept(defn.defs)
        self.binder = old_binder
        self.check_multiple_inheritance(typ)
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
                    if name in base2.names and not base2 in base.mro:
                        self.check_compatibility(name, base, base2, typ)
        # Verify that base class layouts are compatible.
        builtin_bases = [nearest_builtin_ancestor(base.type)
                         for base in typ.bases]
        for base1 in builtin_bases:
            for base2 in builtin_bases:
                if not (base1 in base2.mro or base2 in base1.mro):
                    self.fail(messages.INSTANCE_LAYOUT_CONFLICT, typ)
        # Verify that no disjointclass constraints are violated.
        for base in typ.mro:
            for disjoint in base.disjointclass_decls:
                if disjoint in typ.mro:
                    self.msg.disjointness_violation(base, disjoint, typ)

    def check_compatibility(self, name: str, base1: TypeInfo,
                            base2: TypeInfo, ctx: Context) -> None:
        if name == '__init__':
            # __init__ can be incompatible -- it's a special case.
            return
        first = base1[name]
        second = base2[name]
        first_type = first.type
        second_type = second.type
        if (isinstance(first_type, FunctionLike) and
                isinstance(second_type, FunctionLike)):
            # Method override
            first_sig = method_type(cast(FunctionLike, first_type))
            second_sig = method_type(cast(FunctionLike, second_type))
            # TODO Can we relax the equivalency requirement?
            ok = is_equivalent(first_sig, second_sig)
        else:
            ok = is_equivalent(first_type, second_type)
        if not ok:
            self.msg.base_class_definitions_incompatible(name, base1, base2,
                                                         ctx)

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
        self.check_assignment(s.lvalues[-1], s.rvalue, s.type == None)

        if len(s.lvalues) > 1:
            # Chained assignment (e.g. x = y = ...).
            # Make sure that rvalue type will not be reinferred.
            rvalue = self.temp_node(self.type_map[s.rvalue], s)
            for lv in s.lvalues[:-1]:
                self.check_assignment(lv, rvalue, s.type == None)

    def check_assignment(self, lvalue: Node, rvalue: Node, infer_lvalue_type: bool = True) -> None:
        """Type check a single assignment: lvalue = rvalue
        """
        if isinstance(lvalue, ParenExpr):
            self.check_assignment(lvalue.expr, rvalue, infer_lvalue_type)
        elif isinstance(lvalue, TupleExpr) or isinstance(lvalue, ListExpr):
            ltuple = cast(Union[TupleExpr, ListExpr], lvalue)
            rvalue = self.remove_parens(rvalue)

            self.check_assignment_to_multiple_lvalues(ltuple.items, rvalue, lvalue, infer_lvalue_type)
        else:
            lvalue_type, index_lvalue, inferred = self.check_lvalue(lvalue)

            if lvalue_type:
                rvalue_type = self.check_simple_assignment(lvalue_type, rvalue, lvalue)

                if rvalue_type and infer_lvalue_type:
                    self.binder.assign_type(lvalue, rvalue_type)
            elif index_lvalue:
                self.check_indexed_assignment(index_lvalue, rvalue, rvalue)

            if inferred:
                self.infer_variable_type(inferred, lvalue, self.accept(rvalue),
                                         rvalue)

    def check_assignment_to_multiple_lvalues(self, lvalues: List[Node], rvalue: Node, context: Context,
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
                star_lv = cast(StarExpr, lvalues[star_index]) if star_index != len(lvalues) else None
                right_lvs = lvalues[star_index+1:]

                left_rvs, star_rvs, right_rvs = self.split_around_star(
                                                rvalues, star_index, len(lvalues))

                lr_pairs = list(zip(left_lvs, left_rvs))
                if star_lv:
                    rv_list = ListExpr(star_rvs)
                    rv_list.set_line(rvalue.get_line())
                    lr_pairs.append( (star_lv.expr, rv_list) )
                lr_pairs.extend(zip(right_lvs, right_rvs))

                for lv, rv in lr_pairs:
                    self.check_assignment(lv, rv, infer_lvalue_type)
        else:
            self.check_multi_assignment(lvalues, rvalue, context, infer_lvalue_type)

    def check_rvalue_count_in_assignment(self, lvalues: List[Node], rvalue_count: int,
                                                                    context: Context) -> bool:
        if any(isinstance(lvalue, StarExpr) for lvalue in lvalues):
            if len(lvalues)-1 > rvalue_count:
                self.msg.wrong_number_values_to_unpack(rvalue_count,
                                len(lvalues)-1, context)
                return False
        elif rvalue_count != len(lvalues):
            self.msg.wrong_number_values_to_unpack(rvalue_count,
                            len(lvalues), context)
            return False
        return True

    def remove_parens(self, node: Node) -> Node:
        if isinstance(node, ParenExpr):
            return self.remove_parens(node.expr)
        else:
            return node

    def check_multi_assignment(self, lvalues: List[Node],
                                  rvalue: Node,
                                  context: Context,
                                  infer_lvalue_type: bool = True,
                                  msg: str = None) -> None:
        """Check the assignment of one rvalue to a number of lvalues
        for example from a ListExpr or TupleExpr.
        """

        if not msg:
            msg = messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT

        # First handle case where rvalue is of form Undefined, ...
        rvalue_type = get_undefined_tuple(rvalue, self.named_type('builtins.tuple'))
        undefined_rvalue = True
        if not rvalue_type:
            # Infer the type of an ordinary rvalue expression.
            rvalue_type = self.accept(rvalue)  # TODO maybe elsewhere; redundant
            undefined_rvalue = False

        if isinstance(rvalue_type, AnyType):
            for lv in lvalues:
                if isinstance(lv, StarExpr):
                    lv = lv.expr
                self.check_assignment(lv, self.temp_node(AnyType(), context), infer_lvalue_type)
        elif isinstance(rvalue_type, TupleType):
            self.check_multi_assignment_from_tuple(lvalues, rvalue, cast(TupleType, rvalue_type),
                                                  context, undefined_rvalue, infer_lvalue_type)
        else:
            self.check_multi_assignment_from_iterable(lvalues, rvalue_type,
                                                     context, infer_lvalue_type)

    def check_multi_assignment_from_tuple(self, lvalues: List[Node], rvalue: Node,
                                          rvalue_type: TupleType, context: Context,
                                          undefined_rvalue: bool, infer_lvalue_type: bool=True) -> None:
        if self.check_rvalue_count_in_assignment(lvalues, len(rvalue_type.items), context):
            star_index = next((i for i, lv in enumerate(lvalues) if isinstance(lv, StarExpr)), len(lvalues))

            left_lvs = lvalues[:star_index]
            star_lv = cast(StarExpr, lvalues[star_index]) if star_index != len(lvalues) else None
            right_lvs = lvalues[star_index+1:]

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
        star_index = next((i for i, lv in enumerate(lvalues) if isinstance(lv, StarExpr)), len(lvalues))
        left_lvs = lvalues[:star_index]
        star_lv = cast(StarExpr, lvalues[star_index]) if star_index != len(lvalues) else None
        right_lvs = lvalues[star_index+1:]
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
                                             context: Context, infer_lvalue_type: bool=True) -> None:
        if self.type_is_iterable(rvalue_type):
            item_type = self.iterable_item_type(cast(Instance,rvalue_type))
            for lv in lvalues:
                if isinstance(lv, StarExpr):
                    self.check_assignment(lv.expr, self.temp_node(rvalue_type, context), infer_lvalue_type)
                else:
                    self.check_assignment(lv, self.temp_node(item_type, context), infer_lvalue_type)
        else:
            self.msg.type_not_iterable(rvalue_type, context)

    def check_lvalue(self, lvalue: Node) -> Tuple[Type, IndexExpr, Var]:
        lvalue_type = None # type: Type
        index_lvalue = None # type: IndexExpr
        inferred = None # type: Var

        if self.is_definition(lvalue):
            if isinstance(lvalue, NameExpr):
                inferred = cast(Var, lvalue.node)
            else:
                m = cast(MemberExpr, lvalue)
                self.accept(m.expr)
                inferred = m.def_var
        elif isinstance(lvalue, IndexExpr):
            index_lvalue = lvalue
        elif isinstance(lvalue, MemberExpr):
            lvalue_type = self.expr_checker.analyse_ordinary_member_access(lvalue,
                                                                 True)
            self.store_type(lvalue, lvalue_type)
        elif isinstance(lvalue, NameExpr):
            lvalue_type = self.expr_checker.analyse_ref_expr(lvalue)
            self.store_type(lvalue, lvalue_type)
        elif isinstance(lvalue, TupleExpr) or isinstance(lvalue, ListExpr):
            lv = cast(Union[TupleExpr, ListExpr], lvalue)
            types = [self.check_lvalue(sub_expr)[0] for sub_expr in lv.items]
            lvalue_type = TupleType(types, self.named_type('builtins.tuple'))
        elif isinstance(lvalue, ParenExpr):
            return self.check_lvalue(lvalue.expr)
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
        if isinstance(init_type, Void):
            self.check_not_void(init_type, context)
        elif not self.is_valid_inferred_type(init_type):
            # We cannot use the type of the initialization expression for type
            # inference (it's not specific enough).
            self.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
        else:
            # Infer type of the target.

            # Make the type more general (strip away function names etc.).
            init_type = strip_type(init_type)

            self.set_inferred_type(name, lvalue, init_type)

    def set_inferred_type(self, var: Var, lvalue: Node, type: Type) -> None:
        """Store inferred variable type.

        Store the type to both the variable node and the expression node that
        refers to the variable (lvalue). If var is None, do nothing.
        """
        if var:
            var.type = type
            self.store_type(lvalue, type)

    def is_valid_inferred_type(self, typ: Type) -> bool:
        """Is an inferred type invalid?

        Examples include the None type or a type with a None component.
        """
        if is_same_type(typ, NoneTyp()):
            return False
        elif isinstance(typ, Instance):
            for arg in typ.args:
                if not self.is_valid_inferred_type(arg):
                    return False
        elif isinstance(typ, TupleType):
            for item in typ.items:
                if not self.is_valid_inferred_type(item):
                    return False
        return True

    def narrow_type_from_binder(self, expr: Node, known_type: Type) -> Type:
        if expr.literal >= LITERAL_TYPE:
            restriction = self.binder.get(expr)
            if restriction:
                ans = meet_simple(known_type, restriction)
                return ans
        return known_type

    def check_simple_assignment(self, lvalue_type: Type, rvalue: Node,
                                context: Node,
                                msg: str = messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT) -> Type:
        """Checks the assignment of rvalue to a lvalue of type lvalue_type."""
        if refers_to_fullname(rvalue, 'typing.Undefined'):
            # The rvalue is just 'Undefined'; this is always valid.
            # Infer the type of 'Undefined' from the lvalue type.
            self.store_type(rvalue, lvalue_type)
            return None
        else:
            rvalue_type = self.accept(rvalue, lvalue_type)
            self.check_subtype(rvalue_type, lvalue_type, context, msg,
                               'expression has type', 'variable has type')
            return rvalue_type

    def check_indexed_assignment(self, lvalue: IndexExpr,
                                 rvalue: Node, context: Context) -> None:
        """Type check indexed assignment base[index] = rvalue.

        The lvalue argument is the base[index] expression.
        """
        basetype = self.accept(lvalue.base)
        method_type = self.expr_checker.analyse_external_member_access(
            '__setitem__', basetype, context)
        lvalue.method_type = method_type
        self.expr_checker.check_call(method_type, [lvalue.index, rvalue],
                                     [nodes.ARG_POS, nodes.ARG_POS],
                                     context)

    def visit_expression_stmt(self, s: ExpressionStmt) -> Type:
        self.accept(s.expr)

    def visit_return_stmt(self, s: ReturnStmt) -> Type:
        """Type check a return statement."""
        self.breaking_out = True
        if self.is_within_function():
            if s.expr:
                # Return with a value.
                typ = self.accept(s.expr, self.return_types[-1])
                # Returning a value of type Any is always fine.
                if not isinstance(typ, AnyType):
                    if isinstance(self.return_types[-1], Void):
                        # FuncExpr (lambda) may have a Void return.
                        # Function returning a value of type None may have a Void return.
                        if (not isinstance(self.function_stack[-1], FuncExpr) and
                                not isinstance(typ, NoneTyp)):
                            self.fail(messages.NO_RETURN_VALUE_EXPECTED, s)
                    else:
                        if self.function_stack[-1].is_coroutine: # Something similar will be needed to mix return and yield
                            # If the function is a coroutine, wrap the return type in a Future
                            typ = self.wrap_generic_type(cast(Instance,typ), cast(Instance,self.return_types[-1]), 'asyncio.futures.Future', s)
                        self.check_subtype(
                            typ, self.return_types[-1], s,
                            messages.INCOMPATIBLE_RETURN_VALUE_TYPE
                            + ": expected {}, got {}".format(self.return_types[-1], typ)
                        )
            else:
                # Return without a value. It's valid in a generator and coroutine function.
                if not self.function_stack[-1].is_generator and not self.function_stack[-1].is_coroutine:
                    if (not isinstance(self.return_types[-1], Void) and
                            not self.is_dynamic_function()):
                            self.fail(messages.RETURN_VALUE_EXPECTED, s)

    def wrap_generic_type(self, typ: Instance, rtyp: Instance, check_type: str, context: Context) -> Type:
        n_diff = self.count_nested_types(rtyp, check_type) - self.count_nested_types(typ, check_type)
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
            typ = map_instance_to_supertype(self.named_generic_type(check_type, typ.args), self.lookup_typeinfo(check_type))
            if typ.args:
                typ = cast(Instance,typ.args[0])
            else:
                return c
        return c

    def visit_yield_stmt(self, s: YieldStmt) -> Type:
        return_type = self.return_types[-1]
        if isinstance(return_type, Instance):
            if return_type.type.fullname() != 'typing.Iterator':
                self.fail(messages.INVALID_RETURN_TYPE_FOR_YIELD, s)
                return None
            expected_item_type = return_type.args[0]
        elif isinstance(return_type, AnyType):
            expected_item_type = AnyType()
        else:
            self.fail(messages.INVALID_RETURN_TYPE_FOR_YIELD, s)
            return None
        if s.expr is None:
            actual_item_type = Void()  # type: Type
        else:
            actual_item_type = self.accept(s.expr, expected_item_type)
        self.check_subtype(actual_item_type, expected_item_type, s,
                           messages.INCOMPATIBLE_TYPES_IN_YIELD,
                           'actual type', 'expected type')

    def visit_yield_from_stmt(self, s: YieldFromStmt) -> Type:
        return_type = self.return_types[-1]
        type_func = self.accept(s.expr, return_type)
        if isinstance(type_func, Instance):
            if type_func.type.fullname() == 'asyncio.futures.Future':
                # if is a Future, in stmt don't need to do nothing
                # because the type Future[Some] jus matters to the main loop
                # that python executes, in statement we shouldn't get the Future,
                # is just for async purposes.
                self.function_stack[-1].is_coroutine = True  # Set the function as coroutine
            elif is_subtype(type_func, self.named_type('typing.Iterable')):
                # If it's and Iterable-Like, let's check the types.
                # Maybe just check if have __iter__? (like in analyse_iterable)
                self.check_iterable_yield_from(s)
            else:
                self.msg.yield_from_invalid_operand_type(type_func, s)
        elif isinstance(type_func, AnyType):
            self.check_iterable_yield_from(s)
        else:
            self.msg.yield_from_invalid_operand_type(type_func, s)

    def check_iterable_yield_from(self, s: YieldFromStmt) -> Type:
        """
            Check that return type is super type of Iterable (Maybe just check if have __iter__?)
            and compare it with the type of the expression
        """
        expected_item_type = self.return_types[-1]
        if isinstance(expected_item_type, Instance):
            if not is_subtype(expected_item_type, self.named_type('typing.Iterable')):
                self.fail(messages.INVALID_RETURN_TYPE_FOR_YIELD_FROM, s)
                return None
            elif expected_item_type.args:
                expected_item_type = map_instance_to_supertype(expected_item_type, self.lookup_typeinfo('typing.Iterable'))
                expected_item_type = expected_item_type.args[0]  # Take the item inside the iterator
        elif isinstance(expected_item_type, AnyType):
            expected_item_type = AnyType()
        else:
            self.fail(messages.INVALID_RETURN_TYPE_FOR_YIELD_FROM, s)
            return None
        if s.expr is None:
            actual_item_type = Void() # type: Type
        else:
            actual_item_type = self.accept(s.expr, expected_item_type)
            if hasattr(actual_item_type, 'args') and cast(Instance,actual_item_type).args:
                actual_item_type = map_instance_to_supertype(cast(Instance,actual_item_type), self.lookup_typeinfo('typing.Iterable'))
                actual_item_type = actual_item_type.args[0]   # Take the item inside the iterator
        self.check_subtype(actual_item_type, expected_item_type, s,
                           messages.INCOMPATIBLE_TYPES_IN_YIELD_FROM,
                           'actual type', 'expected type')

    def visit_if_stmt(self, s: IfStmt) -> Type:
        """Type check an if statement."""
        broken = True
        ending_frames = List[Frame]()
        clauses_frame = self.binder.push_frame()
        for e, b in zip(s.expr, s.body):
            t = self.accept(e)
            self.check_not_void(t, e)
            var, type, elsetype, kind = find_isinstance_check(e, self.type_map)
            if kind == ISINSTANCE_ALWAYS_FALSE:
                # XXX should issue a warning?
                pass
            else:
                # Only type check body if the if condition can be true.
                self.binder.push_frame()
                if var:
                    self.binder.push(var, type)
                self.accept(b)
                _, frame = self.binder.pop_frame()
                self.binder.allow_jump(len(self.binder.frames) - 1)
                if not self.breaking_out:
                    broken = False
                    ending_frames.append(meet_frames(clauses_frame, frame))

                self.breaking_out = False

                if var:
                    self.binder.push(var, elsetype)
            if kind == ISINSTANCE_ALWAYS_TRUE:
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
            lv = cast(IndexExpr, s.lvalue)
            self.check_indexed_assignment(lv, s.rvalue, s.rvalue)
        else:
            if not is_subtype(rvalue_type, lvalue_type):
                self.msg.incompatible_operator_assignment(s.op, s)

    def visit_assert_stmt(self, s: AssertStmt) -> Type:
        self.accept(s.expr)

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
                if base in typeinfo.mro:
                    # Good!
                    return None
                # Else fall back to the check below (which will fail).
        self.check_subtype(typ,
                           self.named_type('builtins.BaseException'), s,
                           messages.INVALID_EXCEPTION)

    def visit_try_stmt(self, s: TryStmt) -> Type:
        """Type check a try statement."""
        completed_frames = List[Frame]()
        self.binder.push_frame()
        self.binder.try_frames.add(len(self.binder.frames) - 2)
        self.accept(s.body)
        self.binder.try_frames.remove(len(self.binder.frames) - 2)
        if s.else_body:
            self.accept(s.else_body)
        changed, frame_on_completion = self.binder.pop_frame()
        completed_frames.append(frame_on_completion)

        for i in range(len(s.handlers)):
            if s.types[i]:
                t = self.exception_type(s.types[i])
                if s.vars[i]:
                    self.check_assignment(s.vars[i],
                                           self.temp_node(t, s.vars[i]))
            self.binder.push_frame()
            self.accept(s.handlers[i])
            changed, frame_on_completion = self.binder.pop_frame()
            completed_frames.append(frame_on_completion)
        if s.else_body:
            self.binder.push_frame()
            self.accept(s.else_body)
            changed, frame_on_completion = self.binder.pop_frame()
            completed_frames.append(frame_on_completion)

        self.binder.update_from_options(completed_frames)

        if s.finally_body:
            self.accept(s.finally_body)

    def exception_type(self, n: Node) -> Type:
        if isinstance(n, ParenExpr):
            # Multiple exception types (...).
            unwrapped = self.expr_checker.strip_parens(n)
            if isinstance(unwrapped, TupleExpr):
                t = None  # type: Type
                for item in unwrapped.items:
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

    @overload
    def check_exception_type(self, type: FunctionLike,
                             context: Context) -> Type:
        item = type.items()[0]
        ret = item.ret_type
        if (is_subtype(ret, self.named_type('builtins.BaseException'))
                and item.is_type_obj()):
            return ret
        else:
            self.fail(messages.INVALID_EXCEPTION_TYPE, context)
            return AnyType()

    @overload
    def check_exception_type(self, type: AnyType, context: Context) -> Type:
        return AnyType()

    @overload
    def check_exception_type(self, type: Type, context: Context) -> Type:
        self.fail(messages.INVALID_EXCEPTION_TYPE, context)
        return AnyType()

    def visit_for_stmt(self, s: ForStmt) -> Type:
        """Type check a for statement."""
        item_type = self.analyse_iterable_item_type(s.expr)
        self.analyse_index_variables(s.index, item_type, s)
        self.binder.push_frame()
        self.binder.push_loop_frame()
        self.accept_in_frame(s.body, repeat_till_fixed=True)
        self.binder.pop_loop_frame()
        if s.else_body:
            self.accept(s.else_body)
        self.binder.pop_frame(False, True)

    def analyse_iterable_item_type(self, expr: Node) -> Type:
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
            method = echk.analyse_external_member_access('__iter__', iterable,
                                                         expr)
            iterator = echk.check_call(method, [], [], expr)[0]
            if self.pyversion >= 3:
                nextmethod = '__next__'
            else:
                nextmethod = 'next'
            method = echk.analyse_external_member_access(nextmethod, iterator,
                                                         expr)
            return echk.check_call(method, [], [], expr)[0]

    def analyse_index_variables(self, index: Node, item_type: Type,
                                context: Context) -> None:
        """Type check or infer for loop or list comprehension index vars."""
        self.check_assignment(index, self.temp_node(item_type, context))

    def visit_del_stmt(self, s: DelStmt) -> Type:
        if isinstance(s.expr, IndexExpr):
            e = cast(IndexExpr, s.expr)  # Cast
            m = MemberExpr(e.base, '__delitem__')
            m.line = s.line
            c = CallExpr(m, [e.index], [nodes.ARG_POS], [None])
            c.line = s.line
            return c.accept(self)
        else:
            s.expr.accept(self)
            return None

    def visit_decorator(self, e: Decorator) -> Type:
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

    def visit_with_stmt(self, s: WithStmt) -> Type:
        echk = self.expr_checker
        for expr, name in zip(s.expr, s.name):
            ctx = self.accept(expr)
            enter = echk.analyse_external_member_access('__enter__', ctx, expr)
            obj = echk.check_call(enter, [], [], expr)[0]
            if name:
                self.check_assignment(name, self.temp_node(obj, expr))
            exit = echk.analyse_external_member_access('__exit__', ctx, expr)
            arg = self.temp_node(AnyType(), expr)
            echk.check_call(exit, [arg] * 3, [nodes.ARG_POS] * 3, expr)
        self.accept(s.body)

    def visit_print_stmt(self, s: PrintStmt) -> Type:
        for arg in s.args:
            self.accept(arg)

    #
    # Expressions
    #

    def visit_name_expr(self, e: NameExpr) -> Type:
        return self.expr_checker.visit_name_expr(e)

    def visit_paren_expr(self, e: ParenExpr) -> Type:
        return self.expr_checker.visit_paren_expr(e)

    def visit_call_expr(self, e: CallExpr) -> Type:
        result = self.expr_checker.visit_call_expr(e)
        self.breaking_out = False
        return result

    def visit_yield_from_expr(self, e: YieldFromExpr) -> Type:
        # result = self.expr_checker.visit_yield_from_expr(e)
        result = self.accept(e.expr)
        result_instance = cast(Instance, result)
        if result_instance.type.fullname() == "asyncio.futures.Future":
            self.function_stack[-1].is_coroutine = True  # Set the function as coroutine
            result = result_instance.args[0]  # Set the return type as the type inside
        elif is_subtype(result, self.named_type('typing.Iterable')):
            # TODO
            # Check return type Iterator[Some]
            # Maybe set result like in the Future
            pass
        else:
            # self.msg.yield_from_invalid_operand_type(e.expr, e)
            self.msg.yield_from_invalid_operand_type(e.expr.accept(self), e)
        return result

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

    def visit_ellipsis(self, e: EllipsisNode) -> Type:
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

    def visit_undefined_expr(self, e: UndefinedExpr) -> Type:
        return self.expr_checker.visit_undefined_expr(e)

    def visit_temp_node(self, e: TempNode) -> Type:
        return e.type

    def visit_conditional_expr(self, e: ConditionalExpr) -> Type:
        return self.expr_checker.visit_conditional_expr(e)

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
                if subtype_label is not None:
                    extra_info.append(subtype_label + ' ' + self.msg.format(subtype, verbose=True))
                if supertype_label is not None:
                    extra_info.append(supertype_label + ' ' + self.msg.format(supertype,
                                                                              verbose=True))
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

    def is_dynamic_function(self) -> bool:
        return len(self.dynamic_funcs) > 0 and self.dynamic_funcs[-1]

    def lookup(self, name: str, kind: int) -> SymbolTableNode:
        """Look up a definition from the symbol table with the given name.
        TODO remove kind argument
        """
        if self.locals is not None and name in self.locals:
            return self.locals[name]
        elif name in self.globals:
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

    def enter(self) -> None:
        self.locals = SymbolTable()

    def leave(self) -> None:
        self.locals = None

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
        return method_type(func, self.named_type('builtins.function'))


def map_type_from_supertype(typ: Type, sub_info: TypeInfo,
                            super_info: TypeInfo) -> Type:
    """Map type variables in a type defined in a supertype context to be valid
    in the subtype context. Assume that the result is unique; if more than
    one type is possible, return one of the alternatives.

    For example, assume

    . class D(Generic[S]) ...
    . class C(D[E[T]], Generic[T]) ...

    Now S in the context of D would be mapped to E[T] in the context of C.
    """
    # Create the type of self in subtype, of form t[a1, ...].
    inst_type = self_type(sub_info)
    if isinstance(inst_type, TupleType):
        inst_type = inst_type.fallback
    # Map the type of self to supertype. This gets us a description of the
    # supertype type variables in terms of subtype variables, i.e. t[t1, ...]
    # so that any type variables in tN are to be interpreted in subtype
    # context.
    inst_type = map_instance_to_supertype(inst_type, super_info)
    # Finally expand the type variables in type with those in the previously
    # constructed type. Note that both type and inst_type may have type
    # variables, but in type they are interpreterd in supertype context while
    # in inst_type they are interpreted in subtype context. This works even if
    # the names of type variables in supertype and subtype overlap.
    return expand_type_by_instance(typ, inst_type)


def get_undefined_tuple(rvalue: Node, tuple_type: Instance) -> Type:
    """Get tuple type corresponding to a tuple of Undefined values.

    The type is Tuple[Any, ...]. If rvalue is not of the right form, return
    None.
    """
    if isinstance(rvalue, TupleExpr):
        for item in rvalue.items:
            if not refers_to_fullname(item, 'typing.Undefined'):
                break
        else:
            return TupleType([AnyType()] * len(rvalue.items), tuple_type)
    return None


def find_isinstance_check(node: Node,
                          type_map: Dict[Node, Type]) -> Tuple[Node, Type, Type, int]:
    """Check if node is an isinstance(variable, type) check.

    If successful, return tuple (variable, target-type, else-type,
    kind); otherwise, return (None, AnyType, AnyType, -1).

    When successful, the kind takes one of these values:

      ISINSTANCE_OVERLAPPING: The type of variable and the target type are
          partially overlapping => the test result can be True or False.
      ISINSTANCE_ALWAYS_TRUE: The target type at least as general as the
          variable type => the test is always True.
      ISINSTANCE_ALWAYS_FALSE: The target type and the variable type are not
          overlapping => the test is always False.
    """
    if isinstance(node, CallExpr):
        if refers_to_fullname(node.callee, 'builtins.isinstance'):
            expr = node.args[0]
            if expr.literal == LITERAL_TYPE:
                type = get_isinstance_type(node.args[1], type_map)
                if type:
                    vartype = type_map[expr]
                    kind = ISINSTANCE_OVERLAPPING
                    elsetype = vartype
                    if vartype:
                        if is_proper_subtype(vartype, type):
                            kind = ISINSTANCE_ALWAYS_TRUE
                            elsetype = None
                        elif not is_overlapping_types(vartype, type):
                            kind = ISINSTANCE_ALWAYS_FALSE
                        else:
                            elsetype = restrict_subtype_away(vartype, type)
                    return expr, type, elsetype, kind
    # Not a supported isinstance check
    return None, AnyType(), AnyType(), -1


def get_isinstance_type(node: Node, type_map: Dict[Node, Type]) -> Type:
    type = type_map[node]
    if isinstance(type, FunctionLike):
        if type.is_type_obj():
            # Type variables may be present -- erase them, which is the best
            # we can do (outside disallowing them here).
            return erase_typevars(type.items()[0].ret_type)
    return None


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
    if isinstance(signature, Callable):
        if isinstance(other, Callable):
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
    if isinstance(t, Callable):
        if isinstance(s, Callable):
            return all(is_proper_subtype(args, argt)
                       for argt, args in zip(t.arg_types, s.arg_types))
    elif isinstance(t, FunctionLike):
        if isinstance(s, FunctionLike):
            if len(t.items()) == len(s.items()):
                return all(is_same_arg_prefix(items, itemt)
                           for items, itemt in zip(t.items(), s.items()))
    return False


def is_same_arg_prefix(t: Callable, s: Callable) -> bool:
    # TODO check argument kinds
    return all(is_same_type(argt, args)
               for argt, args in zip(t.arg_types, s.arg_types))


def is_more_precise_signature(t: Callable, s: Callable) -> bool:
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
