"""Semantic analysis of types"""

from collections import OrderedDict
from typing import Callable, List, Optional, Set, Tuple, Iterator, TypeVar, Iterable
from itertools import chain

from contextlib import contextmanager

from mypy.types import (
    Type, UnboundType, TypeVarType, TupleType, TypedDictType, UnionType, Instance,
    AnyType, CallableType, NoneTyp, DeletedType, TypeList, TypeVarDef, TypeVisitor,
    SyntheticTypeVisitor,
    StarType, PartialType, EllipsisType, UninhabitedType, TypeType, get_typ_args, set_typ_args,
    CallableArgument, get_type_vars, TypeQuery, union_items
)

from mypy.nodes import (
    TVAR, TYPE_ALIAS, UNBOUND_IMPORTED,
    TypeInfo, Context, SymbolTableNode, Var, Expression,
    IndexExpr, RefExpr, nongen_builtins, check_arg_names, check_arg_kinds,
    ARG_POS, ARG_NAMED, ARG_OPT, ARG_NAMED_OPT, ARG_STAR, ARG_STAR2, TypeVarExpr
)
from mypy.tvar_scope import TypeVarScope
from mypy.sametypes import is_same_type
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.subtypes import is_subtype
from mypy import nodes
from mypy import experiments


T = TypeVar('T')


type_constructors = {
    'typing.Callable',
    'typing.Optional',
    'typing.Tuple',
    'typing.Type',
    'typing.Union',
}

ARG_KINDS_BY_CONSTRUCTOR = {
    'mypy_extensions.Arg': ARG_POS,
    'mypy_extensions.DefaultArg': ARG_OPT,
    'mypy_extensions.NamedArg': ARG_NAMED,
    'mypy_extensions.DefaultNamedArg': ARG_NAMED_OPT,
    'mypy_extensions.VarArg': ARG_STAR,
    'mypy_extensions.KwArg': ARG_STAR2,
}


def analyze_type_alias(node: Expression,
                       lookup_func: Callable[[str, Context], SymbolTableNode],
                       lookup_fqn_func: Callable[[str], SymbolTableNode],
                       tvar_scope: TypeVarScope,
                       fail_func: Callable[[str, Context], None],
                       allow_unnormalized: bool = False) -> Optional[Type]:
    """Return type if node is valid as a type alias rvalue.

    Return None otherwise. 'node' must have been semantically analyzed.
    """
    # Quickly return None if the expression doesn't look like a type. Note
    # that we don't support straight string literals as type aliases
    # (only string literals within index expressions).
    if isinstance(node, RefExpr):
        # Note that this misses the case where someone tried to use a
        # class-referenced type variable as a type alias.  It's easier to catch
        # that one in checkmember.py
        if node.kind == TVAR:
            fail_func('Type variable "{}" is invalid as target for type alias'.format(
                node.fullname), node)
            return None
        if not (isinstance(node.node, TypeInfo) or
                node.fullname == 'typing.Any' or
                node.kind == TYPE_ALIAS):
            return None
    elif isinstance(node, IndexExpr):
        base = node.base
        if isinstance(base, RefExpr):
            if not (isinstance(base.node, TypeInfo) or
                    base.fullname in type_constructors or
                    base.kind == TYPE_ALIAS):
                return None
            # Enums can't be generic, and without this check we may incorrectly interpret indexing
            # an Enum class as creating a type alias.
            if isinstance(base.node, TypeInfo) and base.node.is_enum:
                return None
        else:
            return None
    else:
        return None

    # It's a type alias (though it may be an invalid one).
    try:
        type = expr_to_unanalyzed_type(node)
    except TypeTranslationError:
        fail_func('Invalid type alias', node)
        return None
    analyzer = TypeAnalyser(lookup_func, lookup_fqn_func, tvar_scope, fail_func, aliasing=True,
                            allow_unnormalized=allow_unnormalized)
    return type.accept(analyzer)


def no_subscript_builtin_alias(name: str, propose_alt: bool = True) -> str:
    msg = '"{}" is not subscriptable'.format(name.split('.')[-1])
    replacement = nongen_builtins[name]
    if replacement and propose_alt:
        msg += ', use "{}" instead'.format(replacement)
    return msg


