import unittest

from mypyc.emit import Emitter, EmitterContext
from mypyc.emitwrapper import generate_arg_check
from mypyc.ops import RTType


class TestArgCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.context = EmitterContext()

    def test_check_list(self) -> None:
        emitter = Emitter(self.context)
        generate_arg_check('x', RTType('list'), emitter)
        lines = emitter.fragments
        assert lines == [
            'PyObject *arg_x;\n',
            'if (PyList_Check(obj_x))\n',
            '    arg_x = obj_x;\n',
            'else\n',
            '    return NULL;\n',
        ]
