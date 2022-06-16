from typing import Dict, Iterable, List, TypeVar, Mapping, cast, Union, Optional

from mypy.types import (
    Type, Instance, CallableType, TypeVisitor, UnboundType, AnyType,
    NoneType, Overloaded, TupleType, TypedDictType, UnionType,
    ErasedType, PartialType, DeletedType, UninhabitedType, TypeType, TypeVarId,
    FunctionLike, TypeVarType, LiteralType, get_proper_type, ProperType,
    TypeAliasType, ParamSpecType, TypeVarLikeType, Parameters, ParamSpecFlavor,
    UnpackType, TypeVarTupleType
)


def expand_type(typ: Type, env: Mapping[TypeVarId, Type]) -> Type:
    """Substitute any type variable references in a type given by a type
    environment.
    """
    # TODO: use an overloaded signature? (ProperType stays proper after expansion.)
    return typ.accept(ExpandTypeVisitor(env))


def expand_type_by_instance(typ: Type, instance: Instance) -> Type:
    """Substitute type variables in type using values from an Instance.
    Type variables are considered to be bound by the class declaration."""
    # TODO: use an overloaded signature? (ProperType stays proper after expansion.)
    if not instance.args:
        return typ
    else:
        variables: Dict[TypeVarId, Type] = {}
        for binder, arg in zip(instance.type.defn.type_vars, instance.args):
            variables[binder.id] = arg
        return expand_type(typ, variables)


F = TypeVar('F', bound=FunctionLike)


def freshen_function_type_vars(callee: F) -> F:
    """Substitute fresh type variables for generic function type variables."""
    if isinstance(callee, CallableType):
        if not callee.is_generic():
            return cast(F, callee)
        tvs = []
        tvmap: Dict[TypeVarId, Type] = {}
        for v in callee.variables:
            # TODO(PEP612): fix for ParamSpecType
            if isinstance(v, TypeVarType):
                tv: TypeVarLikeType = TypeVarType.new_unification_variable(v)
            elif isinstance(v, TypeVarTupleType):
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
        fresh_overload = Overloaded([freshen_function_type_vars(item)
                                     for item in callee.items])
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
        args = self.expand_types(t.args)
        return Instance(t.type, args, t.line, t.column)

    def visit_type_var(self, t: TypeVarType) -> Type:
        repl = get_proper_type(self.variables.get(t.id, t))
        if isinstance(repl, Instance):
            inst = repl
            return Instance(inst.type, inst.args, line=inst.line, column=inst.column)
        else:
            return repl

    def visit_param_spec(self, t: ParamSpecType) -> Type:
        repl = get_proper_type(self.variables.get(t.id, t))
        if isinstance(repl, Instance):
            inst = repl
            # Return copy of instance with type erasure flag on.
            # TODO: what does prefix mean in this case?
            # TODO: why does this case even happen? Instances aren't plural.
            return Instance(inst.type, inst.args, line=inst.line, column=inst.column)
        elif isinstance(repl, ParamSpecType):
            return repl.copy_modified(flavor=t.flavor, prefix=t.prefix.copy_modified(
                arg_types=t.prefix.arg_types + repl.prefix.arg_types,
                arg_kinds=t.prefix.arg_kinds + repl.prefix.arg_kinds,
                arg_names=t.prefix.arg_names + repl.prefix.arg_names,
            ))
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
                return Parameters(t.prefix.arg_types + repl.arg_types,
                                  t.prefix.arg_kinds + repl.arg_kinds,
                                  t.prefix.arg_names + repl.arg_names,
                                  variables=[*t.prefix.variables, *repl.variables])
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

    def expand_unpack(self, t: UnpackType) -> Optional[Union[List[Type], Instance, AnyType]]:
        """May return either a list of types to unpack to, any, or a single
        variable length tuple. The latter may not be valid in all contexts.
        """
        proper_typ = get_proper_type(t.type)
        if isinstance(proper_typ, TypeVarTupleType):
            repl = get_proper_type(self.variables.get(proper_typ.id, t))
            if isinstance(repl, TupleType):
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
                raise NotImplementedError(f"Invalid type to expand: {repl}")
        else:
            raise NotImplementedError

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
                    type_guard=(t.type_guard.accept(self) if t.type_guard is not None else None))

        return t.copy_modified(arg_types=self.expand_types(t.arg_types),
                               ret_type=t.ret_type.accept(self),
                               type_guard=(t.type_guard.accept(self)
                                           if t.type_guard is not None else None))

    def visit_overloaded(self, t: Overloaded) -> Type:
        items: List[CallableType] = []
        for item in t.items:
            new_item = item.accept(self)
            assert isinstance(new_item, ProperType)
            assert isinstance(new_item, CallableType)
            items.append(new_item)
        return Overloaded(items)

    def visit_tuple_type(self, t: TupleType) -> Type:
        items = []
        for item in t.items:
            proper_item = get_proper_type(item)
            if isinstance(proper_item, UnpackType):
                unpacked_items = self.expand_unpack(proper_item)
                if unpacked_items is None:
                    # TODO: better error, something like tuple of unknown?
                    return UninhabitedType()
                elif isinstance(unpacked_items, Instance):
                    if len(t.items) == 1:
                        return unpacked_items
                    else:
                        assert False, "Invalid unpack of variable length tuple"
                elif isinstance(unpacked_items, AnyType):
                    return unpacked_items
                else:
                    items.extend(unpacked_items)
            else:
                items.append(proper_item.accept(self))

        return t.copy_modified(items=items)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        return t.copy_modified(item_types=self.expand_types(t.items.values()))

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

    def expand_types(self, types: Iterable[Type]) -> List[Type]:
        a: List[Type] = []
        for t in types:
            a.append(t.accept(self))
        return a
