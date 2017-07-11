"""Stub generator for C modules.

The public interface is via the mypy.stubgen module.
"""

import importlib
import os.path
import re
from typing import List, Dict, Tuple, Optional
from types import ModuleType

from mypy.stubutil import (
    parse_all_signatures, find_unique_signatures, is_c_module, write_header,
    infer_sig_from_docstring
)


def generate_stub_for_c_module(module_name: str,
                               target: str,
                               add_header: bool = True,
                               sigs: Dict[str, str] = {},
                               class_sigs: Dict[str, str] = {},
                               ) -> None:
    module = importlib.import_module(module_name)
    assert is_c_module(module), '%s is not a C module' % module_name
    subdir = os.path.dirname(target)
    if subdir and not os.path.isdir(subdir):
        os.makedirs(subdir)
    functions = []  # type: List[str]
    done = set()
    items = sorted(module.__dict__.items(), key=lambda x: x[0])
    for name, obj in items:
        if is_c_function(obj):
            generate_c_function_stub(module, name, obj, functions, sigs=sigs)
            done.add(name)
    types = []  # type: List[str]
    for name, obj in items:
        if name.startswith('__') and name.endswith('__'):
            continue
        if is_c_type(obj):
            generate_c_type_stub(module, name, obj, types, sigs=sigs, class_sigs=class_sigs)
            done.add(name)
    variables = []
    for name, obj in items:
        if name.startswith('__') and name.endswith('__'):
            continue
        if name not in done:
            type_str = type(obj).__name__
            if type_str not in ('int', 'str', 'bytes', 'float', 'bool'):
                type_str = 'Any'
            variables.append('%s = ... # type: %s' % (name, type_str))
    output = []
    for line in variables:
        output.append(line)
    if output and functions:
        output.append('')
    for line in functions:
        output.append(line)
    for line in types:
        if line.startswith('class') and output and output[-1]:
            output.append('')
        output.append(line)
    output = add_typing_import(output)
    with open(target, 'w') as file:
        if add_header:
            write_header(file, module_name)
        for line in output:
            file.write('%s\n' % line)


def add_typing_import(output: List[str]) -> List[str]:
    names = []
    for name in ['Any']:
        if any(re.search(r'\b%s\b' % name, line) for line in output):
            names.append(name)
    if names:
        return ['from typing import %s' % ', '.join(names), ''] + output
    else:
        return output[:]


def is_c_function(obj: object) -> bool:
    return type(obj) is type(ord)


def is_c_method(obj: object) -> bool:
    return type(obj) in (type(str.index),
                         type(str.__add__),
                         type(str.__new__))


def is_c_classmethod(obj: object) -> bool:
    type_str = type(obj).__name__
    return type_str == 'classmethod_descriptor'


def is_c_type(obj: object) -> bool:
    return type(obj) is type(int)


def generate_c_function_stub(module: ModuleType,
                             name: str,
                             obj: object,
                             output: List[str],
                             self_var: Optional[str] = None,
                             sigs: Dict[str, str] = {},
                             class_name: Optional[str] = None,
                             class_sigs: Dict[str, str] = {},
                             ) -> None:
    if self_var:
        self_arg = '%s, ' % self_var
    else:
        self_arg = ''
    if (name in ('__new__', '__init__') and name not in sigs and class_name and
            class_name in class_sigs):
        sig = class_sigs[class_name]
    else:
        docstr = getattr(obj, '__doc__', None)
        inferred = infer_sig_from_docstring(docstr, name)
        if inferred:
            sig = inferred
        else:
            if class_name and name not in sigs:
                sig = infer_method_sig(name)
            else:
                sig = sigs.get(name, '(*args, **kwargs)')
    sig = sig[1:-1]
    if sig:
        if sig.split(',', 1)[0] == self_var:
            self_arg = ''
    else:
        self_arg = self_arg.replace(', ', '')
    output.append('def %s(%s%s): ...' % (name, self_arg, sig))


def generate_c_type_stub(module: ModuleType,
                         class_name: str,
                         obj: type,
                         output: List[str],
                         sigs: Dict[str, str] = {},
                         class_sigs: Dict[str, str] = {},
                         ) -> None:
    items = sorted(obj.__dict__.items(), key=lambda x: method_name_sort_key(x[0]))
    methods = []
    done = set()
    for attr, value in items:
        if is_c_method(value) or is_c_classmethod(value):
            done.add(attr)
            if not is_skipped_attribute(attr):
                if is_c_classmethod(value):
                    methods.append('@classmethod')
                    self_var = 'cls'
                else:
                    self_var = 'self'
                if attr == '__new__':
                    # TODO: We should support __new__.
                    if '__init__' in obj.__dict__:
                        # Avoid duplicate functions if both are present.
                        # But is there any case where .__new__() has a
                        # better signature than __init__() ?
                        continue
                    attr = '__init__'
                generate_c_function_stub(module, attr, value, methods, self_var, sigs=sigs,
                                         class_name=class_name, class_sigs=class_sigs)
    variables = []
    for attr, value in items:
        if is_skipped_attribute(attr):
            continue
        if attr not in done:
            variables.append('%s = ... # type: Any' % attr)
    all_bases = obj.mro()
    if all_bases[-1] is object:
        # TODO: Is this always object?
        del all_bases[-1]
    # remove the class itself
    all_bases = all_bases[1:]
    # Remove base classes of other bases as redundant.
    bases = []  # type: List[type]
    for base in all_bases:
        if not any(issubclass(b, base) for b in bases):
            bases.append(base)
    if bases:
        bases_str = '(%s)' % ', '.join(base.__name__ for base in bases)
    else:
        bases_str = ''
    if not methods and not variables:
        output.append('class %s%s: ...' % (class_name, bases_str))
    else:
        output.append('class %s%s:' % (class_name, bases_str))
        for variable in variables:
            output.append('    %s' % variable)
        for method in methods:
            output.append('    %s' % method)


def method_name_sort_key(name: str) -> Tuple[int, str]:
    if name in ('__new__', '__init__'):
        return (0, name)
    if name.startswith('__') and name.endswith('__'):
        return (2, name)
    return (1, name)


def is_skipped_attribute(attr: str) -> bool:
    return attr in ('__getattribute__',
                    '__str__',
                    '__repr__',
                    '__doc__',
                    '__dict__',
                    '__module__',
                    '__weakref__')  # For pickling


def infer_method_sig(name: str) -> str:
    if name.startswith('__') and name.endswith('__'):
        name = name[2:-2]
        if name in ('hash', 'iter', 'next', 'sizeof', 'copy', 'deepcopy', 'reduce', 'getinitargs',
                    'int', 'float', 'trunc', 'complex', 'bool'):
            return '()'
        if name == 'getitem':
            return '(index)'
        if name == 'setitem':
            return '(index, object)'
        if name in ('delattr', 'getattr'):
            return '(name)'
        if name == 'setattr':
            return '(name, value)'
        if name == 'getstate':
            return '()'
        if name == 'setstate':
            return '(state)'
        if name in ('eq', 'ne', 'lt', 'le', 'gt', 'ge',
                    'add', 'radd', 'sub', 'rsub', 'mul', 'rmul',
                    'mod', 'rmod', 'floordiv', 'rfloordiv', 'truediv', 'rtruediv',
                    'divmod', 'rdivmod', 'pow', 'rpow'):
            return '(other)'
        if name in ('neg', 'pos'):
            return '()'
    return '(*args, **kwargs)'
