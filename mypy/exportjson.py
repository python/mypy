"""Tool to convert mypy cache file to a JSON format (print to stdout).

Usage:
   python -m mypy.exportjson .mypy_cache/.../my_module.data.ff

The idea is to make caches introspectable once we've switched to a binary
cache format and removed support for the older JSON cache format.

This is primarily to support existing use cases that need to inspect
cache files, and to support debugging mypy caching issues. This means that
this doesn't necessarily need to be kept 1:1 up to date with changes in the
binary cache format (to simplify maintenance -- we don't want this to slow
down mypy development).
"""

import argparse
import json
from typing import Any, TypeAlias as _TypeAlias

from mypy.types import (
    Type, get_proper_type, Instance, AnyType, UnionType, TupleType, CallableType,
    Overloaded, TypeVarType, TypeAliasType, LiteralType
)
from mypy.nodes import (
    MypyFile, SymbolTable, SymbolTableNode, node_kinds, SymbolNode, FuncDef, TypeInfo,
    TypeAlias, TypeVarExpr, Var, OverloadedFuncDef, get_flags, FUNCDEF_FLAGS,
    DataclassTransformSpec, FUNCBASE_FLAGS, OverloadPart, Decorator, VAR_FLAGS,
    ParamSpecExpr, TypeVarTupleExpr
)
from librt.internal import Buffer

JsonDict: _TypeAlias = dict[str, Any]


def convert_binary_cache_to_json(data: bytes) -> JsonDict:
    tree = MypyFile.read(Buffer(data))
    return convert_mypy_file_to_json(tree)


def convert_mypy_file_to_json(self: MypyFile) -> JsonDict:
    return {
        ".class": "MypyFile",
        "_fullname": self._fullname,
        "names": convert_symbol_table(self.names, self._fullname),
        "is_stub": self.is_stub,
        "path": self.path,
        "is_partial_stub_package": self.is_partial_stub_package,
        "future_import_flags": sorted(self.future_import_flags),
    }


def convert_symbol_table(self: SymbolTable, fullname: str) -> JsonDict:
    data: JsonDict = {".class": "SymbolTable"}
    for key, value in self.items():
        # Skip __builtins__: it's a reference to the builtins
        # module that gets added to every module by
        # SemanticAnalyzerPass2.visit_file(), but it shouldn't be
        # accessed by users of the module.
        if key == "__builtins__" or value.no_serialize:
            continue
        data[key] = convert_symbol_table_node(value, fullname, key)
    return data


def convert_symbol_table_node(self: SymbolTableNode, prefix: str | None, name: str) -> JsonDict:
    data: JsonDict = {".class": "SymbolTableNode", "kind": node_kinds[self.kind]}
    if self.module_hidden:
        data["module_hidden"] = True
    if not self.module_public:
        data["module_public"] = False
    if self.implicit:
        data["implicit"] = True
    if self.plugin_generated:
        data["plugin_generated"] = True
    if self.cross_ref:
        data["cross_ref"] = self.cross_ref
    elif self.node is not None:
        data["node"] = convert_symbol_node(self.node)
    return data


def convert_symbol_node(self: SymbolNode) -> JsonDict:
    if isinstance(self, FuncDef):
        return convert_func_def(self)
    elif isinstance(self, OverloadedFuncDef):
        return convert_overloaded_func_def(self)
    elif isinstance(self, Decorator):
        return convert_decorator(self)
    elif isinstance(self, Var):
        return convert_var(self)
    elif isinstance(self, TypeInfo):
        return convert_type_info(self)
    elif isinstance(self, TypeAlias):
        return convert_type_alias(self)
    elif isinstance(self, TypeVarExpr):
        return convert_type_var_expr(self)
    elif isinstance(self, ParamSpecExpr):
        return convert_param_spec_expr(self)
    elif isinstance(self, TypeVarTupleExpr):
        return convert_type_var_tuple_expr(self)
    assert False, type(self)


