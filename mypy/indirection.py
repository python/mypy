from typing import Dict, Iterable, List, Optional, Set
from abc import abstractmethod

from mypy.visitor import NodeVisitor
from mypy.types import SyntheticTypeVisitor
from mypy.nodes import MODULE_REF
import mypy.nodes as nodes
import mypy.types as types
from mypy.util import split_module_names


def extract_module_names(type_name: Optional[str]) -> List[str]:
    """Returns the module names of a fully qualified type name."""
    if type_name is not None:
        # Discard the first one, which is just the qualified name of the type
        possible_module_names = split_module_names(type_name)
        return possible_module_names[1:]
    else:
        return []


class TypeIndirectionVisitor(SyntheticTypeVisitor[Set[str]]):
    """Returns all module references within a particular type."""

    def __init__(self) -> None:
        self.cache = {}  # type: Dict[types.Type, Set[str]]

    def find_modules(self, typs: Iterable[types.Type]) -> Set[str]:
        return self._visit(*typs)

    def _visit(self, *typs: types.Type) -> Set[str]:
        output = set()  # type: Set[str]
        for typ in typs:
            if typ in self.cache:
                modules = self.cache[typ]
            else:
                modules = typ.accept(self)
                self.cache[typ] = set(modules)
            output.update(modules)
        return output

    def visit_unbound_type(self, t: types.UnboundType) -> Set[str]:
        return self._visit(*t.args)

    def visit_type_list(self, t: types.TypeList) -> Set[str]:
        return self._visit(*t.items)

    def visit_callable_argument(self, t: types.CallableArgument) -> Set[str]:
        return self._visit(t.typ)

    def visit_any(self, t: types.AnyType) -> Set[str]:
        return set()

    def visit_none_type(self, t: types.NoneTyp) -> Set[str]:
        return set()

    def visit_uninhabited_type(self, t: types.UninhabitedType) -> Set[str]:
        return set()

    def visit_erased_type(self, t: types.ErasedType) -> Set[str]:
        return set()

    def visit_deleted_type(self, t: types.DeletedType) -> Set[str]:
        return set()

    def visit_type_var(self, t: types.TypeVarType) -> Set[str]:
        return self._visit(*t.values) | self._visit(t.upper_bound)

    def visit_instance(self, t: types.Instance) -> Set[str]:
        out = self._visit(*t.args)
        if t.type is not None:
            out.update(split_module_names(t.type.module_name))
        return out

    def visit_callable_type(self, t: types.CallableType) -> Set[str]:
        out = self._visit(*t.arg_types) | self._visit(t.ret_type)
        if t.definition is not None:
            out.update(extract_module_names(t.definition.fullname()))
        return out

    def visit_overloaded(self, t: types.Overloaded) -> Set[str]:
        return self._visit(*t.items()) | self._visit(t.fallback)

    def visit_tuple_type(self, t: types.TupleType) -> Set[str]:
        return self._visit(*t.items) | self._visit(t.fallback)

    def visit_typeddict_type(self, t: types.TypedDictType) -> Set[str]:
        return self._visit(*t.items.values()) | self._visit(t.fallback)

    def visit_star_type(self, t: types.StarType) -> Set[str]:
        return set()

    def visit_union_type(self, t: types.UnionType) -> Set[str]:
        return self._visit(*t.items)

    def visit_partial_type(self, t: types.PartialType) -> Set[str]:
        return set()

    def visit_ellipsis_type(self, t: types.EllipsisType) -> Set[str]:
        return set()

    def visit_type_type(self, t: types.TypeType) -> Set[str]:
        return self._visit(t.item)

    def visit_forwardref_type(self, t: types.ForwardRef) -> Set[str]:
        if t.resolved:
            return self._visit(t.resolved)
        else:
            return set()
