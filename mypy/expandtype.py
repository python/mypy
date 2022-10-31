from __future__ import annotations

from typing import Iterable, Mapping, Sequence, TypeVar, cast, overload

from mypy.nodes import ARG_STAR
from mypy.types import (
    AnyType,
    CallableType,
    DeletedType,
    ErasedType,
    FunctionLike,
    Instance,
    LiteralType,
    NoneType,
    Overloaded,
    Parameters,
    ParamSpecFlavor,
    ParamSpecType,
    PartialType,
    ProperType,
    TupleType,
    Type,
    TypeAliasType,
    TypedDictType,
    TypeList,
    TypeType,
    TypeVarId,
    TypeVarLikeType,
    TypeVarTupleType,
    TypeVarType,
    TypeVisitor,
    UnboundType,
    UninhabitedType,
    UnionType,
    UnpackType,
    get_proper_type,
)
from mypy.typevartuples import split_with_instance, split_with_prefix_and_suffix


@overload
def expand_type(typ: ProperType, env: Mapping[TypeVarId, Type]) -> ProperType:
    ...


@overload
def expand_type(typ: Type, env: Mapping[TypeVarId, Type]) -> Type:
    ...


def expand_type(typ: Type, env: Mapping[TypeVarId, Type]) -> Type:
    """Substitute any type variable references in a type given by a type
    environment.
    """
    return typ.accept(ExpandTypeVisitor(env))


@overload
def expand_type_by_instance(typ: ProperType, instance: Instance) -> ProperType:
    ...


@overload
def expand_type_by_instance(typ: Type, instance: Instance) -> Type:
    ...


def expand_type_by_instance(typ: Type, instance: Instance) -> Type:
    """Substitute type variables in type using values from an Instance.
    Type variables are considered to be bound by the class declaration."""
    if not instance.args:
        return typ
    else:
        variables: dict[TypeVarId, Type] = {}
        if instance.type.has_type_var_tuple_type:
            assert instance.type.type_var_tuple_prefix is not None
            assert instance.type.type_var_tuple_suffix is not None

            args_prefix, args_middle, args_suffix = split_with_instance(instance)
            tvars_prefix, tvars_middle, tvars_suffix = split_with_prefix_and_suffix(
                tuple(instance.type.defn.type_vars),
                instance.type.type_var_tuple_prefix,
                instance.type.type_var_tuple_suffix,
            )
            variables = {tvars_middle[0].id: TypeList(list(args_middle))}
            instance_args = args_prefix + args_suffix
            tvars = tvars_prefix + tvars_suffix
        else:
            tvars = tuple(instance.type.defn.type_vars)
            instance_args = instance.args

        for binder, arg in zip(tvars, instance_args):
            variables[binder.id] = arg

        return expand_type(typ, variables)


F = TypeVar("F", bound=FunctionLike)


def freshen_function_type_vars(callee: F) -> F:
    """Substitute fresh type variables for generic function type variables."""
    if isinstance(callee, CallableType):
        if not callee.is_generic():
            return cast(F, callee)
        tvs = []
        tvmap: dict[TypeVarId, Type] = {}
        for v in callee.variables:
            if isinstance(v, TypeVarType):
                tv: TypeVarLikeType = TypeVarType.new_unification_variable(v)
            elif isinstance(v, TypeVarTupleType):
                assert isinstance(v, TypeVarTupleType)
                tv = TypeVarTupleType.new_unification_variable(v)
            else:
                assert isinstance(v, ParamSpecType)
                tv = ParamSpecType.new_unification_variable(v)
            tvs.append(tv)
            tvmap[v.id] = tv
        fresh = cast(CallableType, expand_type(callee, tvmap)).copy_modified(variables=tvs)
        return cast(F, fresh)
    else:
        assert isinstance(callee, Overloaded)
        fresh_overload = Overloaded([freshen_function_type_vars(item) for item in callee.items])
        return cast(F, fresh_overload)


