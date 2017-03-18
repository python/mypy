"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave
at runtime.
"""

import importlib
import sys
from typing import Dict, Any
from collections import defaultdict, namedtuple

from mypy import build
from mypy.build import default_data_dir, default_lib_path, find_modules_recursive
from mypy.errors import CompileError
from mypy.nodes import MypyFile, TypeInfo, FuncItem
from mypy.options import Options

import dumpmodule


skipped = {
    '_importlib_modulespec',
    '_subprocess',
    'distutils.command.bdist_msi',
    'distutils.command.bdist_packager',
    'msvcrt',
    'wsgiref.types',
}


Error = namedtuple('Error', ('name', 'error_type', 'message'))


def test_stub(id: str) -> None:
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
def verify_stub(name, symbols, dumped):
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
            yield Error(name, 'not_in_runtime',
                '"{}" defined in stub but not at runtime'.format(name))
        elif typeshed is None:
            yield Error(name, 'not_in_stub',
                '"{}" defined at runtime but not in stub'.format(name))
        else:
            verify_node(name, typeshed, runtime)


def verify_node(name, node, dump):
    if isinstance(node.node, TypeInfo):
        if not isinstance(dump, dict) or dump['type'] != 'class':
            yield Error(name, 'class_not_in_stub',
                '"{}" is a class in stub but not at runtime'.format(name))
            return
        all_attrs = {x[0] for x in dump['attributes']}
        for attr, attr_node in node.node.names.items():
            if isinstance(attr_node.node, FuncItem) and attr not in all_attrs:
                yield Error(name, 'method_not_in_stub',
                    ('"{}.{}" defined as a method in stub but not defined '
                     'at runtime in class object').format(
                        name, attr))
    # TODO other kinds of nodes


def dump_module(id: str) -> Dict[str, Any]:
    m = importlib.import_module(id)
    return dumpmodule.module_to_json(m)


def build_stubs(id):
    errors = []
    data_dir = default_data_dir(None)
    options = Options()
    options.python_version = (3, 6)
    lib_path = default_lib_path(data_dir,
                                options.python_version,
                                custom_typeshed_dir=None)
    sources = find_modules_recursive(id, lib_path)
    if not sources:
        errors.append(Error(repr(id), 'no_typeshed',
            'could not find typeshed {}'.format(repr(id))))
    try:
        res = build.build(sources=sources,
                          options=options)
        msg = res.errors
    except CompileError as e:
        msg = e.messages
    if msg:
        for m in msg:
            print(m)
        sys.exit(1)
    return res, errors


if __name__ == '__main__':
    for error in test_stub(sys.argv[1]):
        print(error.message)
