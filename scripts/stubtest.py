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
from mypy.nodes import MypyFile, TypeInfo, FuncItem
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

not_in_runtime_msg = ('"{name}" defined at line {line} in stub '
                      'but is not defined at runtime').format

not_in_stub_msg = ('"{obj_type} {name}" defined at line {line} at runtime '
                   'but is not defined in stub').format

no_typeshed_msg = 'could not find typeshed {}'.format

class_not_in_stub_msg = '"{}" is a class in stub but not at runtime'.format

method_not_in_stub_msg = ('"{}.{}" defined as a method in stub but not defined '
                          'at runtime in class object').format

Error = namedtuple('Error', ('module', 'name', 'error_type', 'line', 'message'))


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
            msg = not_in_runtime_msg(name=name, line=line)
            yield Error(module, name, 'not_in_runtime', line, msg)
        elif typeshed is None:
            msg = not_in_stub_msg(
                obj_type=runtime['type'],
                name=name,
                line=runtime['line'])
            yield Error(module, name, 'not_in_stub', runtime['line'], msg)
        else:
            for obj, error_type, line, msg in verify_node(name, typeshed, runtime):
                yield Error(module, obj, error_type, line, msg)


def verify_node(name, node, dump):
    if isinstance(node.node, TypeInfo):
        if not isinstance(dump, dict) or dump['type'] != 'class':
            yield (name, 'class_not_in_stub', node.node.line,
                   class_not_in_stub_msg(name))
            return
        all_attrs = {x[0] for x in dump['attributes']}
        for attr, attr_node in node.node.names.items():
            if isinstance(attr_node.node, FuncItem) and attr not in all_attrs:
                yield (name, 'method_not_in_stub', node.node.line,
                       method_not_in_stub_msg(name, attr))
    # TODO other kinds of nodes


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
        errors += [Error(repr(mod), repr(mod), 'no_typeshed', None,
                        no_typeshed_msg(repr(mod)))]
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


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('must provide at least one module to test, or --all_stdlib')
        sys.exit(1)
    elif sys.argv[1] == '--all_stdlib':
        version = '{}.{}'.format(sys.version_info.major, sys.version_info.minor)
        from stdlib_list import stdlib_list
        modules = set(stdlib_list(version))
        modules.remove('unittest')
        modules.remove('unittest.mock')
    else:
        modules = sys.argv[1:]

    for module in modules:
        for error in test_stub(module):
            print(error.module, ':', error.message)
