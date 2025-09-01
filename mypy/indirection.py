from __future__ import annotations

from collections.abc import Iterable

import mypy.types as types
from mypy.types import TypeVisitor
from mypy.util import split_module_names


def extract_module_names(type_name: str | None) -> list[str]:
    """Returns the module names of a fully qualified type name."""
    if type_name is not None:
        # Discard the first one, which is just the qualified name of the type
        possible_module_names = split_module_names(type_name)
        return possible_module_names[1:]
    else:
        return []


class TypeIndirectionVisitor(TypeVisitor[None]):
    """Returns all module references within a particular type."""

    def __init__(self) -> None:
        # Module references are collected here
        self.modules: set[str] = set()
        # User to avoid infinite recursion with recursive type aliases
        self.seen_aliases: set[types.TypeAliasType] = set()
        # Used to avoid redundant work
        self.seen_fullnames: set[str] = set()

    def find_modules(self, typs: Iterable[types.Type]) -> set[str]:
        self.modules = set()
        self.seen_fullnames = set()
        self.seen_aliases = set()
        for typ in typs:
            self._visit(typ)
        return self.modules

    def _visit(self, typ: types.Type) -> None:
        if isinstance(typ, types.TypeAliasType):
            # Avoid infinite recursion for recursive type aliases.
            if typ not in self.seen_aliases:
                self.seen_aliases.add(typ)
        typ.accept(self)

    def _visit_type_tuple(self, typs: tuple[types.Type, ...]) -> None:
        # Micro-optimization: Specialized version of _visit for lists
        for typ in typs:
            if isinstance(typ, types.TypeAliasType):
                # Avoid infinite recursion for recursive type aliases.
                if typ in self.seen_aliases:
                    continue
                self.seen_aliases.add(typ)
            typ.accept(self)

    def _visit_type_list(self, typs: list[types.Type]) -> None:
        # Micro-optimization: Specialized version of _visit for tuples
        for typ in typs:
            if isinstance(typ, types.TypeAliasType):
                # Avoid infinite recursion for recursive type aliases.
                if typ in self.seen_aliases:
                    continue
                self.seen_aliases.add(typ)
            typ.accept(self)

    def _visit_module_name(self, module_name: str) -> None:
        if module_name not in self.modules:
            self.modules.update(split_module_names(module_name))

    def visit_unbound_type(self, t: types.UnboundType) -> None:
        self._visit_type_tuple(t.args)

    def visit_any(self, t: types.AnyType) -> None:
        pass

    def visit_none_type(self, t: types.NoneType) -> None:
        pass

    def visit_uninhabited_type(self, t: types.UninhabitedType) -> None:
        pass

    def visit_erased_type(self, t: types.ErasedType) -> None:
        pass

    def visit_deleted_type(self, t: types.DeletedType) -> None:
        pass

    def visit_type_var(self, t: types.TypeVarType) -> None:
        self._visit_type_list(t.values)
        self._visit(t.upper_bound)
        self._visit(t.default)

    def visit_param_spec(self, t: types.ParamSpecType) -> None:
        self._visit(t.upper_bound)
        self._visit(t.default)

    def visit_type_var_tuple(self, t: types.TypeVarTupleType) -> None:
        self._visit(t.upper_bound)
        self._visit(t.default)

    def visit_unpack_type(self, t: types.UnpackType) -> None:
        t.type.accept(self)

    def visit_parameters(self, t: types.Parameters) -> None:
        self._visit_type_list(t.arg_types)

    def visit_instance(self, t: types.Instance) -> None:
        self._visit_type_tuple(t.args)
        if t.type:
            # Uses of a class depend on everything in the MRO,
            # as changes to classes in the MRO can add types to methods,
            # change property types, change the MRO itself, etc.
            for s in t.type.mro:
                self._visit_module_name(s.module_name)
            if t.type.metaclass_type is not None:
                self._visit_module_name(t.type.metaclass_type.type.module_name)

    def visit_callable_type(self, t: types.CallableType) -> None:
        self._visit_type_list(t.arg_types)
        self._visit(t.ret_type)
        if t.definition is not None:
            fullname = t.definition.fullname
            if fullname not in self.seen_fullnames:
                self.modules.update(extract_module_names(t.definition.fullname))
                self.seen_fullnames.add(fullname)

    def visit_overloaded(self, t: types.Overloaded) -> None:
        self._visit_type_list(list(t.items))
        self._visit(t.fallback)

    def visit_tuple_type(self, t: types.TupleType) -> None:
        self._visit_type_list(t.items)
        self._visit(t.partial_fallback)

    def visit_typeddict_type(self, t: types.TypedDictType) -> None:
        self._visit_type_list(list(t.items.values()))
        self._visit(t.fallback)

    def visit_literal_type(self, t: types.LiteralType) -> None:
        self._visit(t.fallback)

    def visit_union_type(self, t: types.UnionType) -> None:
        self._visit_type_list(t.items)

    def visit_partial_type(self, t: types.PartialType) -> None:
        pass

    def visit_type_type(self, t: types.TypeType) -> None:
        self._visit(t.item)

    def visit_type_alias_type(self, t: types.TypeAliasType) -> None:
        self._visit(types.get_proper_type(t))
