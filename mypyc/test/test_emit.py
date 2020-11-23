import unittest

from mypy.nodes import Var

from mypyc.codegen.emit import Emitter, EmitterContext
from mypyc.ir.ops import BasicBlock, Environment
from mypyc.ir.rtypes import int_rprimitive
from mypyc.ir.pprint import generate_names_for_env
from mypyc.namegen import NameGenerator


class TestEmitter(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Environment()
        self.n = self.env.add_local(Var('n'), int_rprimitive)
        self.context = EmitterContext(NameGenerator([['mod']]))

    def test_label(self) -> None:
        emitter = Emitter(self.context, self.env, {})
        assert emitter.label(BasicBlock(4)) == 'CPyL4'

    def test_reg(self) -> None:
        names = generate_names_for_env(self.env)
        emitter = Emitter(self.context, self.env, names)
        assert emitter.reg(self.n) == 'cpy_r_n'

    def test_emit_line(self) -> None:
        emitter = Emitter(self.context, self.env, {})
        emitter.emit_line('line;')
        emitter.emit_line('a {')
        emitter.emit_line('f();')
        emitter.emit_line('}')
        assert emitter.fragments == ['line;\n',
                                     'a {\n',
                                     '    f();\n',
                                     '}\n']
