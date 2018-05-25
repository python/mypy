import unittest

from mypy.nodes import Var
from mypy.test.helpers import assert_string_arrays_equal

from mypyc.ops import (
    Environment, BasicBlock, FuncIR, RuntimeArg, RType, Goto, Return, LoadInt, Assign,
    PrimitiveOp, IncRef, DecRef, Branch, Call, Unbox, Box, RTuple, TupleGet, GetAttr,
    ClassIR, RInstance, SetAttr, Op, Label, int_rprimitive, bool_rprimitive, list_rprimitive,
    dict_rprimitive, object_rprimitive
)
from mypyc.emit import Emitter, EmitterContext
from mypyc.emitfunc import generate_native_function, FunctionEmitterVisitor


class TestFunctionEmitterVisitor(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Environment()
        self.n = self.env.add_local(Var('n'), int_rprimitive)
        self.m = self.env.add_local(Var('m'), int_rprimitive)
        self.k = self.env.add_local(Var('k'), int_rprimitive)
        self.l = self.env.add_local(Var('l'), list_rprimitive)
        self.ll = self.env.add_local(Var('ll'), list_rprimitive)
        self.o = self.env.add_local(Var('o'), object_rprimitive)
        self.o2 = self.env.add_local(Var('o2'), object_rprimitive)
        self.d = self.env.add_local(Var('d'), dict_rprimitive)
        self.b = self.env.add_local(Var('b'), bool_rprimitive)
        self.context = EmitterContext()
        self.emitter = Emitter(self.context, self.env)
        self.declarations = Emitter(self.context, self.env)
        self.visitor = FunctionEmitterVisitor(self.emitter, self.declarations, 'func', 'prog.py')

    def test_goto(self) -> None:
        self.assert_emit(Goto(Label(2)),
                         "goto CPyL2;")

    def test_return(self) -> None:
        self.assert_emit(Return(self.m),
                         "return cpy_r_m;")

    def test_load_int(self) -> None:
        self.assert_emit(LoadInt(self.m, 5),
                         "cpy_r_m = 10;")

    def test_tuple_get(self) -> None:
        self.assert_emit(TupleGet(self.m, self.n, 1, bool_rprimitive, 0), 'cpy_r_m = cpy_r_n.f1;')

    def test_load_None(self) -> None:
        self.assert_emit(PrimitiveOp(self.m, PrimitiveOp.NONE, [], 0),
                         """cpy_r_m = Py_None;
                            Py_INCREF(cpy_r_m);
                         """)

    def test_load_True(self) -> None:
        self.assert_emit(PrimitiveOp(self.m, PrimitiveOp.TRUE, [], 0), "cpy_r_m = 1;")

    def test_load_False(self) -> None:
        self.assert_emit(PrimitiveOp(self.m, PrimitiveOp.FALSE, [], 0), "cpy_r_m = 0;")

    def test_assign_int(self) -> None:
        self.assert_emit(Assign(self.m, self.n),
                         "cpy_r_m = cpy_r_n;")

    def test_int_add(self) -> None:
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.INT_ADD, [self.m, self.k], 55),
                         "cpy_r_n = CPyTagged_Add(cpy_r_m, cpy_r_k);")

    def test_int_sub(self) -> None:
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.INT_SUB, [self.m, self.k], 55),
                         "cpy_r_n = CPyTagged_Subtract(cpy_r_m, cpy_r_k);")

    def test_list_repeat(self) -> None:
        self.assert_emit(PrimitiveOp(self.ll, PrimitiveOp.LIST_REPEAT, [self.l, self.n], 55),
                         """long long __tmp1;
                            __tmp1 = CPyTagged_AsLongLong(cpy_r_n);
                            if (__tmp1 == -1 && PyErr_Occurred())
                                CPyError_OutOfMemory();
                            cpy_r_ll = PySequence_Repeat(cpy_r_l, __tmp1);
                         """)

    def test_int_neg(self) -> None:
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.INT_NEG, [self.m], 55),
                         "cpy_r_n = CPy_NegateInt(cpy_r_m);")

    def test_list_len(self) -> None:
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.LIST_LEN, [self.l], 55),
                         """long long __tmp1;
                            __tmp1 = PyList_GET_SIZE(cpy_r_l);
                            cpy_r_n = CPyTagged_ShortFromLongLong(__tmp1);
                         """)

    def test_branch_eq(self) -> None:
        self.assert_emit(Branch(self.n, self.m, Label(8), Label(9), Branch.INT_EQ),
                         """if (CPyTagged_IsEq(cpy_r_n, cpy_r_m)) {
                                goto CPyL8;
                            } else
                                goto CPyL9;
                         """)
        b = Branch(self.n, self.m, Label(8), Label(9), Branch.INT_LT)
        b.negated = True
        self.assert_emit(b,
                         """if (!CPyTagged_IsLt(cpy_r_n, cpy_r_m)) {
                                goto CPyL8;
                            } else
                                goto CPyL9;
                         """)

    def test_call(self) -> None:
        self.assert_emit(Call(self.n, 'myfn', [self.m], 55),
                         "cpy_r_n = CPyDef_myfn(cpy_r_m);")

    def test_call_two_args(self) -> None:
        self.assert_emit(Call(self.n, 'myfn', [self.m, self.k], 55),
                         "cpy_r_n = CPyDef_myfn(cpy_r_m, cpy_r_k);")

    def test_call_no_return(self) -> None:
        self.assert_emit(Call(None, 'myfn', [self.m, self.k], 55),
                         "CPyDef_myfn(cpy_r_m, cpy_r_k);")

    def test_inc_ref(self) -> None:
        self.assert_emit(IncRef(self.m, int_rprimitive),
                         "CPyTagged_IncRef(cpy_r_m);")

    def test_dec_ref(self) -> None:
        self.assert_emit(DecRef(self.m, int_rprimitive),
                         "CPyTagged_DecRef(cpy_r_m);")

    def test_dec_ref_tuple(self) -> None:
        tuple_type = RTuple([int_rprimitive, bool_rprimitive])
        self.assert_emit(DecRef(self.m, tuple_type), 'CPyTagged_DecRef(cpy_r_m.f0);')

    def test_dec_ref_tuple_nested(self) -> None:
        tuple_type = RTuple([RTuple([int_rprimitive, bool_rprimitive]), bool_rprimitive])
        self.assert_emit(DecRef(self.m, tuple_type), 'CPyTagged_DecRef(cpy_r_m.f0.f0);')

    def test_list_get_item(self) -> None:
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.LIST_GET, [self.m, self.k], 55),
                         """cpy_r_n = CPyList_GetItem(cpy_r_m, cpy_r_k);""")

    def test_list_set_item(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, PrimitiveOp.LIST_SET, [self.l, self.n, self.o], 55),
                         """cpy_r_b = CPyList_SetItem(cpy_r_l, cpy_r_n, cpy_r_o) != 0;""")

    def test_box(self) -> None:
        self.assert_emit(Box(self.o, self.n, int_rprimitive),
                         """cpy_r_o = CPyTagged_StealAsObject(cpy_r_n);""")

    def test_unbox(self) -> None:
        self.assert_emit(Unbox(self.n, self.m, int_rprimitive, 55),
                         """if (PyLong_Check(cpy_r_m))
                                cpy_r_n = CPyTagged_FromObject(cpy_r_m);
                            else {
                                PyErr_SetString(PyExc_TypeError, "int object expected");
                                cpy_r_n = CPY_INT_TAG;
                            }
                         """)

    def test_new_list(self) -> None:
        self.assert_emit(PrimitiveOp(self.l, PrimitiveOp.NEW_LIST, [self.n, self.m], 55),
                         """cpy_r_l = PyList_New(2);
                            Py_INCREF(cpy_r_n);
                            Py_INCREF(cpy_r_m);
                            if (cpy_r_l != NULL) {
                                PyList_SET_ITEM(cpy_r_l, 0, cpy_r_n);
                                PyList_SET_ITEM(cpy_r_l, 1, cpy_r_m);
                            }
                         """)

    def test_list_append(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, PrimitiveOp.LIST_APPEND, [self.l, self.o], 1),
                         """cpy_r_b = PyList_Append(cpy_r_l, cpy_r_o) != -1;""")

    def test_get_attr(self) -> None:
        ir = ClassIR('A', [('x', bool_rprimitive),
                           ('y', int_rprimitive)])
        rtype = RInstance(ir)
        self.assert_emit(GetAttr(self.n, self.m, 'y', rtype, 1),
                         """cpy_r_n = CPY_GET_ATTR(cpy_r_m, 2, AObject, CPyTagged);""")

    def test_set_attr(self) -> None:
        ir = ClassIR('A', [('x', bool_rprimitive),
                           ('y', int_rprimitive)])
        rtype = RInstance(ir)
        self.assert_emit(SetAttr(self.b, self.n, 'y', self.m, rtype, 1),
                         """cpy_r_b = CPY_SET_ATTR(cpy_r_n, 3, cpy_r_m, AObject, CPyTagged);""")

    def test_dict_get_item(self) -> None:
        self.assert_emit(PrimitiveOp(self.o, PrimitiveOp.DICT_GET, [self.d, self.o2], 1),
                         """cpy_r_o = PyDict_GetItemWithError(cpy_r_d, cpy_r_o2);
                            if (!cpy_r_o)
                                PyErr_SetObject(PyExc_KeyError, cpy_r_o2);
                            else
                                Py_INCREF(cpy_r_o);
                         """)

    def test_dict_set_item(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, PrimitiveOp.DICT_SET, [self.d, self.o, self.o2], 1),
                         """cpy_r_b = PyDict_SetItem(cpy_r_d, cpy_r_o, cpy_r_o2) >= 0;""")

    def test_dict_update(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, PrimitiveOp.DICT_UPDATE, [self.d, self.o], 1),
                        """cpy_r_b = PyDict_Update(cpy_r_d, cpy_r_o) != -1;""")

    def test_new_dict(self) -> None:
        self.assert_emit(PrimitiveOp(self.d, PrimitiveOp.NEW_DICT, [], 1),
                         """cpy_r_d = PyDict_New();""")

    def test_dict_contains(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, PrimitiveOp.DICT_CONTAINS, [self.o, self.d], 1),
                         """int __tmp1 = PyDict_Contains(cpy_r_d, cpy_r_o);
                            if (__tmp1 < 0)
                                abort();
                            cpy_r_b = __tmp1;
                         """)

    def assert_emit(self, op: Op, expected: str) -> None:
        self.emitter.fragments = []
        self.declarations.fragments = []
        op.accept(self.visitor)
        frags = self.declarations.fragments + self.emitter.fragments
        actual_lines = [line.strip(' ') for line in frags]
        assert all(line.endswith('\n') for line in actual_lines)
        actual_lines = [line.rstrip('\n') for line in actual_lines]
        expected_lines = expected.rstrip().split('\n')
        expected_lines = [line.strip(' ') for line in expected_lines]
        assert_string_arrays_equal(expected_lines, actual_lines,
                                   msg='Generated code unexpected')


