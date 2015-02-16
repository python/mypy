"""Automatically generate a dynamically typed stub for an arbitrary module.

For example, to generate a stub for module 'acme':

  $ python3 stubgen.py acme

This would generate acme.py (or directory 'acme' if acme is a package) in the
current directory.
"""

import os.path

import mypy.parse
import mypy.traverser



def generate_stub(path, output_dir):
    source = open(path).read()
    ast = mypy.parse.parse(source)
    gen = StubGenerator()
    ast.accept(gen)
    with open(os.path.join(output_dir, os.path.basename(path)), 'w') as file:
        file.write(''.join(gen.out))


class StubGenerator(mypy.traverser.TraverserVisitor):
    def __init__(self):
        self.out = []

    def visit_func_def(self, o):
        self.add("def %s(" % o.name())
        self.add(", ".join(var.name() for var in o.args))
        self.add("): pass\n")

    def add(self, string):
        self.out.append(string)
