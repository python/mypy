from __future__ import annotations

from collections.abc import Container
from typing import Callable, cast

from mypy.nodes import ARG_STAR, ARG_STAR2
from mypy.types import (
    AnyType,
    CallableType,
    DeletedType,
    ErasedType,
    Instance,
    LiteralType,
    NoneType,
    Overloaded,
    Parameters,
    ParamSpecType,
    PartialType,
    ProperType,
    TupleType,
    Type,
    TypeAliasType,
    TypedDictType,
    TypeOfAny,
    TypeTranslator,
    TypeType,
    TypeVarId,
    TypeVarTupleType,
    TypeVarType,
    TypeVisitor,
    UnboundType,
    UninhabitedType,
    UnionType,
    UnpackType,
    get_proper_type,
    get_proper_types,
)
from mypy.typevartuples import erased_vars


def erase_type(typ: Type) -> ProperType:
    """Erase any type variables from a type.

    Also replace tuple types with the corresponding concrete types.

    Examples:
      A -> A
      B[X] -> B[Any]
      Tuple[A, B] -> tuple
      Callable[[A1, A2, ...], R] -> Callable[..., Any]
      Type[X] -> Type[Any]
    """
    typ = get_proper_type(typ)
    return typ.accept(EraseTypeVisitor())


class EraseTypeVisitor(TypeVisitor[ProperType]):
    def visit_unbound_type(self, t: UnboundType) -> ProperType:
        # TODO: replace with an assert after UnboundType can't leak from semantic analysis.
        return AnyType(TypeOfAny.from_error)

    def visit_any(self, t: AnyType) -> ProperType:
        return t

    def visit_none_type(self, t: NoneType) -> ProperType:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> ProperType:
        return t

    def visit_erased_type(self, t: ErasedType) -> ProperType:
        return t

    def visit_partial_type(self, t: PartialType) -> ProperType:
        # Should not get here.
        raise RuntimeError("Cannot erase partial types")

    def visit_deleted_type(self, t: DeletedType) -> ProperType:
        return t

    def visit_instance(self, t: Instance) -> ProperType:
        args = erased_vars(t.type.defn.type_vars, TypeOfAny.special_form)
        return Instance(t.type, args, t.line)

    def visit_type_var(self, t: TypeVarType) -> ProperType:
        return AnyType(TypeOfAny.special_form)

    def visit_param_spec(self, t: ParamSpecType) -> ProperType:
        return AnyType(TypeOfAny.special_form)

    def visit_parameters(self, t: Parameters) -> ProperType:
        raise RuntimeError("Parameters should have been bound to a class")

    def visit_type_var_tuple(self, t: TypeVarTupleType) -> ProperType:
        # Likely, we can never get here because of aggressive erasure of types that
        # can contain this, but better still return a valid replacement.
        return t.tuple_fallback.copy_modified(args=[AnyType(TypeOfAny.special_form)])

    def visit_unpack_type(self, t: UnpackType) -> ProperType:
        return AnyType(TypeOfAny.special_form)

    def visit_callable_type(self, t: CallableType) -> ProperType:
        # We must preserve the fallback type for overload resolution to work.
        any_type = AnyType(TypeOfAny.special_form)
        return CallableType(
            arg_types=[any_type, any_type],
            arg_kinds=[ARG_STAR, ARG_STAR2],
            arg_names=[None, None],
            ret_type=any_type,
            fallback=t.fallback,
            is_ellipsis_args=True,
            implicit=True,
        )

    def visit_overloaded(self, t: Overloaded) -> ProperType:
        return t.fallback.accept(self)

    def visit_tuple_type(self, t: TupleType) -> ProperType:
        return t.partial_fallback.accept(self)

    def visit_typeddict_type(self, t: TypedDictType) -> ProperType:
        return t.fallback.accept(self)

    def visit_literal_type(self, t: LiteralType) -> ProperType:
        # The fallback for literal types should always be either
        # something like int or str, or an enum class -- types that
        # don't contain any TypeVars. So there's no need to visit it.
        return t

    def visit_union_type(self, t: UnionType) -> ProperType:
        erased_items = [erase_type(item) for item in t.items]
        from mypy.typeops import make_simplified_union

        return make_simplified_union(erased_items)

    def visit_type_type(self, t: TypeType) -> ProperType:
        return TypeType.make_normalized(t.item.accept(self), line=t.line)

    def visit_type_alias_type(self, t: TypeAliasType) -> ProperType:
        raise RuntimeError("Type aliases should be expanded before accepting this visitor")


def erase_typevars(t: Type, ids_to_erase: Container[TypeVarId] | None = None) -> Type:
    """Replace all type variables in a type with any,
    or just the ones in the provided collection.
    """

    if ids_to_erase is None:
        return t.accept(TypeVarEraser(None, AnyType(TypeOfAny.special_form)))

    def erase_id(id: TypeVarId) -> bool:
        return id in ids_to_erase

    return t.accept(TypeVarEraser(erase_id, AnyType(TypeOfAny.special_form)))