class TestGenerateFunction(unittest.TestCase):
    def setUp(self) -> None:
        self.var = Var('arg')
        self.arg = RuntimeArg('arg', int_rprimitive)
        self.env = Environment()
        self.reg = self.env.add_local(self.var, int_rprimitive)
        self.block = BasicBlock(Label(0))

    def test_simple(self) -> None:
        self.block.ops.append(Return(self.reg))
        fn = FuncIR('myfunc', None, [self.arg], int_rprimitive, [self.block], self.env)
        emitter = Emitter(EmitterContext())
        generate_native_function(fn, emitter, 'prog.py')
        result = emitter.fragments
        assert_string_arrays_equal(
            [
                'static CPyTagged CPyDef_myfunc(CPyTagged cpy_r_arg) {\n',
                'CPyL0: ;\n',
                '    return cpy_r_arg;\n',
                '}\n',
            ],
            result, msg='Generated code invalid')

    def test_register(self) -> None:
        self.temp = self.env.add_temp(int_rprimitive)
        self.block.ops.append(LoadInt(self.temp, 5))
        fn = FuncIR('myfunc', None, [self.arg], list_rprimitive, [self.block], self.env)
        emitter = Emitter(EmitterContext())
        generate_native_function(fn, emitter, 'prog.py')
        result = emitter.fragments
        assert_string_arrays_equal(
            [
                'static PyObject *CPyDef_myfunc(CPyTagged cpy_r_arg) {\n',
                '    CPyTagged cpy_r_r0;\n',
                'CPyL0: ;\n',
                '    cpy_r_r0 = 10;\n',
                '}\n',
            ],
            result, msg='Generated code invalid')
