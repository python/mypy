"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave
at runtime.
"""

import argparse
import importlib
import sys
import types
from collections import defaultdict
from functools import singledispatch
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from typing_extensions import Final, Type

import mypy.build
import mypy.modulefinder
from mypy import nodes
from mypy.errors import CompileError
from mypy.modulefinder import FindModuleCache
from mypy.options import Options


class Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING = Missing()

T = TypeVar("T")
MaybeMissing = Union[T, Missing]


class Error(str):
    pass


def test_module(
    module_name: str, options: Options, find_module_cache: FindModuleCache
) -> Iterator[Error]:
    stubs = {
        mod: stub
        for mod, stub in build_stubs(module_name, options, find_module_cache).items()
        if (mod == module_name or mod.startswith(module_name + "."))
    }

    for mod, stub in stubs.items():
        runtime = importlib.import_module(mod)
        yield from verify(stub, runtime)


@singledispatch
def verify(stub: nodes.Node, runtime: MaybeMissing[Any]) -> Iterator[Error]:
    raise TypeError("unknown mypy node " + str(stub))


@verify.register(nodes.MypyFile)
def verify_mypyfile(
    stub: nodes.MypyFile, runtime: MaybeMissing[types.ModuleType]
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        yield Error("not_in_runtime")
        return
    if not isinstance(runtime, types.ModuleType):
        yield Error("type_mismatch")
        return

    # Check all things in the stub
    to_check = set(m for m, o in stub.names.items() if o.module_public)
    # Check all things declared in module's __all__
    to_check.update(getattr(runtime, "__all__", []))
    to_check.difference_update(
        {"__file__", "__doc__", "__name__", "__builtins__", "__package__"}
    )
    # We currently don't check things in the module that aren't in the stub, other than things that
    # are in __all__ to avoid false positives.

    for entry in to_check:
        yield from verify(
            getattr(stub.names.get(entry, MISSING), "node", MISSING),
            getattr(runtime, entry, MISSING),
        )


@verify.register(nodes.TypeInfo)
def verify_typeinfo(
    stub: nodes.TypeInfo, runtime: MaybeMissing[Any]
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        yield Error("not_in_runtime")
        return
    if not runtime:
        yield Error("not_in_runtime")
    elif runtime["type"] != "class":
        yield Error("inconsistent")
    else:
        for attr, attr_node in stub.names.items():
            subdump = runtime["attributes"].get(attr, None)
            yield from verify(attr_node.node, subdump)


@verify.register(nodes.FuncItem)
def verify_funcitem(
    stub: nodes.FuncItem, runtime: MaybeMissing[Any]
) -> Iterator[Error]:
    if not runtime:
        yield Error("not_in_runtime")
    elif "type" not in runtime or runtime["type"] not in ("function", "callable"):
        yield Error("inconsistent")
    # TODO check arguments and return value


@verify.register(type(None))
def verify_none(stub: None, runtime: MaybeMissing[Any]) -> Iterator[Error]:
    if runtime is None:
        yield Error("not_in_stub")
    else:
        yield Error("not_in_stub")


@verify.register(nodes.Var)
def verify_var(node: nodes.Var, module_node: MaybeMissing[Any]) -> Iterator[Error]:
    if False:
        yield None
    # Need to check if types are inconsistent.
    # if 'type' not in dump or dump['type'] != node.node.type:
    #    import ipdb; ipdb.set_trace()
    #    yield name, 'inconsistent', node.node.line, shed_type, module_type


@verify.register(nodes.OverloadedFuncDef)
def verify_overloadedfuncdef(
    node: nodes.OverloadedFuncDef, module_node: MaybeMissing[Any]
) -> Iterator[Error]:
    # Should check types of the union of the overloaded types.
    if False:
        yield None


@verify.register(nodes.TypeVarExpr)
def verify_typevarexpr(
    node: nodes.TypeVarExpr, module_node: MaybeMissing[Any]
) -> Iterator[Error]:
    if False:
        yield None


@verify.register(nodes.Decorator)
def verify_decorator(
    node: nodes.Decorator, module_node: MaybeMissing[Any]
) -> Iterator[Error]:
    if False:
        yield None


@verify.register(nodes.TypeAlias)
def verify_typealias(
    node: nodes.TypeAlias, module_node: MaybeMissing[Any]
) -> Iterator[Error]:
    if False:
        yield None


def build_stubs(
    module_name: str, options: Options, find_module_cache: FindModuleCache
) -> Dict[str, nodes.MypyFile]:
    sources = find_module_cache.find_modules_recursive(module_name)

    res = mypy.build.build(sources=sources, options=options)
    if res.errors:
        raise CompileError

    return res.files


def main() -> Iterator[Error]:
    parser = argparse.ArgumentParser()
    parser.add_argument("modules", nargs="+", help="Modules to test")
    parser.add_argument(
        "--custom-typeshed-dir", metavar="DIR", help="Use the custom typeshed in DIR"
    )
    args = parser.parse_args()

    options = Options()
    options.incremental = False
    options.custom_typeshed_dir = args.custom_typeshed_dir

    data_dir = mypy.build.default_data_dir()
    search_path = mypy.modulefinder.compute_search_paths([], options, data_dir)
    find_module_cache = FindModuleCache(search_path)

    for module in args.modules:
        for error in test_module(module, options, find_module_cache):
            yield error


if __name__ == "__main__":
    for err in main():
        print(err)
