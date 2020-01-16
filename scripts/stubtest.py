"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave
at runtime.
"""

import argparse
import importlib
import sys
from typing import Dict, Any, List, Iterator, NamedTuple, Optional, Mapping, Tuple
from typing_extensions import Type, Final
from collections import defaultdict
from functools import singledispatch

import mypy.build
import mypy.modulefinder
from mypy.modulefinder import FindModuleCache
from mypy.errors import CompileError
from mypy import nodes
from mypy.options import Options


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
def verify(stub: nodes.Node, runtime: Optional[Any]) -> Iterator[Error]:
    raise TypeError("unknown mypy node " + str(stub))


@verify.register(nodes.MypyFile)
def verify_mypyfile(stub: nodes.MypyFile, runtime: Optional[Any]) -> Iterator[Error]:
    if runtime is None:
        yield Error("not_in_runtime")
    elif runtime["type"] != "file":
        yield Error("inconsistent")
    else:
        stub_children = defaultdict(
            lambda: None, stub.names
        )  # type: Mapping[str, Optional[nodes.SymbolTableNode]]
        runtime_children = defaultdict(lambda: None, runtime["names"])

        # TODO: I would rather not filter public children here.
        #       For example, what if the checkersurfaces an inconsistency
        #       in the typing of a private child
        public_nodes = {
            name: (stub_children[name], runtime_children[name])
            for name in set(stub_children) | set(runtime_children)
            if not name.startswith("_")
            and (stub_children[name] is None or stub_children[name].module_public)  # type: ignore
        }

        for node, (stub_child, runtime_child) in public_nodes.items():
            stub_child = getattr(stub_child, "node", None)
            yield from verify(stub_child, runtime_child)


@verify.register(nodes.TypeInfo)
def verify_typeinfo(stub: nodes.TypeInfo, runtime: Optional[Any]) -> Iterator[Error]:
    if not runtime:
        yield Error("not_in_runtime")
    elif runtime["type"] != "class":
        yield Error("inconsistent")
    else:
        for attr, attr_node in stub.names.items():
            subdump = runtime["attributes"].get(attr, None)
            yield from verify(attr_node.node, subdump)


@verify.register(nodes.FuncItem)
def verify_funcitem(stub: nodes.FuncItem, runtime: Optional[Any]) -> Iterator[Error]:
    if not runtime:
        yield Error("not_in_runtime")
    elif "type" not in runtime or runtime["type"] not in ("function", "callable"):
        yield Error("inconsistent")
    # TODO check arguments and return value


@verify.register(type(None))
def verify_none(stub: None, runtime: Optional[Any]) -> Iterator[Error]:
    if runtime is None:
        yield Error("not_in_stub")
    else:
        yield Error("not_in_stub")


@verify.register(nodes.Var)
def verify_var(node: nodes.Var, module_node: Optional[Any]) -> Iterator[Error]:
    if False:
        yield None
    # Need to check if types are inconsistent.
    # if 'type' not in dump or dump['type'] != node.node.type:
    #    import ipdb; ipdb.set_trace()
    #    yield name, 'inconsistent', node.node.line, shed_type, module_type


@verify.register(nodes.OverloadedFuncDef)
def verify_overloadedfuncdef(
    node: nodes.OverloadedFuncDef, module_node: Optional[Any]
) -> Iterator[Error]:
    # Should check types of the union of the overloaded types.
    if False:
        yield None


@verify.register(nodes.TypeVarExpr)
def verify_typevarexpr(
    node: nodes.TypeVarExpr, module_node: Optional[Any]
) -> Iterator[Error]:
    if False:
        yield None


@verify.register(nodes.Decorator)
def verify_decorator(
    node: nodes.Decorator, module_node: Optional[Any]
) -> Iterator[Error]:
    if False:
        yield None


@verify.register(nodes.TypeAlias)
def verify_typealias(
    node: nodes.TypeAlias, module_node: Optional[Any]
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
