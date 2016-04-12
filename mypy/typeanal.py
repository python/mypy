"""Semantic analysis of types"""

from typing import Callable, cast, List, Tuple

from mypy.types import (
    Type, UnboundType, TypeVarType, TupleType, UnionType, Instance, AnyType, CallableType,
    Void, NoneTyp, DeletedType, TypeList, TypeVarDef, TypeVisitor, StarType, PartialType,
    EllipsisType
)
from mypy.nodes import (
    BOUND_TVAR, TYPE_ALIAS, UNBOUND_IMPORTED,
    TypeInfo, Context, SymbolTableNode, TypeVarExpr, Var, Node,
    IndexExpr, RefExpr
)
from mypy.sametypes import is_same_type
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.subtypes import satisfies_upper_bound
from mypy import nodes


type_constructors = ['typing.Tuple', 'typing.Union', 'typing.Callable']


def analyze_type_alias(node: Node,
                       lookup_func: Callable[[str, Context], SymbolTableNode],
                       lookup_fqn_func: Callable[[str], SymbolTableNode],
                       fail_func: Callable[[str, Context], None]) -> Type:
    """Return type if node is valid as a type alias rvalue.

    Return None otherwise. 'node' must have been semantically analyzed.
    """
    # Quickly return None if the expression doesn't look like a type. Note
    # that we don't support straight string literals as type aliases
    # (only string literals within index expressions).
    if isinstance(node, RefExpr):
        if not (isinstance(node.node, TypeInfo) or
                node.fullname == 'typing.Any' or
                node.kind == TYPE_ALIAS):
            return None
    elif isinstance(node, IndexExpr):
        base = node.base
        if isinstance(base, RefExpr):
            if not (isinstance(base.node, TypeInfo) or
                    base.fullname in type_constructors):
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
    analyzer = TypeAnalyser(lookup_func, lookup_fqn_func, fail_func)
    return type.accept(analyzer)


