"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave
at runtime.
"""

import importlib
import json
import subprocess
import sys
from typing import Dict, Any
from collections import defaultdict

from mypy import build
from mypy.build import default_data_dir, default_lib_path, find_modules_recursive
from mypy.errors import CompileError
from mypy.nodes import MypyFile, TypeInfo, FuncItem
from mypy.options import Options


skipped = {
    '_importlib_modulespec',
    '_subprocess',
    'distutils.command.bdist_msi',
    'distutils.command.bdist_packager',
    'msvcrt',
    'wsgiref.types',
}


class Errors:
    def __init__(self, id):
        self.id = id
        self.num_errors = 0

    def fail(self, msg):
        print('{}: {}'.format(self.id, msg))
        self.num_errors += 1


def test_stub(id: str) -> None:
    result = build_stubs(id)
    verify_stubs(result.files, prefix=id)


def verify_stubs(files: Dict[str, MypyFile], prefix: str) -> None:
    for id, node in files.items():
        if not (id == prefix or id.startswith(prefix + '.')):
            # Not one of the target modules
            continue
        if id in skipped:
            # There's some issue with processing this module; skip for now
            continue
        dumped = dump_module(id)
        verify_stub(id, node.names, dumped)


# symbols is typeshed, dumped is runtime
def verify_stub(id, symbols, dumped):
    errors = Errors(id)
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
            errors.fail('"{}" defined in stub but not at runtime'.format(name))
        elif typeshed is None:
            errors.fail('"{}" defined at runtime but not in stub'.format(name))
        else:
            verify_node(name, typeshed, runtime, errors)


def verify_node(name, node, dump, errors):
    if isinstance(node.node, TypeInfo):
        if not isinstance(dump, dict) or dump['type'] != 'class':
            errors.fail('"{}" is a class in stub but not at runtime'.format(name))
            return
        all_attrs = {x[0] for x in dump['attributes']}
        for attr, attr_node in node.node.names.items():
            if isinstance(attr_node.node, FuncItem) and attr not in all_attrs:
                errors.fail(
                    ('"{}.{}" defined as a method in stub but not defined '
                     'at runtime in class object').format(
                        name, attr))
    # TODO other kinds of nodes


def dump_module(id: str) -> Dict[str, Any]:
    try:
        o = subprocess.check_output(
            ['python', 'scripts/dumpmodule.py', id])
    except subprocess.CalledProcessError:
        print('Failure to dump module contents of "{}"'.format(id))
        sys.exit(1)
    return json.loads(o.decode('ascii'))


def build_stubs(id):
    data_dir = default_data_dir(None)
    options = Options()
    options.python_version = (3, 6)
    lib_path = default_lib_path(data_dir,
                                options.python_version,
                                custom_typeshed_dir=None)
    sources = find_modules_recursive(id, lib_path)
    if not sources:
        sys.exit('Error: Cannot find module {}'.format(repr(id)))
    msg = []
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
    return res


if __name__ == '__main__':
    test_stub(sys.argv[1])
