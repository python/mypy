"""Stub generator for C modules.

TODO:

 - add tests
 - infer argument names and counts from documentation when unambigous
 - add empty lines for nicer formatting
 - add from typing import ...
 - run against many C modules
"""

import _datetime
import os.path


def generate_stub_for_c_module(module_name):
    module = __import__(module_name)
    if '__file__' in module.__dict__:
        raise RuntimeError('%s is not a C module' % module_name)
    functions = []
    done = set()
    items = sorted(module.__dict__.items(), key=lambda x: x[0])
    for name, obj in items:
        if is_c_function(obj):
            generate_c_function_stub(module, name, obj, functions)
            done.add(name)
    types = []
    for name, obj in items:
        if name.startswith('__') and name.endswith('__'):
            continue
        if is_c_type(obj):
            generate_c_type_stub(module, name, obj, types)
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


def generate_c_function_stub(module, name, obj, output, self_var=None):
    if self_var:
        self_arg = '%s, ' % self_var
    else:
        self_arg = ''
    output.append('def %s(%s*args, **kwargs): pass' % (name, self_arg))


def generate_c_type_stub(module, class_name, obj, output):
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
                generate_c_function_stub(module, attr, value, methods, self_var)
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
    if not os.path.isdir('out'):
        raise SystemExit('Directory out does not exist')
    for module in sys.argv[1:]:
        generate_stub_for_c_module(module)