def convert_func_def(self: FuncDef) -> JsonDict:
    return {
        ".class": "FuncDef",
        "name": self._name,
        "fullname": self._fullname,
        "arg_names": self.arg_names,
        "arg_kinds": [int(x.value) for x in self.arg_kinds],
        "type": None if self.type is None else convert_type(self.type),
        "flags": get_flags(self, FUNCDEF_FLAGS),
        "abstract_status": self.abstract_status,
        # TODO: Do we need expanded, original_def?
        "dataclass_transform_spec": (
            None
            if self.dataclass_transform_spec is None
            else convert_dataclass_transform_spec(self.dataclass_transform_spec)
        ),
        "deprecated": self.deprecated,
        "original_first_arg": self.original_first_arg,
    }


def convert_dataclass_transform_spec(self: DataclassTransformSpec) -> JsonDict:
    return {
        "eq_default": self.eq_default,
        "order_default": self.order_default,
        "kw_only_default": self.kw_only_default,
        "frozen_default": self.frozen_default,
        "field_specifiers": list(self.field_specifiers),
    }


def convert_overloaded_func_def(self: OverloadedFuncDef) -> JsonDict:
    return {
        ".class": "OverloadedFuncDef",
        "items": [convert_overload_part(i) for i in self.items],
        "type": None if self.type is None else convert_type(self.type),
        "fullname": self._fullname,
        "impl": None if self.impl is None else convert_overload_part(self.impl),
        "flags": get_flags(self, FUNCBASE_FLAGS),
        "deprecated": self.deprecated,
        "setter_index": self.setter_index,
    }


def convert_overload_part(self: OverloadPart) -> JsonDict:
    if isinstance(self, FuncDef):
        return convert_func_def(self)
    else:
        return convert_decorator(self)


def convert_decorator(self: Decorator) -> JsonDict:
    return {
        ".class": "Decorator",
        "func": convert_func_def(self.func),
        "var": convert_var(self.var),
        "is_overload": self.is_overload,
    }


def convert_var(self: Var) -> JsonDict:
    data: JsonDict = {
        ".class": "Var",
        "name": self._name,
        "fullname": self._fullname,
        "type": None if self.type is None else convert_type(self.type),
        "setter_type": None if self.setter_type is None else convert_type(self.setter_type),
        "flags": get_flags(self, VAR_FLAGS),
    }
    if self.final_value is not None:
        data["final_value"] = self.final_value
    return data


def convert_type_info(self: TypeInfo) -> JsonDict:
    return {}


def convert_type_alias(self: TypeAlias) -> JsonDict:
    data: JsonDict = {
        ".class": "TypeAlias",
        "fullname": self._fullname,
        "module": self.module,
        "target": convert_type(self.target),
        "alias_tvars": [convert_type(v) for v in self.alias_tvars],
        "no_args": self.no_args,
        "normalized": self.normalized,
        "python_3_12_type_alias": self.python_3_12_type_alias,
    }
    return data


def convert_type_var_expr(self: TypeVarExpr) -> JsonDict:
    return {
        ".class": "TypeVarExpr",
        "name": self._name,
        "fullname": self._fullname,
        "values": [convert_type(t) for t in self.values],
        "upper_bound": convert_type(self.upper_bound),
        "default": convert_type(self.default),
        "variance": self.variance,
    }


def convert_param_spec_expr(self: ParamSpecExpr) -> JsonDict:
    return {
        ".class": "ParamSpecExpr",
        "name": self._name,
        "fullname": self._fullname,
        "upper_bound": convert_type(self.upper_bound),
        "default": convert_type(self.default),
        "variance": self.variance,
    }


def convert_type_var_tuple_expr(self: TypeVarTupleExpr) -> JsonDict:
    return {
        ".class": "TypeVarTupleExpr",
        "name": self._name,
        "fullname": self._fullname,
        "upper_bound": convert_type(self.upper_bound),
        "tuple_fallback": convert_type(self.tuple_fallback),
        "default": convert_type(self.default),
        "variance": self.variance,
    }


