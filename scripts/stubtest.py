"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave
at runtime.
"""

import importlib
import sys
from typing import Dict, Any, List, Iterator, NamedTuple, Optional, Mapping, Tuple
from typing_extensions import Type, Final
from collections import defaultdict
from functools import singledispatch

from mypy import build
from mypy.build import default_data_dir
from mypy.modulefinder import compute_search_paths, FindModuleCache
from mypy.errors import CompileError
from mypy import nodes
from mypy.options import Options

from dumpmodule import module_to_json, DumpNode


# TODO: email.contentmanager has a symbol table with a None node.
#       This seems like it should not be.

skip = {
    '_importlib_modulespec',
    '_subprocess',
    'distutils.command.bdist_msi',
    'distutils.command.bdist_packager',
    'msvcrt',
    'wsgiref.types',
    'mypy_extensions',
    'unittest.mock',  # mock.call infinite loops on inspect.getsourcelines
                      # https://bugs.python.org/issue25532
                      # TODO: can we filter only call?
}  # type: Final


messages = {
    'not_in_runtime': ('{error.stub_type} "{error.name}" defined at line '
                       ' {error.line} in stub but is not defined at runtime'),
    'not_in_stub': ('{error.module_type} "{error.name}" defined at line'
                    ' {error.line} at runtime but is not defined in stub'),
    'no_stubs': 'could not find typeshed {error.name}',
    'inconsistent': ('"{error.name}" is {error.stub_type} in stub but'
                     ' {error.module_type} at runtime'),
}  # type: Final

Error = NamedTuple('Error', (
    ('module', str),
    ('name', str),
    ('error_type', str),
    ('line', Optional[int]),
    ('stub_type', Optional[Type[nodes.Node]]),
    ('module_type', Optional[str]),
))

ErrorParts = Tuple[
    List[str],
    str,
    Optional[int],
    Optional[Type[nodes.Node]],
    Optional[str],
]


def test_stub(options: Options,
              find_module_cache: FindModuleCache,
              name: str) -> Iterator[Error]:
    stubs = {
        mod: stub for mod, stub in build_stubs(options, find_module_cache, name).items()
        if (mod == name or mod.startswith(name + '.')) and mod not in skip
    }

    for mod, stub in stubs.items():
        instance = dump_module(mod)

        for identifiers, error_type, line, stub_type, module_type in verify(stub, instance):
            yield Error(mod, '.'.join(identifiers), error_type, line, stub_type, module_type)


@singledispatch
def verify(node: nodes.Node,
           module_node: Optional[DumpNode]) -> Iterator[ErrorParts]:
    raise TypeError('unknown mypy node ' + str(node))



@verify.register(nodes.MypyFile)
def verify_mypyfile(stub: nodes.MypyFile,
                    instance: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if instance is None:
        yield [], 'not_in_runtime', stub.line, type(stub), None
    elif instance['type'] != 'file':
        yield [], 'inconsistent', stub.line, type(stub), instance['type']
    else:
        stub_children = defaultdict(lambda: None, stub.names)  # type: Mapping[str, Optional[nodes.SymbolTableNode]]
        instance_children = defaultdict(lambda: None, instance['names'])

        # TODO: I would rather not filter public children here.
        #       For example, what if the checkersurfaces an inconsistency
        #       in the typing of a private child
        public_nodes = {
            name: (stub_children[name], instance_children[name])
            for name in set(stub_children) | set(instance_children)
            if not name.startswith('_')
            and (stub_children[name] is None or stub_children[name].module_public)  # type: ignore
        }

        for node, (stub_child, instance_child) in public_nodes.items():
            stub_child = getattr(stub_child, 'node', None)
            for identifiers, error_type, line, stub_type, module_type in verify(stub_child, instance_child):
                yield ([node] + identifiers, error_type, line, stub_type, module_type)


@verify.register(nodes.TypeInfo)
def verify_typeinfo(stub: nodes.TypeInfo,
                    instance: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if not instance:
        yield [], 'not_in_runtime', stub.line, type(stub), None
    elif instance['type'] != 'class':
        yield [], 'inconsistent', stub.line, type(stub), instance['type']
    else:
        for attr, attr_node in stub.names.items():
            subdump = instance['attributes'].get(attr, None)
            for identifiers, error_type, line, stub_type, module_type in verify(attr_node.node, subdump):
                yield ([attr] + identifiers, error_type, line, stub_type, module_type)


@verify.register(nodes.FuncItem)
def verify_funcitem(stub: nodes.FuncItem,
                    instance: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if not instance:
        yield [], 'not_in_runtime', stub.line, type(stub), None
    elif 'type' not in instance or instance['type'] not in ('function', 'callable'):
        yield [], 'inconsistent', stub.line, type(stub), instance['type']
    # TODO check arguments and return value


@verify.register(type(None))
def verify_none(stub: None,
                instance: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if instance is None:
        yield [], 'not_in_stub', None, None, None
    else:
        yield [], 'not_in_stub', instance['line'], None, instance['type']


@verify.register(nodes.Var)
def verify_var(node: nodes.Var,
               module_node: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if False:
        yield None
    # Need to check if types are inconsistent.
    #if 'type' not in dump or dump['type'] != node.node.type:
    #    import ipdb; ipdb.set_trace()
    #    yield name, 'inconsistent', node.node.line, shed_type, module_type


@verify.register(nodes.OverloadedFuncDef)
def verify_overloadedfuncdef(node: nodes.OverloadedFuncDef,
                             module_node: Optional[DumpNode]) -> Iterator[ErrorParts]:
    # Should check types of the union of the overloaded types.
    if False:
        yield None


@verify.register(nodes.TypeVarExpr)
def verify_typevarexpr(node: nodes.TypeVarExpr,
                       module_node: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if False:
        yield None


@verify.register(nodes.Decorator)
def verify_decorator(node: nodes.Decorator,
                     module_node: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if False:
        yield None


@verify.register(nodes.TypeAlias)
def verify_typealias(node: nodes.TypeAlias,
                     module_node: Optional[DumpNode]) -> Iterator[ErrorParts]:
    if False:
        yield None


def dump_module(name: str) -> DumpNode:
    mod = importlib.import_module(name)
    return {'type': 'file', 'names': module_to_json(mod)}


def build_stubs(options: Options,
                find_module_cache: FindModuleCache,
                mod: str) -> Dict[str, nodes.MypyFile]:
    sources = find_module_cache.find_modules_recursive(mod)
    try:
        res = build.build(sources=sources, options=options)
        messages = res.errors
    except CompileError as error:
        messages = error.messages

    if messages:
        for msg in messages:
            print(msg)
        sys.exit(1)
    return res.files


def main(args: List[str]) -> Iterator[Error]:
    if len(args) == 1:
        print('must provide at least one module to test')
        sys.exit(1)
    else:
        modules = args[1:]

    options = Options()
    options.incremental = False
    data_dir = default_data_dir()
    search_path = compute_search_paths([], options, data_dir)
    find_module_cache = FindModuleCache(search_path)

    for module in modules:
        for error in test_stub(options, find_module_cache, module):
            yield error


if __name__ == '__main__':

    for err in main(sys.argv):
        print(messages[err.error_type].format(error=err))
