"""Generator of dynamically typed stubs for arbitrary modules."""

import os.path

import mypy.parse
import mypy.traverser
from mypy.nodes import (
    IntExpr, UnaryExpr, StrExpr, BytesExpr, NameExpr, FloatExpr, MemberExpr, TupleExpr,
    ListExpr, ARG_STAR, ARG_STAR2, ARG_NAMED
)


def generate_stub(path, output_dir):
    source = open(path).read()
    ast = mypy.parse.parse(source)
    gen = StubGenerator()
    ast.accept(gen)
    with open(os.path.join(output_dir, os.path.basename(path)), 'w') as file:
        file.write(''.join(gen.output()))


class StubGenerator(mypy.traverser.TraverserVisitor):
    def __init__(self):
        self._output = []
        self._imports = []
        self._indent = ''
        self._vars = [[]]

    def visit_mypy_file(self, o):
        self._classes = find_classes(o)
        super().visit_mypy_file(o)

    def visit_func_def(self, o):
        if self.is_private_name(o.name()):
            return
        self_inits = find_self_initializers(o)
        for init in self_inits:
            self.add_init(init)
        self.add("%sdef %s(" % (self._indent, o.name()))
        args = []
        for i, (arg, kind) in enumerate(zip(o.args, o.arg_kinds)):
            name = arg.name()
            init = o.init[i]
            if init:
                if kind == ARG_NAMED and '*' not in args:
                    args.append('*')
                arg = '%s=' % name
                init = init.rvalue
                if isinstance(init, IntExpr):
                    arg += str(init.value)
                elif isinstance(init, StrExpr):
                    arg += "''"
                elif isinstance(init, BytesExpr):
                    arg += "b''"
                elif isinstance(init, FloatExpr):
                    arg += "0.0"
                elif isinstance(init, UnaryExpr):
                    arg += '-%s' % init.expr.value
                elif isinstance(init, NameExpr) and init.name == 'None':
                    arg += init.name
                else:
                    self.add_import("Undefined")
                    arg += 'Undefined'
            elif kind == ARG_STAR:
                arg = '*%s' % name
            elif kind == ARG_STAR2:
                arg = '**%s' % name
            else:
                arg = name
            args.append(arg)
        self.add(', '.join(args))
        self.add("): pass\n")

    def visit_decorator(self, o):
        for decorator in o.decorators:
            if isinstance(decorator, NameExpr) and decorator.name in ('property',
                                                                      'staticmethod',
                                                                      'classmethod'):
                self.add('%s@%s\n' % (self._indent, decorator.name))
            elif (isinstance(decorator, MemberExpr) and decorator.name == 'setter' and
                  isinstance(decorator.expr, NameExpr)):
                self.add('%s@%s.setter\n' % (self._indent, decorator.expr.name))
        super().visit_decorator(o)

    def visit_class_def(self, o):
        self.add('class %s' % o.name)
        base_types = []
        for base in o.base_type_exprs:
            if isinstance(base, NameExpr) and base.name in self._classes:
                base_types.append(base.name)
        if base_types:
            self.add('(%s)' % ', '.join(base_types))
        self.add(':\n')
        n = len(self._output)
        self._indent += '    '
        self._vars.append([])
        super().visit_class_def(o)
        self._indent = self._indent[:-4]
        self._vars.pop()
        if len(self._output) == n:
            self._output[-1] = self._output[-1][:-1] + ' pass\n'

    def visit_assignment_stmt(self, o):
        lvalue = o.lvalues[0]
        if isinstance(lvalue, (TupleExpr, ListExpr)):
            items = lvalue.items
        else:
            items = [lvalue]
        for item in items:
            if isinstance(item, NameExpr):
                self.add_init(item.name)

    def add_init(self, lvalue):
        if lvalue in self._vars[-1]:
            return
        if self.is_private_name(lvalue):
            return
        self._vars[-1].append(lvalue)
        self.add('%s%s = Undefined(Any)\n' % (self._indent, lvalue))
        self.add_import('Undefined')
        self.add_import('Any')

    def add(self, string):
        self._output.append(string)

    def add_import(self, name):
        if name not in self._imports:
            self._imports.append(name)

    def output(self):
        if self._imports:
            imports = 'from typing import %s\n\n' % ", ".join(self._imports)
        else:
            imports = ''
        return imports + ''.join(self._output)

    def is_private_name(self, name):
        return name.startswith('_') and (not name.endswith('__') or name == '__all__')


def find_self_initializers(fdef):
    results = []
    class SelfTraverser(mypy.traverser.TraverserVisitor):
        def visit_assignment_stmt(self, o):
            lvalue = o.lvalues[0]
            if (isinstance(lvalue, MemberExpr) and
                    isinstance(lvalue.expr, NameExpr) and
                    lvalue.expr.name == 'self'):
                results.append(lvalue.name)
    fdef.accept(SelfTraverser())
    return results


def find_classes(cdef):
    results = set()
    class ClassTraverser(mypy.traverser.TraverserVisitor):
        def visit_class_def(self, o):
            results.add(o.name)
    cdef.accept(ClassTraverser())
    return results


if __name__ == '__main__':
    import sys
    for path in sys.argv[1:]:
        generate_stub(path, '.')