class TypeAnalyser(SyntheticTypeVisitor[Type]):
    """Semantic analyzer for types (semantic analysis pass 2).

    Converts unbound types into bound types.
    """

    def __init__(self,
                 lookup_func: Callable[[str, Context], SymbolTableNode],
                 lookup_fqn_func: Callable[[str], SymbolTableNode],
                 tvar_scope: TypeVarScope,
                 fail_func: Callable[[str, Context], None], *,
                 aliasing: bool = False,
                 allow_tuple_literal: bool = False,
                 allow_unnormalized: bool = False) -> None:
        self.lookup = lookup_func
        self.lookup_fqn_func = lookup_fqn_func
        self.fail = fail_func
        self.tvar_scope = tvar_scope
        self.aliasing = aliasing
        self.allow_tuple_literal = allow_tuple_literal
        # Positive if we are analyzing arguments of another (outer) type
        self.nesting_level = 0
        self.allow_unnormalized = allow_unnormalized

    def visit_unbound_type(self, t: UnboundType) -> Type:
        if t.optional:
            t.optional = False
            # We don't need to worry about double-wrapping Optionals or
            # wrapping Anys: Union simplification will take care of that.
            return make_optional_type(self.visit_unbound_type(t))
        sym = self.lookup(t.name, t)
        if sym is not None:
            if sym.node is None:
                # UNBOUND_IMPORTED can happen if an unknown name was imported.
                if sym.kind != UNBOUND_IMPORTED:
                    self.fail('Internal error (node is None, kind={})'.format(sym.kind), t)
                return AnyType()
            fullname = sym.node.fullname()
            if (fullname in nongen_builtins and t.args and
                    not sym.normalized and not self.allow_unnormalized):
                self.fail(no_subscript_builtin_alias(fullname), t)
            tvar_def = self.tvar_scope.get_binding(sym)
            if sym.kind == TVAR and tvar_def is not None:
                if len(t.args) > 0:
                    self.fail('Type variable "{}" used with arguments'.format(
                        t.name), t)
                return TypeVarType(tvar_def, t.line)
            elif fullname == 'builtins.None':
                return NoneTyp()
            elif fullname == 'typing.Any' or fullname == 'builtins.Any':
                return AnyType()
            elif fullname == 'typing.Tuple':
                if len(t.args) == 0 and not t.empty_tuple_index:
                    # Bare 'Tuple' is same as 'tuple'
                    return self.builtin_type('builtins.tuple')
                if len(t.args) == 2 and isinstance(t.args[1], EllipsisType):
                    # Tuple[T, ...] (uniform, variable-length tuple)
                    instance = self.builtin_type('builtins.tuple', [self.anal_type(t.args[0])])
                    instance.line = t.line
                    return instance
                return self.tuple_type(self.anal_array(t.args))
            elif fullname == 'typing.Union':
                items = self.anal_array(t.args)
                if not experiments.STRICT_OPTIONAL:
                    items = [item for item in items if not isinstance(item, NoneTyp)]
                return UnionType.make_union(items)
            elif fullname == 'typing.Optional':
                if len(t.args) != 1:
                    self.fail('Optional[...] must have exactly one type argument', t)
                    return AnyType()
                item = self.anal_type(t.args[0])
                return make_optional_type(item)
            elif fullname == 'typing.Callable':
                return self.analyze_callable_type(t)
            elif fullname == 'typing.Type':
                if len(t.args) == 0:
                    return TypeType(AnyType(), line=t.line)
                if len(t.args) != 1:
                    self.fail('Type[...] must have exactly one type argument', t)
                item = self.anal_type(t.args[0])
                return TypeType(item, line=t.line)
            elif fullname == 'typing.ClassVar':
                if self.nesting_level > 0:
                    self.fail('Invalid type: ClassVar nested inside other type', t)
                if len(t.args) == 0:
                    return AnyType(line=t.line)
                if len(t.args) != 1:
                    self.fail('ClassVar[...] must have at most one type argument', t)
                    return AnyType()
                item = self.anal_type(t.args[0])
                if isinstance(item, TypeVarType) or get_type_vars(item):
                    self.fail('Invalid type: ClassVar cannot be generic', t)
                    return AnyType()
                return item
            elif fullname in ('mypy_extensions.NoReturn', 'typing.NoReturn'):
                return UninhabitedType(is_noreturn=True)
            elif sym.kind == TYPE_ALIAS:
                override = sym.type_override
                assert override is not None
                an_args = self.anal_array(t.args)
                all_vars = self.get_type_var_names(override)
                exp_len = len(all_vars)
                act_len = len(an_args)
                if exp_len > 0 and act_len == 0:
                    # Interpret bare Alias same as normal generic, i.e., Alias[Any, Any, ...]
                    return self.replace_alias_tvars(override, all_vars, [AnyType()] * exp_len,
                                                    t.line, t.column)
                if exp_len == 0 and act_len == 0:
                    return override
                if act_len != exp_len:
                    self.fail('Bad number of arguments for type alias, expected: %s, given: %s'
                              % (exp_len, act_len), t)
                    return t
                return self.replace_alias_tvars(override, all_vars, an_args, t.line, t.column)
            elif not isinstance(sym.node, TypeInfo):
                name = sym.fullname
                if name is None:
                    name = sym.node.name()
                if isinstance(sym.node, Var) and isinstance(sym.node.type, AnyType):
                    # Something with an Any type -- make it an alias for Any in a type
                    # context. This is slightly problematic as it allows using the type 'Any'
                    # as a base class -- however, this will fail soon at runtime so the problem
                    # is pretty minor.
                    return AnyType(from_unimported_type=True)
                # Allow unbound type variables when defining an alias
                if not (self.aliasing and sym.kind == TVAR and
                        self.tvar_scope.get_binding(sym) is None):
                    self.fail('Invalid type "{}"'.format(name), t)
                return t
            info = sym.node  # type: TypeInfo
            if len(t.args) > 0 and info.fullname() == 'builtins.tuple':
                return TupleType(self.anal_array(t.args),
                                 Instance(info, [AnyType()], t.line),
                                 t.line)
            else:
                # Analyze arguments and construct Instance type. The
                # number of type arguments and their values are
                # checked only later, since we do not always know the
                # valid count at this point. Thus we may construct an
                # Instance with an invalid number of type arguments.
                instance = Instance(info, self.anal_array(t.args), t.line, t.column)
                tup = info.tuple_type
                if tup is not None:
                    # The class has a Tuple[...] base class so it will be
                    # represented as a tuple type.
                    if t.args:
                        self.fail('Generic tuple types not supported', t)
                        return AnyType()
                    return tup.copy_modified(items=self.anal_array(tup.items),
                                             fallback=instance)
                td = info.typeddict_type
                if td is not None:
                    # The class has a TypedDict[...] base class so it will be
                    # represented as a typeddict type.
                    if t.args:
                        self.fail('Generic TypedDict types not supported', t)
                        return AnyType()
                    # Create a named TypedDictType
                    return td.copy_modified(item_types=self.anal_array(list(td.items.values())),
                                            fallback=instance)
                return instance
        else:
            return AnyType()

    def get_type_var_names(self, tp: Type) -> List[str]:
        """Get all type variable names that are present in a generic type alias
        in order of textual appearance (recursively, if needed).
        """
        return [name for name, _
                in tp.accept(TypeVariableQuery(self.lookup, self.tvar_scope,
                                               include_callables=True, include_bound_tvars=True))]

    def get_tvar_name(self, t: Type) -> Optional[str]:
        if not isinstance(t, UnboundType):
            return None
        sym = self.lookup(t.name, t)
        if sym is not None and sym.kind == TVAR:
            return t.name
        return None

    def replace_alias_tvars(self, tp: Type, vars: List[str], subs: List[Type],
                            newline: int, newcolumn: int) -> Type:
        """Replace type variables in a generic type alias tp with substitutions subs
        resetting context. Length of subs should be already checked.
        """
        typ_args = get_typ_args(tp)
        new_args = typ_args[:]
        for i, arg in enumerate(typ_args):
            tvar = self.get_tvar_name(arg)
            if tvar and tvar in vars:
                # Perform actual substitution...
                new_args[i] = subs[vars.index(tvar)]
            else:
                # ...recursively, if needed.
                new_args[i] = self.replace_alias_tvars(arg, vars, subs, newline, newcolumn)
        return set_typ_args(tp, new_args, newline, newcolumn)

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_type_list(self, t: TypeList) -> Type:
        self.fail('Invalid type', t)
        return AnyType()

    def visit_callable_argument(self, t: CallableArgument) -> Type:
        self.fail('Invalid type', t)
        return AnyType()

    def visit_instance(self, t: Instance) -> Type:
        return t

    def visit_type_var(self, t: TypeVarType) -> Type:
        return t

    def visit_callable_type(self, t: CallableType, nested: bool = True) -> Type:
        # Every Callable can bind its own type variables, if they're not in the outer scope
        with self.tvar_scope_frame():
            if self.aliasing:
                variables = t.variables
            else:
                variables = self.bind_function_type_variables(t, t)
            ret = t.copy_modified(arg_types=self.anal_array(t.arg_types, nested=nested),
                                  ret_type=self.anal_type(t.ret_type, nested=nested),
                                  fallback=t.fallback or self.builtin_type('builtins.function'),
                                  variables=self.anal_var_defs(variables))
        return ret

    def visit_tuple_type(self, t: TupleType) -> Type:
        # Types such as (t1, t2, ...) only allowed in assignment statements. They'll
        # generate errors elsewhere, and Tuple[t1, t2, ...] must be used instead.
        if t.implicit and not self.allow_tuple_literal:
            self.fail('Invalid tuple literal type', t)
            return AnyType()
        star_count = sum(1 for item in t.items if isinstance(item, StarType))
        if star_count > 1:
            self.fail('At most one star type allowed in a tuple', t)
            if t.implicit:
                return TupleType([AnyType() for _ in t.items],
                                 self.builtin_type('builtins.tuple'),
                                 t.line)
            else:
                return AnyType()
        fallback = t.fallback if t.fallback else self.builtin_type('builtins.tuple', [AnyType()])
        return TupleType(self.anal_array(t.items), fallback, t.line)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        items = OrderedDict([
            (item_name, self.anal_type(item_type))
            for (item_name, item_type) in t.items.items()
        ])
        return TypedDictType(items, t.fallback)

    def visit_star_type(self, t: StarType) -> Type:
        return StarType(self.anal_type(t.type), t.line)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.anal_array(t.items), t.line)

    def visit_partial_type(self, t: PartialType) -> Type:
        assert False, "Internal error: Unexpected partial type"

    def visit_ellipsis_type(self, t: EllipsisType) -> Type:
        self.fail("Unexpected '...'", t)
        return AnyType()

    def visit_type_type(self, t: TypeType) -> Type:
        return TypeType(self.anal_type(t.item), line=t.line)

    def analyze_callable_type(self, t: UnboundType) -> Type:
        fallback = self.builtin_type('builtins.function')
        if len(t.args) == 0:
            # Callable (bare). Treat as Callable[..., Any].
            ret = CallableType([AnyType(), AnyType()],
                               [nodes.ARG_STAR, nodes.ARG_STAR2],
                               [None, None],
                               ret_type=AnyType(),
                               fallback=fallback,
                               is_ellipsis_args=True)
        elif len(t.args) == 2:
            ret_type = t.args[1]
            if isinstance(t.args[0], TypeList):
                # Callable[[ARG, ...], RET] (ordinary callable type)
                args = []   # type: List[Type]
                names = []  # type: List[str]
                kinds = []  # type: List[int]
                for arg in t.args[0].items:
                    if isinstance(arg, CallableArgument):
                        args.append(arg.typ)
                        names.append(arg.name)
                        if arg.constructor is None:
                            return AnyType()
                        found = self.lookup(arg.constructor, arg)
                        if found is None:
                            # Looking it up already put an error message in
                            return AnyType()
                        elif found.fullname not in ARG_KINDS_BY_CONSTRUCTOR:
                            self.fail('Invalid argument constructor "{}"'.format(
                                found.fullname), arg)
                            return AnyType()
                        else:
                            kind = ARG_KINDS_BY_CONSTRUCTOR[found.fullname]
                            kinds.append(kind)
                            if arg.name is not None and kind in {ARG_STAR, ARG_STAR2}:
                                self.fail("{} arguments should not have names".format(
                                    arg.constructor), arg)
                                return AnyType()
                    else:
                        args.append(arg)
                        names.append(None)
                        kinds.append(ARG_POS)

                check_arg_names(names, [t] * len(args), self.fail, "Callable")
                check_arg_kinds(kinds, [t] * len(args), self.fail)
                ret = CallableType(args,
                                   kinds,
                                   names,
                                   ret_type=ret_type,
                                   fallback=fallback)
            elif isinstance(t.args[0], EllipsisType):
                # Callable[..., RET] (with literal ellipsis; accept arbitrary arguments)
                ret = CallableType([AnyType(), AnyType()],
                                   [nodes.ARG_STAR, nodes.ARG_STAR2],
                                   [None, None],
                                   ret_type=ret_type,
                                   fallback=fallback,
                                   is_ellipsis_args=True)
            else:
                self.fail('The first argument to Callable must be a list of types or "..."', t)
                return AnyType()
        else:
            self.fail('Invalid function type', t)
            return AnyType()
        assert isinstance(ret, CallableType)
        return ret.accept(self)

    @contextmanager
    def tvar_scope_frame(self) -> Iterator[None]:
        old_scope = self.tvar_scope
        self.tvar_scope = self.tvar_scope.method_frame()
        yield
        self.tvar_scope = old_scope

    def infer_type_variables(self,
                             type: CallableType) -> List[Tuple[str, TypeVarExpr]]:
        """Return list of unique type variables referred to in a callable."""
        names = []  # type: List[str]
        tvars = []  # type: List[TypeVarExpr]
        for arg in type.arg_types:
            for name, tvar_expr in arg.accept(TypeVariableQuery(self.lookup, self.tvar_scope)):
                if name not in names:
                    names.append(name)
                    tvars.append(tvar_expr)
        # When finding type variables in the return type of a function, don't
        # look inside Callable types.  Type variables only appearing in
        # functions in the return type belong to those functions, not the
        # function we're currently analyzing.
        for name, tvar_expr in type.ret_type.accept(
                TypeVariableQuery(self.lookup, self.tvar_scope, include_callables=False)):
            if name not in names:
                names.append(name)
                tvars.append(tvar_expr)
        return list(zip(names, tvars))

    def bind_function_type_variables(self,
                                     fun_type: CallableType, defn: Context) -> List[TypeVarDef]:
        """Find the type variables of the function type and bind them in our tvar_scope"""
        if fun_type.variables:
            for var in fun_type.variables:
                var_expr = self.lookup(var.name, var).node
                assert isinstance(var_expr, TypeVarExpr)
                self.tvar_scope.bind(var.name, var_expr)
            return fun_type.variables
        typevars = self.infer_type_variables(fun_type)
        # Do not define a new type variable if already defined in scope.
        typevars = [(name, tvar) for name, tvar in typevars
                    if not self.is_defined_type_var(name, defn)]
        defs = []  # type: List[TypeVarDef]
        for name, tvar in typevars:
            if not self.tvar_scope.allow_binding(tvar.fullname()):
                self.fail("Type variable '{}' is bound by an outer class".format(name), defn)
            self.tvar_scope.bind(name, tvar)
            binding = self.tvar_scope.get_binding(tvar.fullname())
            assert binding is not None
            defs.append(binding)

        return defs

    def is_defined_type_var(self, tvar: str, context: Context) -> bool:
        return self.tvar_scope.get_binding(self.lookup(tvar, context)) is not None

    def anal_array(self, a: List[Type], nested: bool = True) -> List[Type]:
        res = []  # type: List[Type]
        for t in a:
            res.append(self.anal_type(t, nested))
        return res

    def anal_type(self, t: Type, nested: bool = True) -> Type:
        if nested:
            self.nesting_level += 1
        try:
            return t.accept(self)
        finally:
            if nested:
                self.nesting_level -= 1

    def anal_var_defs(self, var_defs: List[TypeVarDef]) -> List[TypeVarDef]:
        a = []  # type: List[TypeVarDef]
        for vd in var_defs:
            a.append(TypeVarDef(vd.name, vd.id.raw_id, self.anal_array(vd.values),
                                vd.upper_bound.accept(self),
                                vd.variance,
                                vd.line))
        return a

    def builtin_type(self, fully_qualified_name: str, args: List[Type] = None) -> Instance:
        node = self.lookup_fqn_func(fully_qualified_name)
        assert isinstance(node.node, TypeInfo)
        return Instance(node.node, args or [])

    def tuple_type(self, items: List[Type]) -> TupleType:
        return TupleType(items, fallback=self.builtin_type('builtins.tuple', [AnyType()]))


