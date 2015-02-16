"""Generator of dynamically typed stubs for arbitrary modules."""

import os.path

import mypy.parse
import mypy.traverser
from mypy.nodes import IntExpr, UnaryExpr, StrExpr, BytesExpr, NameExpr


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

    def visit_func_def(self, o):
        self.add("def %s(" % o.name())
        args = []
        for i, (arg, kind) in enumerate(zip(o.args, o.arg_kinds)):
            name = arg.name()
            init = o.init[i]
            if init:
                arg = '%s=' % name
                init = init.rvalue
                if isinstance(init, IntExpr):
                    arg += str(init.value)
                elif isinstance(init, StrExpr):
                    arg += "''"
                elif isinstance(init, BytesExpr):
                    arg += "b''"
                elif isinstance(init, UnaryExpr):
                    arg += '-%s' % init.expr.value
                elif isinstance(init, NameExpr) and init.name == 'None':
                    arg += init.name
                else:
                    self.add_import("Undefined")
                    arg += 'Undefined'
            else:
                arg = name
            args.append(arg)
        self.add(', '.join(args))
        self.add("): pass\n")

    def visit_int_expr(self, o):
        self.add(str(o.value))

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
