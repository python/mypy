"""Stub generator for C modules.

TODO:

 * infer argument names and counts from documentation when clearly unambigous
 - infer constant sigs for special methods (__add__, __str__, etc.)
 - try to infer sigs of __new__ / __init__
 - include non-object base classes
 - skip __module__, __weakref__ etc. noise in stubs (maybe also __reduce__)
 - add empty lines for nicer formatting
 - add tests
 - add from typing import ...
 - run against many C modules
 - integrate with stubgen
 - include comment saying that this is a c module
"""

import _datetime
import os.path


from mypy.stubutil import parse_all_signatures, find_unique_signatures


def generate_stub_for_c_module(module_name, sigs={}):
    module = __import__(module_name)
    if '__file__' in module.__dict__ and not module.__dict__['__file__'].endswith('.so'):
        raise RuntimeError('%s is not a C module' % module_name)
    functions = []
    done = set()
    items = sorted(module.__dict__.items(), key=lambda x: x[0])
    for name, obj in items:
        if is_c_function(obj):
            generate_c_function_stub(module, name, obj, functions, sigs=sigs)
            done.add(name)
    types = []
    for name, obj in items:
        if name.startswith('__') and name.endswith('__'):
            continue
        if is_c_type(obj):
            generate_c_type_stub(module, name, obj, types, sigs=sigs)
            done.add(name)
    variables = []
    for name, obj in items:
        if name.startswith('__') and name.endswith('__'):
            continue
        if name not in done:
            type_str = type(obj).__name__
            if type_str not in ('int', 'str', 'bytes', 'float', 'bool'):
                type_str = 'Any'
            variables.append('%s = Undefined(%s)' % (name, type_str))
    for var in variables:
        print(var)
    for func in functions:
        print(func)
    for typ in types:
        print(typ)


def is_c_function(obj):
    return type(obj) is type(ord)


def is_c_method(obj):
    return type(obj) in (type(str.index),
                         type(str.__add__),
                         type(str.__new__))


def is_c_classmethod(obj):
    type_str = type(obj).__name__
    return type_str == 'classmethod_descriptor'


def is_c_type(obj):
    return type(obj) is type(int)


def generate_c_function_stub(module, name, obj, output, self_var=None, sigs={}):
    if self_var:
        self_arg = '%s, ' % self_var
    else:
        self_arg = ''
    sig = sigs.get(name, '(*args, **kwargs)')
    sig = sig[1:-1]
    if not sig:
        self_arg = self_arg.replace(', ', '')
    output.append('def %s(%s%s): pass' % (name, self_arg, sig))


def generate_c_type_stub(module, class_name, obj, output, sigs={}):
    items = sorted(obj.__dict__.items(), key=lambda x: method_name_sort_key(x[0]))
    methods = []
    done = set()
    for attr, value in items:
        if is_c_method(value) or is_c_classmethod(value):
            done.add(attr)
            if attr not in ('__getattribute__',
                            '__str__',
                            '__repr__'):
                if is_c_classmethod(value):
                    methods.append('@classmethod')
                    self_var = 'cls'
                else:
                    self_var = 'self'
                generate_c_function_stub(module, attr, value, methods, self_var, sigs=sigs)
    variables = []
    for attr, value in items:
        if attr == '__doc__':
            continue
        if attr not in done:
            variables.append('%s = Undefined(Any)' % attr)
    if not methods and not variables:
        output.append('class %s: pass' % class_name)
    else:
        output.append('class %s:' % class_name)
        for variable in variables:
            output.append('    %s' % variable)
        for method in methods:
            output.append('    %s' % method)


def method_name_sort_key(name):
    if name in ('__new__', '__init__'):
        return (0, name)
    if name.startswith('__') and name.endswith('__'):
        return (2, name)
    return (1, name)


if __name__ == '__main__':
    import sys
    import glob
    if not os.path.isdir('out'):
        raise SystemExit('Directory out does not exist')
    if sys.argv[1] == '--docpath':
        docpath = sys.argv[2]
        modules = sys.argv[3:]
        all_sigs = []
        for path in glob.glob('%s/*.rst' % docpath):
            all_sigs += parse_all_signatures(open(path).readlines())
        sigs = dict(find_unique_signatures(all_sigs))
    else:
        modules = sys.argv[1:]
        sigs = {}
    for module in modules:
        generate_stub_for_c_module(module, sigs)