class TypeAnalyserPass3(TypeVisitor[None]):
    """Analyze type argument counts and values of generic types.

    This is semantic analysis pass 3 for types.

    Perform these operations:

     * Report error for invalid type argument counts, such as List[x, y].
     * Make implicit Any type arguments explicit my modifying types
       in-place. For example, modify Foo into Foo[Any] if Foo expects a single
       type argument.
     * If a type variable has a value restriction, ensure that the value is
       valid. For example, reject IO[int] if the type argument must be str
       or bytes.

    We can't do this earlier than the third pass, since type argument counts
    are only determined in pass 2, and we have to support forward references
    to types.
    """

    def __init__(self, fail_func: Callable[[str, Context], None]) -> None:
        self.fail = fail_func

    def visit_instance(self, t: Instance) -> None:
        info = t.type
        # Check type argument count.
        if len(t.args) != len(info.type_vars):
            if len(t.args) == 0:
                # Insert implicit 'Any' type arguments.
                t.args = [AnyType()] * len(info.type_vars)
                return
            # Invalid number of type parameters.
            n = len(info.type_vars)
            s = '{} type arguments'.format(n)
            if n == 0:
                s = 'no type arguments'
            elif n == 1:
                s = '1 type argument'
            act = str(len(t.args))
            if act == '0':
                act = 'none'
            self.fail('"{}" expects {}, but {} given'.format(
                info.name(), s, act), t)
            # Construct the correct number of type arguments, as
            # otherwise the type checker may crash as it expects
            # things to be right.
            t.args = [AnyType() for _ in info.type_vars]
            t.invalid = True
        elif info.defn.type_vars:
            # Check type argument values.
            for (i, arg), tvar in zip(enumerate(t.args), info.defn.type_vars):
                if tvar.values:
                    if isinstance(arg, TypeVarType):
                        arg_values = arg.values
                        if not arg_values:
                            self.fail('Type variable "{}" not valid as type '
                                      'argument value for "{}"'.format(
                                          arg.name, info.name()), t)
                            continue
                    else:
                        arg_values = [arg]
                    self.check_type_var_values(info, arg_values,
                                               tvar.values, i + 1, t)
                if not is_subtype(arg, tvar.upper_bound):
                    self.fail('Type argument "{}" of "{}" must be '
                              'a subtype of "{}"'.format(
                                  arg, info.name(), tvar.upper_bound), t)
        for arg in t.args:
            arg.accept(self)
        if info.is_newtype:
            for base in info.bases:
                base.accept(self)

    def check_type_var_values(self, type: TypeInfo, actuals: List[Type],
                              valids: List[Type], arg_number: int, context: Context) -> None:
        for actual in actuals:
            if (not isinstance(actual, AnyType) and
                    not any(is_same_type(actual, value) for value in valids)):
                if len(actuals) > 1 or not isinstance(actual, Instance):
                    self.fail('Invalid type argument value for "{}"'.format(
                        type.name()), context)
                else:
                    self.fail('Type argument {} of "{}" has incompatible value "{}"'.format(
                        arg_number, type.name(), actual.type.name()), context)

    def visit_callable_type(self, t: CallableType) -> None:
        t.ret_type.accept(self)
        for arg_type in t.arg_types:
            arg_type.accept(self)

    def visit_tuple_type(self, t: TupleType) -> None:
        for item in t.items:
            item.accept(self)

    def visit_typeddict_type(self, t: TypedDictType) -> None:
        for item_type in t.items.values():
            item_type.accept(self)

    def visit_union_type(self, t: UnionType) -> None:
        for item in t.items:
            item.accept(self)

    def visit_star_type(self, t: StarType) -> None:
        t.type.accept(self)

    # Other kinds of type are trivial, since they are atomic (or invalid).

    def visit_unbound_type(self, t: UnboundType) -> None:
        pass

    def visit_any(self, t: AnyType) -> None:
        pass

    def visit_none_type(self, t: NoneTyp) -> None:
        pass

    def visit_uninhabited_type(self, t: UninhabitedType) -> None:
        pass

    def visit_deleted_type(self, t: DeletedType) -> None:
        pass

    def visit_type_list(self, t: TypeList) -> None:
        self.fail('Invalid type', t)

    def visit_type_var(self, t: TypeVarType) -> None:
        pass

    def visit_partial_type(self, t: PartialType) -> None:
        pass

    def visit_type_type(self, t: TypeType) -> None:
        pass