def erase_meta_id(id: TypeVarId) -> bool:
    return id.is_meta_var()


def replace_meta_vars(t: Type, target_type: Type) -> Type:
    """Replace unification variables in a type with the target type."""
    return t.accept(TypeVarEraser(erase_meta_id, target_type))


class TypeVarEraser(TypeTranslator):
    """Implementation of type erasure"""

    def __init__(self, erase_id: Callable[[TypeVarId], bool] | None, replacement: Type) -> None:
        super().__init__()
        self.erase_id = erase_id
        self.replacement = replacement

    def visit_type_var(self, t: TypeVarType) -> Type:
        if self.erase_id is None or self.erase_id(t.id):
            return self.replacement
        return t

    # TODO: below two methods duplicate some logic with expand_type().
    # In fact, we may want to refactor this whole visitor to use expand_type().
    def visit_instance(self, t: Instance) -> Type:
        result = super().visit_instance(t)
        assert isinstance(result, ProperType) and isinstance(result, Instance)
        if t.type.fullname == "builtins.tuple":
            # Normalize Tuple[*Tuple[X, ...], ...] -> Tuple[X, ...]
            arg = result.args[0]
            if isinstance(arg, UnpackType):
                unpacked = get_proper_type(arg.type)
                if isinstance(unpacked, Instance):
                    assert unpacked.type.fullname == "builtins.tuple"
                    return unpacked
        return result

    def visit_tuple_type(self, t: TupleType) -> Type:
        result = super().visit_tuple_type(t)
        assert isinstance(result, ProperType) and isinstance(result, TupleType)
        if len(result.items) == 1:
            # Normalize Tuple[*Tuple[X, ...]] -> Tuple[X, ...]
            item = result.items[0]
            if isinstance(item, UnpackType):
                unpacked = get_proper_type(item.type)
                if isinstance(unpacked, Instance):
                    assert unpacked.type.fullname == "builtins.tuple"
                    if result.partial_fallback.type.fullname != "builtins.tuple":
                        # If it is a subtype (like named tuple) we need to preserve it,
                        # this essentially mimics the logic in tuple_fallback().
                        return result.partial_fallback.accept(self)
                    return unpacked
        return result

    def visit_callable_type(self, t: CallableType) -> Type:
        result = super().visit_callable_type(t)
        assert isinstance(result, ProperType) and isinstance(result, CallableType)
        # Usually this is done in semanal_typeargs.py, but erasure can create
        # a non-normal callable from normal one.
        result.normalize_trivial_unpack()
        return result

    def visit_type_var_tuple(self, t: TypeVarTupleType) -> Type:
        if self.erase_id is None or self.erase_id(t.id):
            return t.tuple_fallback.copy_modified(args=[self.replacement])
        return t

    def visit_param_spec(self, t: ParamSpecType) -> Type:
        if self.erase_id is None or self.erase_id(t.id):
            return self.replacement
        return t

    def visit_type_alias_type(self, t: TypeAliasType) -> Type:
        # Type alias target can't contain bound type variables (not bound by the type
        # alias itself), so it is safe to just erase the arguments.
        return t.copy_modified(args=[a.accept(self) for a in t.args])


def remove_instance_last_known_values(t: Type) -> Type:
    return t.accept(LastKnownValueEraser())


class LastKnownValueEraser(TypeTranslator):
    """Removes the Literal[...] type that may be associated with any
    Instance types."""

    def visit_instance(self, t: Instance) -> Type:
        if not t.last_known_value and not t.args:
            return t
        return t.copy_modified(args=[a.accept(self) for a in t.args], last_known_value=None)

    def visit_type_alias_type(self, t: TypeAliasType) -> Type:
        # Type aliases can't contain literal values, because they are
        # always constructed as explicit types.
        return t

    def visit_union_type(self, t: UnionType) -> Type:
        new = cast(UnionType, super().visit_union_type(t))
        # Erasure can result in many duplicate items; merge them.
        # Call make_simplified_union only on lists of instance types
        # that all have the same fullname, to avoid simplifying too
        # much.
        instances = [item for item in new.items if isinstance(get_proper_type(item), Instance)]
        # Avoid merge in simple cases such as optional types.
        if len(instances) > 1:
            instances_by_name: dict[str, list[Instance]] = {}
            p_new_items = get_proper_types(new.items)
            for p_item in p_new_items:
                if isinstance(p_item, Instance) and not p_item.args:
                    instances_by_name.setdefault(p_item.type.fullname, []).append(p_item)
            merged: list[Type] = []
            for item in new.items:
                orig_item = item
                item = get_proper_type(item)
                if isinstance(item, Instance) and not item.args:
                    types = instances_by_name.get(item.type.fullname)
                    if types is not None:
                        if len(types) == 1:
                            merged.append(item)
                        else:
                            from mypy.typeops import make_simplified_union

                            merged.append(make_simplified_union(types))
                            del instances_by_name[item.type.fullname]
                else:
                    merged.append(orig_item)
            return UnionType.make_union(merged)
        return new
