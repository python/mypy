"""Semantic analysis of types"""

from collections import OrderedDict
from typing import Callable, List, Optional, Set

from mypy.types import (
    Type, UnboundType, TypeVarType, TupleType, TypedDictType, UnionType, Instance,
    AnyType, CallableType, NoneTyp, DeletedType, TypeList, TypeVarDef, TypeVisitor,
    StarType, PartialType, EllipsisType, UninhabitedType, TypeType, get_typ_args, set_typ_args,
    get_type_vars,
)
from mypy.nodes import (
    BOUND_TVAR, UNBOUND_TVAR, TYPE_ALIAS, UNBOUND_IMPORTED,
    TypeInfo, Context, SymbolTableNode, Var, Expression,
    IndexExpr, RefExpr, nongen_builtins,
)
from mypy.sametypes import is_same_type
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.subtypes import is_subtype
from mypy import nodes
from mypy import join
from mypy import experiments


type_constructors = {
    'typing.Callable',
    'typing.Optional',
    'typing.Tuple',
    'typing.Type',
    'typing.Union',
}


def analyze_type_alias(node: Expression,
                       lookup_func: Callable[[str, Context], SymbolTableNode],
                       lookup_fqn_func: Callable[[str], SymbolTableNode],
                       fail_func: Callable[[str, Context], None],
                       allow_unnormalized: bool = False) -> Type:
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
        if node.kind == UNBOUND_TVAR or node.kind == BOUND_TVAR:
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
    analyzer = TypeAnalyser(lookup_func, lookup_fqn_func, fail_func, aliasing=True,
                            allow_unnormalized=allow_unnormalized)
    return type.accept(analyzer)


def no_subscript_builtin_alias(name: str, propose_alt: bool = True) -> str:
    msg = '"{}" is not subscriptable'.format(name.split('.')[-1])
    replacement = nongen_builtins[name]
    if replacement and propose_alt:
        msg += ', use "{}" instead'.format(replacement)
    return msg


class TypeAnalyser(TypeVisitor[Type]):
    """Semantic analyzer for types (semantic analysis pass 2).

    Converts unbound types into bound types.
    """

    def __init__(self,
                 lookup_func: Callable[[str, Context], SymbolTableNode],
                 lookup_fqn_func: Callable[[str], SymbolTableNode],
                 fail_func: Callable[[str, Context], None], *,
                 aliasing: bool = False,
                 allow_tuple_literal: bool = False,
                 allow_unnormalized: bool = False) -> None:
        self.lookup = lookup_func
        self.lookup_fqn_func = lookup_fqn_func
        self.fail = fail_func
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
            return UnionType.make_simplified_union([self.visit_unbound_type(t), NoneTyp()])
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
            if sym.kind == BOUND_TVAR:
                if len(t.args) > 0:
                    self.fail('Type variable "{}" used with arguments'.format(
                        t.name), t)
                assert sym.tvar_def is not None
                return TypeVarType(sym.tvar_def, t.line)
            elif fullname == 'builtins.None':
                return NoneTyp()
            elif fullname == 'typing.Any' or fullname == 'builtins.Any':
                return AnyType()
            elif fullname == 'typing.Tuple':
                if len(t.args) == 0 and not t.empty_tuple_index:
                    # Bare 'Tuple' is same as 'tuple'
                    return self.builtin_type('builtins.tuple', [AnyType()])
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
                return UnionType.make_simplified_union([item, NoneTyp()])
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
                    return AnyType()
                # Allow unbound type variables when defining an alias
                if not (self.aliasing and sym.kind == UNBOUND_TVAR):
                    self.fail('Invalid type "{}"'.format(name), t)
                return t
            info = sym.node  # type: TypeInfo
            if info.fullname() == 'builtins.tuple':
                assert not t.args
                t.args = [AnyType()]
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
        tvars = []  # type: List[str]
        typ_args = get_typ_args(tp)
        for arg in typ_args:
            tvar = self.get_tvar_name(arg)
            if tvar:
                tvars.append(tvar)
            else:
                subvars = self.get_type_var_names(arg)
                if subvars:
                    tvars.extend(subvars)
        # Get unique type variables in order of appearance
        all_tvars = set(tvars)
        new_tvars = []
        for t in tvars:
            if t in all_tvars:
                new_tvars.append(t)
                all_tvars.remove(t)
        return new_tvars

    def get_tvar_name(self, t: Type) -> Optional[str]:
        if not isinstance(t, UnboundType):
            return None
        sym = self.lookup(t.name, t)
        if sym is not None and (sym.kind == UNBOUND_TVAR or sym.kind == BOUND_TVAR):
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

    def visit_instance(self, t: Instance) -> Type:
        return t

    def visit_type_var(self, t: TypeVarType) -> Type:
        return t

    def visit_callable_type(self, t: CallableType) -> Type:
        return t.copy_modified(arg_types=self.anal_array(t.arg_types, nested=False),
                               ret_type=self.anal_type(t.ret_type, nested=False),
                               fallback=t.fallback or self.builtin_type('builtins.function'),
                               variables=self.anal_var_defs(t.variables))

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
                                 self.builtin_type('builtins.tuple', [AnyType()]),
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
            return CallableType([AnyType(), AnyType()],
                                [nodes.ARG_STAR, nodes.ARG_STAR2],
                                [None, None],
                                ret_type=AnyType(),
                                fallback=fallback,
                                is_ellipsis_args=True)
        elif len(t.args) == 2:
            ret_type = self.anal_type(t.args[1])
            if isinstance(t.args[0], TypeList):
                # Callable[[ARG, ...], RET] (ordinary callable type)
                args = t.args[0].items
                return CallableType(self.anal_array(args),
                                    [nodes.ARG_POS] * len(args),
                                    [None] * len(args),
                                    ret_type=ret_type,
                                    fallback=fallback)
            elif isinstance(t.args[0], EllipsisType):
                # Callable[..., RET] (with literal ellipsis; accept arbitrary arguments)
                return CallableType([AnyType(), AnyType()],
                                    [nodes.ARG_STAR, nodes.ARG_STAR2],
                                    [None, None],
                                    ret_type=ret_type,
                                    fallback=fallback,
                                    is_ellipsis_args=True)
            else:
                self.fail('The first argument to Callable must be a list of types or "..."', t)
                return AnyType()

        self.fail('Invalid function type', t)
        return AnyType()

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
            for (i, arg), TypeVar in zip(enumerate(t.args), info.defn.type_vars):
                if TypeVar.values:
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
                                               TypeVar.values, i + 1, t)
                if not is_subtype(arg, TypeVar.upper_bound):
                    self.fail('Type argument "{}" of "{}" must be '
                              'a subtype of "{}"'.format(
                                  arg, info.name(), TypeVar.upper_bound), t)
        for arg in t.args:
            arg.accept(self)

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
        # if it's not builtins.tuple, then its bases should have tuple[Any]
        # TODO: put assert here if it's not too slow
        if type(t.fallback) == Instance and t.fallback.type.fullname() == 'builtins.tuple':
            fallback_item = join.join_type_list(t.items)
            t.fallback.args = [fallback_item]

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
