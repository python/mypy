"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave
at runtime.
"""

import importlib
import sys
from typing import Dict, Any, List
from collections import defaultdict, namedtuple

from mypy import build
from mypy.build import default_data_dir, default_lib_path, find_modules_recursive
from mypy.errors import CompileError
from mypy import nodes
from mypy.options import Options

import dumpmodule

if sys.version_info < (3, 4):
    from singledispatch import singledispatch
else:
    from functools import singledispatch

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
}

messages = {
    'not_in_runtime': ('{error.stub_type} "{error.name}" defined at line '
                       ' {error.line} in stub but is not defined at runtime'),
    'not_in_stub': ('{error.module_type} "{error.name}" defined at line'
                    ' {error.line} at runtime but is not defined in stub'),
    'no_stubs': 'could not find typeshed {error.name}',
    'inconsistent': ('"{error.name}" is {error.stub_type} in stub but'
                     ' {error.module_type} at runtime'),
}

Error = namedtuple('Error', (
    'module',
    'name',
    'error_type',
    'line',
    'stub_type',
    'module_type'))


def test_stub(name: str):
    stubs = {
        mod: stub for mod, stub in build_stubs(name).items()
        if (mod == name or mod.startswith(name + '.')) and mod not in skip
    }

    for mod, stub in stubs.items():
        instance = dump_module(mod)

        for identifiers, *error in verify(stub, instance):
            yield Error(mod, '.'.join(identifiers), *error)


@singledispatch
def verify(node, module_node):
    raise TypeError('unknown mypy node ' + str(node))



@verify.register(nodes.MypyFile)
def verify_mypyfile(stub, instance):
    if instance is None:
        yield [], 'not_in_runtime', stub.line, type(stub), None
    elif instance['type'] != 'file':
        yield [], 'inconsistent', stub.line, type(stub), instance['type']
    else:
        stub_children = defaultdict(lambda: None, stub.names)
        instance_children = defaultdict(lambda: None, instance['names'])

        # TODO: I would rather not filter public children here.
        #       For example, what if the checkersurfaces an inconsistency
        #       in the typing of a private child
        public_nodes = {
            name: (stub_children[name], instance_children[name])
            for name in set(stub_children) | set(instance_children)
            if not name.startswith('_')
            and (stub_children[name] is None or stub_children[name].module_public)
        }

        for node, (stub_child, instance_child) in public_nodes.items():
            stub_child = getattr(stub_child, 'node', None)
            for identifiers, *error in verify(stub_child, instance_child):
                yield ([node] + identifiers, *error)

@verify.register(nodes.TypeInfo)
def verify_typeinfo(stub, instance):
    if not instance:
        yield [], 'not_in_runtime', stub.line, type(stub), None
    elif instance['type'] != 'class':
        yield [], 'inconsistent', stub.line, type(stub), instance['type']
    else:
        for attr, attr_node in stub.names.items():
            subdump = instance['attributes'].get(attr, None)
            for identifiers, *error in verify(attr_node.node, subdump):
                yield ([attr] + identifiers, *error)


@verify.register(nodes.FuncItem)
def verify_funcitem(stub, instance):
    if not instance:
        yield [], 'not_in_runtime', stub.line, type(stub), None
    elif 'type' not in instance or instance['type'] not in ('function', 'callable'):
        yield [], 'inconsistent', stub.line, type(stub), instance['type']
    # TODO check arguments and return value


@verify.register(type(None))
def verify_none(stub, instance):
    if instance is None:
        yield [], 'not_in_stub', None, None, None
    else:
        yield [], 'not_in_stub', instance['line'], None, instance['type']


@verify.register(nodes.Var)
def verify_var(node, module_node):
    if False:
        yield None
    # Need to check if types are inconsistent.
    #if 'type' not in dump or dump['type'] != node.node.type:
    #    import ipdb; ipdb.set_trace()
    #    yield name, 'inconsistent', node.node.line, shed_type, module_type


@verify.register(nodes.OverloadedFuncDef)
def verify_overloadedfuncdef(node, module_node):
    # Should check types of the union of the overloaded types.
    if False:
        yield None


@verify.register(nodes.TypeVarExpr)
def verify_typevarexpr(node, module_node):
    if False:
        yield None


@verify.register(nodes.Decorator)
def verify_decorator(node, module_noode):
    if False:
        yield None


def dump_module(name: str) -> Dict[str, Any]:
    mod = importlib.import_module(name)
    return {'type': 'file', 'names': dumpmodule.module_to_json(mod)}


def build_stubs(mod):
    data_dir = default_data_dir(None)
    options = Options()
    options.python_version = (3, 6)
    lib_path = default_lib_path(data_dir,
                                options.python_version,
                                custom_typeshed_dir=None)
    sources = find_modules_recursive(mod, lib_path)
    try:
        res = build.build(sources=sources,
                          options=options)
        messages = res.errors
    except CompileError as error:
        messages = error.messages

    if messages:
        for msg in messages:
            print(msg)
        sys.exit(1)
    return res.files


def main(args):
    if len(args) == 1:
        print('must provide at least one module to test')
        sys.exit(1)
    else:
        modules = args[1:]

    for module in modules:
        for error in test_stub(module):
            yield error


if __name__ == '__main__':

    for err in main(sys.argv):
        print(messages[err.error_type].format(error=err))
