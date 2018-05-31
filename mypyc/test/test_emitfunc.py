import unittest

from mypy.nodes import Var
from mypy.test.helpers import assert_string_arrays_equal

from mypyc.ops import (
    Environment, BasicBlock, FuncIR, RuntimeArg, RType, Goto, Return, LoadInt, Assign,
    IncRef, DecRef, Branch, Call, Unbox, Box, RTuple, TupleGet, GetAttr, PrimitiveOp,
    ClassIR, RInstance, SetAttr, Op, Label, Register, int_rprimitive, bool_rprimitive,
    list_rprimitive, dict_rprimitive, object_rprimitive
)
from mypyc.emit import Emitter, EmitterContext
from mypyc.emitfunc import generate_native_function, FunctionEmitterVisitor
from mypyc.ops_primitive import binary_ops
from mypyc.ops_misc import none_op, true_op, false_op
from mypyc.ops_list import (
    list_len_op, list_get_item_op, list_set_item_op, new_list_op, list_append_op
)
from mypyc.ops_dict import new_dict_op, dict_update_op, dict_get_item_op, dict_set_item_op
from mypyc.ops_int import int_neg_op
from mypyc.subtype import is_subtype


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
        self.assert_emit(PrimitiveOp(self.m, [], none_op, 0),
                         """cpy_r_m = Py_None;
                            Py_INCREF(cpy_r_m);
                         """)

    def test_load_True(self) -> None:
        self.assert_emit(PrimitiveOp(self.m, [], true_op, 0), "cpy_r_m = 1;")

    def test_load_False(self) -> None:
        self.assert_emit(PrimitiveOp(self.m, [], false_op, 0), "cpy_r_m = 0;")

    def test_assign_int(self) -> None:
        self.assert_emit(Assign(self.m, self.n),
                         "cpy_r_m = cpy_r_n;")

    def test_int_add(self) -> None:
        self.assert_emit_binary_op(
            '+', self.n, self.m, self.k,
            "cpy_r_n = CPyTagged_Add(cpy_r_m, cpy_r_k);")

    def test_int_sub(self) -> None:
        self.assert_emit_binary_op(
            '-', self.n, self.m, self.k,
            "cpy_r_n = CPyTagged_Subtract(cpy_r_m, cpy_r_k);")

    def test_list_repeat(self) -> None:
        self.assert_emit_binary_op(
            '*', self.ll, self.l, self.n,
             """long long __tmp1;
                __tmp1 = CPyTagged_AsLongLong(cpy_r_n);
                if (__tmp1 == -1 && PyErr_Occurred())
                    CPyError_OutOfMemory();
                cpy_r_ll = PySequence_Repeat(cpy_r_l, __tmp1);
             """)

    def test_int_neg(self) -> None:
        self.assert_emit(PrimitiveOp(self.n, [self.m], int_neg_op, 55),
                         "cpy_r_n = CPyTagged_Negate(cpy_r_m);")

    def test_list_len(self) -> None:
        self.assert_emit(PrimitiveOp(self.n, [self.l], list_len_op, 55),
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
        self.assert_emit(PrimitiveOp(self.n, [self.m, self.k], list_get_item_op, 55),
                         """cpy_r_n = CPyList_GetItem(cpy_r_m, cpy_r_k);""")

    def test_list_set_item(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, [self.l, self.n, self.o], list_set_item_op, 55),
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
        self.assert_emit(PrimitiveOp(self.l, [self.n, self.m], new_list_op, 55),
                         """cpy_r_l = PyList_New(2);
                            Py_INCREF(cpy_r_n);
                            Py_INCREF(cpy_r_m);
                            if (cpy_r_l != NULL) {
                                PyList_SET_ITEM(cpy_r_l, 0, cpy_r_n);
                                PyList_SET_ITEM(cpy_r_l, 1, cpy_r_m);
                            }
                         """)

    def test_list_append(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, [self.l, self.o], list_append_op, 1),
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
        self.assert_emit(PrimitiveOp(self.o, [self.d, self.o2], dict_get_item_op, 1),
                         """cpy_r_o = PyDict_GetItemWithError(cpy_r_d, cpy_r_o2);
                            if (!cpy_r_o)
                                PyErr_SetObject(PyExc_KeyError, cpy_r_o2);
                            else
                                Py_INCREF(cpy_r_o);
                         """)

    def test_dict_set_item(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, [self.d, self.o, self.o2], dict_set_item_op, 1),
                         """cpy_r_b = PyDict_SetItem(cpy_r_d, cpy_r_o, cpy_r_o2) >= 0;""")

    def test_dict_update(self) -> None:
        self.assert_emit(PrimitiveOp(self.b, [self.d, self.o], dict_update_op, 1),
                        """cpy_r_b = PyDict_Update(cpy_r_d, cpy_r_o) != -1;""")

    def test_new_dict(self) -> None:
        self.assert_emit(PrimitiveOp(self.d, [], new_dict_op, 1),
                         """cpy_r_d = PyDict_New();""")

    def test_dict_contains(self) -> None:
        self.assert_emit_binary_op(
            'in', self.b, self.o, self.d,
             """int __tmp1 = PyDict_Contains(cpy_r_d, cpy_r_o);
                if (__tmp1 < 0)
                    cpy_r_b = 2;
                else
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

    def assert_emit_binary_op(self,
                              op: str,
                              dest: Register,
                              left: Register,
                              right: Register,
                              expected: str) -> None:
        ops = binary_ops[op]
        left_type = self.env.types[left]
        right_type = self.env.types[right]
        for desc in ops:
            if (is_subtype(left_type, desc.arg_types[0])
                    and is_subtype(right_type, desc.arg_types[1])):
                self.assert_emit(PrimitiveOp(dest, [left, right], desc, 55), expected)
                break
        else:
            assert False, 'Could not find matching op'


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