class TypeAnalyser(TypeVisitor[Type]):
    """Semantic analyzer for types (semantic analysis pass 2).

    Converts unbound types into bound types.
    """

    def __init__(self,
                 lookup_func: Callable[[str, Context], SymbolTableNode],
                 lookup_fqn_func: Callable[[str], SymbolTableNode],
                 fail_func: Callable[[str, Context], None]) -> None:
        self.lookup = lookup_func
        self.lookup_fqn_func = lookup_fqn_func
        self.fail = fail_func

    def visit_unbound_type(self, t: UnboundType) -> Type:
        sym = self.lookup(t.name, t)
        if sym is not None:
            if sym.node is None:
                # UNBOUND_IMPORTED can happen if an unknown name was imported.
                if sym.kind != UNBOUND_IMPORTED:
                    self.fail('Internal error (node is None, kind={})'.format(sym.kind), t)
                return AnyType()
            fullname = sym.node.fullname()
            if sym.kind == BOUND_TVAR:
                if len(t.args) > 0:
                    self.fail('Type variable "{}" used with arguments'.format(
                        t.name), t)
                tvar_expr = cast(TypeVarExpr, sym.node)
                return TypeVarType(t.name, sym.tvar_id, tvar_expr.values,
                                   tvar_expr.upper_bound,
                                   tvar_expr.variance,
                                   t.line)
            elif fullname == 'builtins.None':
                return Void()
            elif fullname == 'typing.Any':
                return AnyType()
            elif fullname == 'typing.Tuple':
                if len(t.args) == 2 and isinstance(t.args[1], EllipsisType):
                    # Tuple[T, ...] (uniform, variable-length tuple)
                    node = self.lookup_fqn_func('builtins.tuple')
                    info = cast(TypeInfo, node.node)
                    return Instance(info, [t.args[0].accept(self)], t.line)
                return TupleType(self.anal_array(t.args),
                                 self.builtin_type('builtins.tuple'))
            elif fullname == 'typing.Union':
                items = self.anal_array(t.args)
                items = [item for item in items if not isinstance(item, Void)]
                return UnionType.make_union(items)
            elif fullname == 'typing.Optional':
                if len(t.args) != 1:
                    self.fail('Optional[...] must have exactly one type argument', t)
                items = self.anal_array(t.args)
                # Currently Optional[t] is just an alias for t.
                return items[0]
            elif fullname == 'typing.Callable':
                return self.analyze_callable_type(t)
            elif sym.kind == TYPE_ALIAS:
                # TODO: Generic type aliases.
                return sym.type_override
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
                self.fail('Invalid type "{}"'.format(name), t)
                return t
            info = cast(TypeInfo, sym.node)
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
                instance = Instance(info, self.anal_array(t.args), t.line)
                if info.tuple_type is None:
                    return instance
                else:
                    # The class has a Tuple[...] base class so it will be
                    # represented as a tuple type.
                    if t.args:
                        self.fail('Generic tuple types not supported', t)
                        return AnyType()
                    return TupleType(self.anal_array(info.tuple_type.items),
                                     fallback=instance,
                                     line=t.line)
        else:
            return AnyType()

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_void(self, t: Void) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_type_list(self, t: TypeList) -> Type:
        self.fail('Invalid type', t)
        return AnyType()

    def visit_instance(self, t: Instance) -> Type:
        return t

    def visit_type_var(self, t: TypeVarType) -> Type:
        raise RuntimeError('TypeVarType is already analyzed')

    def visit_callable_type(self, t: CallableType) -> Type:
        return t.copy_modified(arg_types=self.anal_array(t.arg_types),
                               ret_type=t.ret_type.accept(self),
                               fallback=t.fallback or self.builtin_type('builtins.function'),
                               variables=self.anal_var_defs(t.variables))

    def visit_tuple_type(self, t: TupleType) -> Type:
        if t.implicit:
            self.fail('Invalid tuple literal type', t)
            return AnyType()
        star_count = sum(1 for item in t.items if isinstance(item, StarType))
        if star_count > 1:
            self.fail('At most one star type allowed in a tuple', t)
            return AnyType()
        fallback = t.fallback if t.fallback else self.builtin_type('builtins.tuple')
        return TupleType(self.anal_array(t.items), fallback, t.line)

    def visit_star_type(self, t: StarType) -> Type:
        return StarType(t.type.accept(self), t.line)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.anal_array(t.items), t.line)

    def visit_partial_type(self, t: PartialType) -> Type:
        assert False, "Internal error: Unexpected partial type"

    def visit_ellipsis_type(self, t: EllipsisType) -> Type:
        self.fail("Unexpected '...'", t)
        return AnyType()

    def analyze_callable_type(self, t: UnboundType) -> Type:
        fallback = self.builtin_type('builtins.function')
        if len(t.args) == 0:
            # Callable (bare)
            return CallableType([AnyType(), AnyType()],
                                [nodes.ARG_STAR, nodes.ARG_STAR2],
                                [None, None],
                                ret_type=AnyType(),
                                fallback=fallback)
        elif len(t.args) == 2:
            ret_type = t.args[1].accept(self)
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

    def anal_array(self, a: List[Type]) -> List[Type]:
        res = []  # type: List[Type]
        for t in a:
            res.append(t.accept(self))
        return res

    def anal_var_defs(self, var_defs: List[TypeVarDef]) -> List[TypeVarDef]:
        a = []  # type: List[TypeVarDef]
        for vd in var_defs:
            a.append(TypeVarDef(vd.name, vd.id, self.anal_array(vd.values),
                                vd.upper_bound.accept(self),
                                vd.variance,
                                vd.line))
        return a

    def builtin_type(self, fully_qualified_name: str) -> Instance:
        node = self.lookup_fqn_func(fully_qualified_name)
        info = cast(TypeInfo, node.node)
        return Instance(info, [])


class TypeAnalyserPass3(TypeVisitor[None]):
    """Analyze type argument counts and values of generic types.

    This is semantic analysis pass 3 for types.

    Perform these operations:

     * Report error for invalid type argument counts, such as List[x, y].
     * Make implicit Any type argumenents explicit my modifying types
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
        elif info.defn.type_vars:
            # Check type argument values.
            for arg, TypeVar in zip(t.args, info.defn.type_vars):
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
                                               TypeVar.values, t)
                if not satisfies_upper_bound(arg, TypeVar.upper_bound):
                    self.fail('Type argument "{}" of "{}" must be '
                              'a subtype of "{}"'.format(
                                  arg, info.name(), TypeVar.upper_bound), t)
        for arg in t.args:
            arg.accept(self)

    def check_type_var_values(self, type: TypeInfo, actuals: List[Type],
                              valids: List[Type], context: Context) -> None:
        for actual in actuals:
            if (not isinstance(actual, AnyType) and
                    not any(is_same_type(actual, value) for value in valids)):
                self.fail('Invalid type argument value for "{}"'.format(
                    type.name()), context)

    def visit_callable_type(self, t: CallableType) -> None:
        t.ret_type.accept(self)
        for arg_type in t.arg_types:
            arg_type.accept(self)

    def visit_tuple_type(self, t: TupleType) -> None:
        for item in t.items:
            item.accept(self)

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

    def visit_void(self, t: Void) -> None:
        pass

    def visit_none_type(self, t: NoneTyp) -> None:
        pass

    def visit_deleted_type(self, t: DeletedType) -> None:
        pass

    def visit_type_list(self, t: TypeList) -> None:
        self.fail('Invalid type', t)

    def visit_type_var(self, t: TypeVarType) -> None:
        pass

    def visit_partial_type(self, t: PartialType) -> None:
        pass