def convert_type(typ: Type) -> JsonDict:
    if type(typ) is TypeAliasType:
        return convert_type_alias_type(typ)
    typ = get_proper_type(typ)
    if isinstance(typ, Instance):
        return convert_instance(typ)
    elif isinstance(typ, AnyType):
        return convert_any_type(typ)
    elif isinstance(typ, UnionType):
        return convert_union_type(typ)
    elif isinstance(typ, TupleType):
        return convert_tuple_type(typ)
    elif isinstance(typ, CallableType):
        return convert_callable_type(typ)
    elif isinstance(typ, Overloaded):
        return convert_overloaded(typ)
    elif isinstance(typ, LiteralType):
        return convert_literal_type(typ)
    elif isinstance(typ, TypeVarType):
        return convert_type_var_type(typ)
    assert False, type(typ)


def convert_instance(self: Instance) -> JsonDict:
    data: JsonDict = {
        ".class": "Instance",
        "type_ref": self.type_ref,
        "args": [convert_type(arg) for arg in self.args],
    }
    return data


def convert_type_alias_type(self: TypeAliasType) -> JsonDict:
    data: JsonDict = {
        ".class": "TypeAliasType",
        "type_ref": self.type_ref,
        "args": [convert_type(arg) for arg in self.args],
    }
    return data


def convert_any_type(self: AnyType) -> JsonDict:
    return {
        ".class": "AnyType",
        "type_of_any": self.type_of_any,
        "source_any": convert_type(self.source_any) if self.source_any is not None else None,
        "missing_import_name": self.missing_import_name,
    }


def convert_union_type(self: UnionType) -> JsonDict:
    return {
        ".class": "UnionType",
        "items": [convert_type(t) for t in self.items],
        "uses_pep604_syntax": self.uses_pep604_syntax,
    }


def convert_tuple_type(self: TupleType) -> JsonDict:
    return {
        ".class": "TupleType",
        "items": [convert_type(t) for t in self.items],
        "partial_fallback": convert_type(self.partial_fallback),
        "implicit": self.implicit,
    }


def convert_literal_type(self: LiteralType) -> JsonDict:
    return {
        ".class": "LiteralType",
        "value": self.value,
        "fallback": convert_type(self.fallback),
    }


def convert_type_var_type(self: TypeVarType) -> JsonDict:
    return {}


def convert_callable_type(self: CallableType) -> JsonDict:
    return {
        ".class": "CallableType",
        "arg_types": [convert_type(t) for t in self.arg_types],
        "arg_kinds": [int(x.value) for x in self.arg_kinds],
        "arg_names": self.arg_names,
        "ret_type": convert_type(self.ret_type),
        "fallback": convert_type(self.fallback),
        "name": self.name,
        # We don't serialize the definition (only used for error messages).
        "variables": [convert_type(v) for v in self.variables],
        "is_ellipsis_args": self.is_ellipsis_args,
        "implicit": self.implicit,
        "is_bound": self.is_bound,
        "type_guard": convert_type(self.type_guard) if self.type_guard is not None else None,
        "type_is": convert_type(self.type_is) if self.type_is is not None else None,
        "from_concatenate": self.from_concatenate,
        "imprecise_arg_kinds": self.imprecise_arg_kinds,
        "unpack_kwargs": self.unpack_kwargs,
    }


def convert_overloaded(self: Overloaded) -> JsonDict:
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="+")
    args = parser.parse_args()
    fnams: list[str] = args.path
    for fnam in fnams:
        with open(fnam, "rb") as f:
            data = f.read()
        json_data = convert_binary_cache_to_json(data)
        new_fnam = fnam + ".json"
        with open(new_fnam, "w") as f:
            json.dump(json_data, f)
        print(f"{fnam} -> {new_fnam}")


if __name__ == "__main__":
    main()
