import unittest
from typing import List

from mypy.test.helpers import assert_string_arrays_equal

from mypyc.emit import Emitter, EmitterContext
from mypyc.emitwrapper import generate_arg_check
from mypyc.ops import ListRType, IntRType


class TestArgCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.context = EmitterContext()

    def test_check_list(self) -> None:
        emitter = Emitter(self.context)
        generate_arg_check('x', ListRType(), emitter)
        lines = emitter.fragments
        self.assert_lines([
            'PyObject *arg_x;',
            'if (PyList_Check(obj_x))',
            '    arg_x = obj_x;',
            'else {',
            '    PyErr_SetString(PyExc_TypeError, "list object expected");',
            '    arg_x = NULL;',
            '}',
            'if (arg_x == NULL) return NULL;',
        ], lines)

    def test_check_int(self) -> None:
        emitter = Emitter(self.context)
        generate_arg_check('x', IntRType(), emitter)
        lines = emitter.fragments
        self.assert_lines([
            'CPyTagged arg_x;',
            'if (PyLong_Check(obj_x))',
            '    arg_x = CPyTagged_BorrowFromObject(obj_x);',
            'else {',
            '    PyErr_SetString(PyExc_TypeError, "int object expected");',
            '    return NULL;',
            '}',
        ], lines)

    def assert_lines(self, expected: List[str], actual: List[str]) -> None:
        actual = [line.rstrip('\n') for line in actual]
        assert_string_arrays_equal(expected, actual, 'Invalid output')