class ExpandTypeVisitor(TypeVisitor[Type]):
    """Visitor that substitutes type variables with values."""

    variables: Mapping[TypeVarId, Type]  # TypeVar id -> TypeVar value

    def __init__(self, variables: Mapping[TypeVarId, Type]) -> None:
        self.variables = variables

    def visit_unbound_type(self, t: UnboundType) -> Type:
        return t

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_none_type(self, t: NoneType) -> Type:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_erased_type(self, t: ErasedType) -> Type:
        # Should not get here.
        raise RuntimeError()

    def visit_instance(self, t: Instance) -> Type:
        args = self.expand_types_with_unpack(list(t.args))
        if isinstance(args, list):
            return t.copy_modified(args=args)
        else:
            return args

    def visit_type_var(self, t: TypeVarType) -> Type:
        repl = self.variables.get(t.id, t)
        if isinstance(repl, ProperType) and isinstance(repl, Instance):
            # TODO: do we really need to do this?
            # If I try to remove this special-casing ~40 tests fail on reveal_type().
            return repl.copy_modified(last_known_value=None)
        return repl

    def visit_param_spec(self, t: ParamSpecType) -> Type:
        repl = get_proper_type(self.variables.get(t.id, t))
        if isinstance(repl, Instance):
            # TODO: what does prefix mean in this case?
            # TODO: why does this case even happen? Instances aren't plural.
            return repl
        elif isinstance(repl, ParamSpecType):
            return repl.copy_modified(
                flavor=t.flavor,
                prefix=t.prefix.copy_modified(
                    arg_types=t.prefix.arg_types + repl.prefix.arg_types,
                    arg_kinds=t.prefix.arg_kinds + repl.prefix.arg_kinds,
                    arg_names=t.prefix.arg_names + repl.prefix.arg_names,
                ),
            )
        elif isinstance(repl, Parameters) or isinstance(repl, CallableType):
            # if the paramspec is *P.args or **P.kwargs:
            if t.flavor != ParamSpecFlavor.BARE:
                assert isinstance(repl, CallableType), "Should not be able to get here."
                # Is this always the right thing to do?
                param_spec = repl.param_spec()
                if param_spec:
                    return param_spec.with_flavor(t.flavor)
                else:
                    return repl
            else:
                return Parameters(
                    t.prefix.arg_types + repl.arg_types,
                    t.prefix.arg_kinds + repl.arg_kinds,
                    t.prefix.arg_names + repl.arg_names,
                    variables=[*t.prefix.variables, *repl.variables],
                )
        else:
            # TODO: should this branch be removed? better not to fail silently
            return repl

    def visit_type_var_tuple(self, t: TypeVarTupleType) -> Type:
        raise NotImplementedError

    def visit_unpack_type(self, t: UnpackType) -> Type:
        # It is impossible to reasonally implement visit_unpack_type, because
        # unpacking inherently expands to something more like a list of types.
        #
        # Relevant sections that can call unpack should call expand_unpack()
        # instead.
        assert False, "Mypy bug: unpacking must happen at a higher level"

    def expand_unpack(self, t: UnpackType) -> list[Type] | Instance | AnyType | None:
        return expand_unpack_with_variables(t, self.variables)

    def visit_parameters(self, t: Parameters) -> Type:
        return t.copy_modified(arg_types=self.expand_types(t.arg_types))

    def visit_callable_type(self, t: CallableType) -> Type:
        param_spec = t.param_spec()
        if param_spec is not None:
            repl = get_proper_type(self.variables.get(param_spec.id))
            # If a ParamSpec in a callable type is substituted with a
            # callable type, we can't use normal substitution logic,
            # since ParamSpec is actually split into two components
            # *P.args and **P.kwargs in the original type. Instead, we
            # must expand both of them with all the argument types,
            # kinds and names in the replacement. The return type in
            # the replacement is ignored.
            if isinstance(repl, CallableType) or isinstance(repl, Parameters):
                # Substitute *args: P.args, **kwargs: P.kwargs
                prefix = param_spec.prefix
                # we need to expand the types in the prefix, so might as well
                # not get them in the first place
                t = t.expand_param_spec(repl, no_prefix=True)
                return t.copy_modified(
                    arg_types=self.expand_types(prefix.arg_types) + t.arg_types,
                    arg_kinds=prefix.arg_kinds + t.arg_kinds,
                    arg_names=prefix.arg_names + t.arg_names,
                    ret_type=t.ret_type.accept(self),
                    type_guard=(t.type_guard.accept(self) if t.type_guard is not None else None),
                )

        var_arg = t.var_arg()
        if var_arg is not None and isinstance(var_arg.typ, UnpackType):
            expanded = self.expand_unpack(var_arg.typ)
            # Handle other cases later.
            assert isinstance(expanded, list)
            assert len(expanded) == 1 and isinstance(expanded[0], UnpackType)
            star_index = t.arg_kinds.index(ARG_STAR)
            arg_types = (
                self.expand_types(t.arg_types[:star_index])
                + expanded
                + self.expand_types(t.arg_types[star_index + 1 :])
            )
        else:
            arg_types = self.expand_types(t.arg_types)

        return t.copy_modified(
            arg_types=arg_types,
            ret_type=t.ret_type.accept(self),
            type_guard=(t.type_guard.accept(self) if t.type_guard is not None else None),
        )

    def visit_overloaded(self, t: Overloaded) -> Type:
        items: list[CallableType] = []
        for item in t.items:
            new_item = item.accept(self)
            assert isinstance(new_item, ProperType)
            assert isinstance(new_item, CallableType)
            items.append(new_item)
        return Overloaded(items)

    def expand_types_with_unpack(
        self, typs: Sequence[Type]
    ) -> list[Type] | AnyType | UninhabitedType | Instance:
        """Expands a list of types that has an unpack.

        In corner cases, this can return a type rather than a list, in which case this
        indicates use of Any or some error occurred earlier. In this case callers should
        simply propagate the resulting type.
        """
        items: list[Type] = []
        for item in typs:
            if isinstance(item, UnpackType):
                unpacked_items = self.expand_unpack(item)
                if unpacked_items is None:
                    # TODO: better error, something like tuple of unknown?
                    return UninhabitedType()
                elif isinstance(unpacked_items, Instance):
                    if len(typs) == 1:
                        return unpacked_items
                    else:
                        assert False, "Invalid unpack of variable length tuple"
                elif isinstance(unpacked_items, AnyType):
                    return unpacked_items
                else:
                    items.extend(unpacked_items)
            else:
                # Must preserve original aliases when possible.
                items.append(item.accept(self))
        return items

    def visit_tuple_type(self, t: TupleType) -> Type:
        items = self.expand_types_with_unpack(t.items)
        if isinstance(items, list):
            fallback = t.partial_fallback.accept(self)
            fallback = get_proper_type(fallback)
            if not isinstance(fallback, Instance):
                fallback = t.partial_fallback
            return t.copy_modified(items=items, fallback=fallback)
        else:
            return items

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        fallback = t.fallback.accept(self)
        fallback = get_proper_type(fallback)
        if not isinstance(fallback, Instance):
            fallback = t.fallback
        return t.copy_modified(item_types=self.expand_types(t.items.values()), fallback=fallback)

    def visit_literal_type(self, t: LiteralType) -> Type:
        # TODO: Verify this implementation is correct
        return t

    def visit_union_type(self, t: UnionType) -> Type:
        # After substituting for type variables in t.items,
        # some of the resulting types might be subtypes of others.
        from mypy.typeops import make_simplified_union  # asdf

        return make_simplified_union(self.expand_types(t.items), t.line, t.column)

    def visit_partial_type(self, t: PartialType) -> Type:
        return t

    def visit_type_type(self, t: TypeType) -> Type:
        # TODO: Verify that the new item type is valid (instance or
        # union of instances or Any).  Sadly we can't report errors
        # here yet.
        item = t.item.accept(self)
        return TypeType.make_normalized(item)

    def visit_type_alias_type(self, t: TypeAliasType) -> Type:
        # Target of the type alias cannot contain type variables,
        # so we just expand the arguments.
        return t.copy_modified(args=self.expand_types(t.args))

    def expand_types(self, types: Iterable[Type]) -> list[Type]:
        a: list[Type] = []
        for t in types:
            a.append(t.accept(self))
        return a


def expand_unpack_with_variables(
    t: UnpackType, variables: Mapping[TypeVarId, Type]
) -> list[Type] | Instance | AnyType | None:
    """May return either a list of types to unpack to, any, or a single
    variable length tuple. The latter may not be valid in all contexts.
    """
    if isinstance(t.type, TypeVarTupleType):
        repl = get_proper_type(variables.get(t.type.id, t))
        if isinstance(repl, TupleType):
            return repl.items
        if isinstance(repl, TypeList):
            return repl.items
        elif isinstance(repl, Instance) and repl.type.fullname == "builtins.tuple":
            return repl
        elif isinstance(repl, AnyType):
            # tuple[Any, ...] would be better, but we don't have
            # the type info to construct that type here.
            return repl
        elif isinstance(repl, TypeVarTupleType):
            return [UnpackType(typ=repl)]
        elif isinstance(repl, UnpackType):
            return [repl]
        elif isinstance(repl, UninhabitedType):
            return None
        else:
            raise NotImplementedError(f"Invalid type replacement to expand: {repl}")
    else:
        raise NotImplementedError(f"Invalid type to expand: {t.type}")
