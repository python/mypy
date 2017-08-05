from typing import Optional, Container, Callable

from mypy.types import (
    Type, TypeVisitor, UnboundType, AnyType, NoneTyp, TypeVarId, Instance, TypeVarType,
    CallableType, TupleType, TypedDictType, UnionType, Overloaded, ErasedType, PartialType,
    DeletedType, TypeTranslator, TypeList, UninhabitedType, TypeType, TypeOfAny
)
from mypy import experiments


def erase_type(typ: Type) -> Type:
    """Erase any type variables from a type.

    Also replace tuple types with the corresponding concrete types. Replace
    callable types with empty callable types.

    Examples:
      A -> A
      B[X] -> B[Any]
      Tuple[A, B] -> tuple
      Callable[...] -> Callable[[], None]
      Type[X] -> Type[Any]
    """

    return typ.accept(EraseTypeVisitor())


class EraseTypeVisitor(TypeVisitor[Type]):

    def visit_unbound_type(self, t: UnboundType) -> Type:
        assert False, 'Not supported'

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_erased_type(self, t: ErasedType) -> Type:
        # Should not get here.
        raise RuntimeError()

    def visit_partial_type(self, t: PartialType) -> Type:
        # Should not get here.
        raise RuntimeError()

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_instance(self, t: Instance) -> Type:
        return Instance(t.type, [AnyType(TypeOfAny.special_form)] * len(t.args), t.line)

    def visit_type_var(self, t: TypeVarType) -> Type:
        return AnyType(TypeOfAny.special_form)

    def visit_callable_type(self, t: CallableType) -> Type:
        # We must preserve the fallback type for overload resolution to work.
        ret_type = NoneTyp()  # type: Type
        return CallableType([], [], [], ret_type, t.fallback)

    def visit_overloaded(self, t: Overloaded) -> Type:
        return t.items()[0].accept(self)

    def visit_tuple_type(self, t: TupleType) -> Type:
        return t.fallback.accept(self)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        return t.fallback.accept(self)

    def visit_union_type(self, t: UnionType) -> Type:
        erased_items = [erase_type(item) for item in t.items]
        return UnionType.make_simplified_union(erased_items)

    def visit_type_type(self, t: TypeType) -> Type:
        return TypeType.make_normalized(t.item.accept(self), line=t.line)


def erase_typevars(t: Type, ids_to_erase: Optional[Container[TypeVarId]] = None) -> Type:
    """Replace all type variables in a type with any,
    or just the ones in the provided collection.
    """
    def erase_id(id: TypeVarId) -> bool:
        if ids_to_erase is None:
            return True
        return id in ids_to_erase
    return t.accept(TypeVarEraser(erase_id, AnyType(TypeOfAny.special_form)))


def replace_meta_vars(t: Type, target_type: Type) -> Type:
    """Replace unification variables in a type with the target type."""
    return t.accept(TypeVarEraser(lambda id: id.is_meta_var(), target_type))


class TypeVarEraser(TypeTranslator):
    """Implementation of type erasure"""

    def __init__(self, erase_id: Callable[[TypeVarId], bool], replacement: Type) -> None:
        self.erase_id = erase_id
        self.replacement = replacement

    def visit_type_var(self, t: TypeVarType) -> Type:
        if self.erase_id(t.id):
            return self.replacement
        return t