TypeVarList = List[Tuple[str, TypeVarExpr]]


def remove_dups(tvars: Iterable[T]) -> List[T]:
    # Get unique elements in order of appearance
    all_tvars = set()  # type: Set[T]
    new_tvars = []  # type: List[T]
    for t in tvars:
        if t not in all_tvars:
            new_tvars.append(t)
            all_tvars.add(t)
    return new_tvars


def flatten_tvars(ll: Iterable[List[T]]) -> List[T]:
    return remove_dups(chain.from_iterable(ll))


class TypeVariableQuery(TypeQuery[TypeVarList]):

    def __init__(self,
                 lookup: Callable[[str, Context], SymbolTableNode],
                 scope: 'TypeVarScope',
                 *,
                 include_callables: bool = True,
                 include_bound_tvars: bool = False) -> None:
        self.include_callables = include_callables
        self.lookup = lookup
        self.scope = scope
        self.include_bound_tvars = include_bound_tvars
        super().__init__(flatten_tvars)

    def _seems_like_callable(self, type: UnboundType) -> bool:
        if not type.args:
            return False
        if isinstance(type.args[0], (EllipsisType, TypeList)):
            return True
        return False

    def visit_unbound_type(self, t: UnboundType) -> TypeVarList:
        name = t.name
        node = self.lookup(name, t)
        if node and node.kind == TVAR and (
                self.include_bound_tvars or self.scope.get_binding(node) is None):
            assert isinstance(node.node, TypeVarExpr)
            return [(name, node.node)]
        elif not self.include_callables and self._seems_like_callable(t):
            return []
        else:
            return super().visit_unbound_type(t)

    def visit_callable_type(self, t: CallableType) -> TypeVarList:
        if self.include_callables:
            return super().visit_callable_type(t)
        else:
            return []


def has_any_from_unimported_type(t: Type) -> bool:
    """Return true if this type is Any because an import was not followed.

    If type t is such Any type or has type arguments that contain such Any type
    this function will return true.
    """
    return t.accept(HasAnyFromUnimportedType())


class HasAnyFromUnimportedType(TypeQuery[bool]):
    def __init__(self) -> None:
        super().__init__(any)

    def visit_any(self, t: AnyType) -> bool:
        return t.from_unimported_type


def make_optional_type(t: Type) -> Type:
    """Return the type corresponding to Optional[t].

    Note that we can't use normal union simplification, since this function
    is called during semantic analysis and simplification only works during
    type checking.
    """
    if not experiments.STRICT_OPTIONAL:
        return t
    if isinstance(t, NoneTyp):
        return t
    if isinstance(t, UnionType):
        items = [item for item in union_items(t)
                 if not isinstance(item, NoneTyp)]
        return UnionType(items + [NoneTyp()], t.line, t.column)
    return UnionType([t, NoneTyp()], t.line, t.column)
