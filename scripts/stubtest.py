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
from mypy.nodes import MypyFile, TypeInfo, FuncItem, Var, OverloadedFuncDef, TypeVarExpr, Decorator
from mypy.options import Options

import dumpmodule

# TODO: why are these skipped
skipped = {
    '_importlib_modulespec',
    '_subprocess',
    'distutils.command.bdist_msi',
    'distutils.command.bdist_packager',
    'msvcrt',
    'wsgiref.types',
    'unittest.mock',  # mock.call infinite loops on inspect.getsourcelines
                      # https://bugs.python.org/issue25532
}

messages = {
    'not_in_runtime': ('<{error.stub_type}> "{error.name}" defined at line '
                       ' {error.line} in stub but is not defined at runtime'),
    'not_in_stub': ('<{error.module_type}> "{error.name}" defined at line'
                    ' {error.line} at runtime but is not defined in stub'),
    'no_typeshed': 'could not find typeshed {error.name}',
    'inconsistent': ('"{error.name}" is <{error.stub_type}> in stub but'
                     ' <{error.module_type}> at runtime'),
}

Error = namedtuple('Error', (
    'module',
    'name',
    'error_type',
    'line',
    'stub_type',
    'module_type'))


def test_stub(id: str) -> List[Error]:
    result, errors = build_stubs(id)
    errors += list(verify_stubs(result.files, prefix=id))
    return errors


def verify_stubs(files: Dict[str, MypyFile], prefix: str) -> None:
    for id, node in files.items():
        if not (id == prefix or id.startswith(prefix + '.')):
            # Not one of the target modules
            continue
        if id in skipped:
            # There's some issue with processing this module; skip for now
            continue
        dumped = dump_module(id)
        yield from verify_stub(id, node.names, dumped)


# symbols is typeshed, dumped is runtime
def verify_stub(module: str, symbols: dict, dumped: dict):
    """Generate mismatches between typshed and runtime types

    It accepts the following parameters
    module: name of module to check
    symbols: dictionary of typeshed types
    dumped: dictionary of runtime types
    """
    symbols = defaultdict(lambda: None, symbols)
    dumped = defaultdict(lambda: None, dumped)

    all_symbols = {
        name: (symbols[name], dumped[name])
        for name in (set(symbols) | set(dumped))
        if not name.startswith('_')  # private attributes
        and (symbols[name] is None or symbols[name].module_public)
    }

    for name, (typeshed, runtime) in all_symbols.items():
        if runtime is None:
            line = getattr(typeshed.node, 'line', None)
            shed_type = type(typeshed.node).__name__
            yield Error(module, name, 'not_in_runtime', line, shed_type, None)
        elif typeshed is None:
            yield Error(module, name, 'not_in_stub', runtime['line'], None, runtime['type'])
        else:
            for err in verify_node(name, typeshed, runtime):
                yield Error(module, *err)


def verify_node(name, node, dump):
    module_type = dump.get('type', None)
    shed_type = type(node.node).__name__
    if isinstance(node.node, TypeInfo):
        if dump['type'] != 'class':
            yield name, 'inconsistent', node.node.line, shed_type, module_type
        else:
            for attr, attr_node in node.node.names.items():
                subname = '{}.{}'.format(name, attr)
                subdump = dump['attributes'].get(attr, {})
                for err in verify_node(subname, attr_node, subdump):
                    yield err

    elif isinstance(node.node, FuncItem):
        if 'type' not in dump or dump['type'] not in ('function', 'callable'):
            yield name, 'inconsistent', node.node.line, shed_type, module_type
        # TODO check arguments and return value
    elif isinstance(node.node, Var):
        pass
        # Need to check if types are inconsistent.
        #if 'type' not in dump or dump['type'] != node.node.type:
        #    import ipdb; ipdb.set_trace()
        #    yield name, 'inconsistent', node.node.line, shed_type, module_type
    elif isinstance(node.node, MypyFile):
        pass # TODO: what checking can we do here?
    elif isinstance(node.node, OverloadedFuncDef):
        # Should check types of the union of the overloaded types.
        pass
    elif isinstance(node.node, TypeVarExpr):
        pass # TODO: what even is this?
    elif isinstance(node.node, Decorator):
        pass # What can we check here?
    else:
        raise TypeError('unkonwn node type {}'.format(node.node))


def dump_module(id: str) -> Dict[str, Any]:
    m = importlib.import_module(id)
    return dumpmodule.module_to_json(m)


def build_stubs(mod):
    errors = []
    data_dir = default_data_dir(None)
    options = Options()
    options.python_version = (3, 6)
    lib_path = default_lib_path(data_dir,
                                options.python_version,
                                custom_typeshed_dir=None)
    sources = find_modules_recursive(mod, lib_path)
    if not sources:
        errors += [Error(repr(mod), repr(mod), 'no_typeshed', None, None, None)]
    try:
        res = build.build(sources=sources,
                          options=options)
        messages = res.errors
    except CompileError as err:
        messages = err.messages

    if messages:
        for msg in messages:
            print(msg)
        sys.exit(1)
    return res, errors


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
