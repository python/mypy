import unittest

from collections import OrderedDict

from mypy.nodes import Var
from mypy.test.helpers import assert_string_arrays_equal

from mypyc.ops import (
    Environment, BasicBlock, FuncIR, RuntimeArg, Goto, Return, LoadInt, Assign,
    IncRef, DecRef, Branch, Call, Unbox, Box, RTuple, TupleGet, GetAttr, PrimitiveOp,
    RegisterOp, FuncDecl,
    ClassIR, RInstance, SetAttr, Op, Value, int_rprimitive, bool_rprimitive,
    list_rprimitive, dict_rprimitive, object_rprimitive, FuncSignature,
)
from mypyc.genopsvtable import compute_vtable
from mypyc.emit import Emitter, EmitterContext
from mypyc.emitfunc import generate_native_function, FunctionEmitterVisitor
from mypyc.ops_primitive import binary_ops
from mypyc.ops_misc import none_object_op, true_op, false_op
from mypyc.ops_list import (
    list_len_op, list_get_item_op, list_set_item_op, new_list_op, list_append_op
)
from mypyc.ops_dict import new_dict_op, dict_update_op, dict_get_item_op, dict_set_item_op
from mypyc.ops_int import int_neg_op
from mypyc.subtype import is_subtype
from mypyc.namegen import NameGenerator


class TestFunctionEmitterVisitor(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Environment()
        self.n = self.env.add_local(Var('n'), int_rprimitive)
        self.m = self.env.add_local(Var('m'), int_rprimitive)
        self.k = self.env.add_local(Var('k'), int_rprimitive)
        self.l = self.env.add_local(Var('l'), list_rprimitive)  # noqa
        self.ll = self.env.add_local(Var('ll'), list_rprimitive)
        self.o = self.env.add_local(Var('o'), object_rprimitive)
        self.o2 = self.env.add_local(Var('o2'), object_rprimitive)
        self.d = self.env.add_local(Var('d'), dict_rprimitive)
        self.b = self.env.add_local(Var('b'), bool_rprimitive)
        self.t = self.env.add_local(Var('t'), RTuple([int_rprimitive, bool_rprimitive]))
        self.tt = self.env.add_local(
            Var('tt'),
            RTuple([RTuple([int_rprimitive, bool_rprimitive]), bool_rprimitive]))
        ir = ClassIR('A', 'mod')
        ir.attributes = OrderedDict([('x', bool_rprimitive), ('y', int_rprimitive)])
        compute_vtable(ir)
        ir.mro = [ir]
        self.r = self.env.add_local(Var('r'), RInstance(ir))

        self.context = EmitterContext(NameGenerator([['mod']]))
        self.emitter = Emitter(self.context, self.env)
        self.declarations = Emitter(self.context, self.env)
        self.visitor = FunctionEmitterVisitor(self.emitter, self.declarations, 'prog.py', 'prog')

    def test_goto(self) -> None:
        self.assert_emit(Goto(BasicBlock(2)),
                         "goto CPyL2;")

    def test_return(self) -> None:
        self.assert_emit(Return(self.m),
                         "return cpy_r_m;")

    def test_load_int(self) -> None:
        self.assert_emit(LoadInt(5),
                         "cpy_r_r0 = 10;")

    def test_tuple_get(self) -> None:
        self.assert_emit(TupleGet(self.t, 1, 0), 'cpy_r_r0 = cpy_r_t.f1;')

    def test_load_None(self) -> None:
        self.assert_emit(PrimitiveOp([], none_object_op, 0), "cpy_r_r0 = Py_None;")

    def test_load_True(self) -> None:
        self.assert_emit(PrimitiveOp([], true_op, 0), "cpy_r_r0 = 1;")

    def test_load_False(self) -> None:
        self.assert_emit(PrimitiveOp([], false_op, 0), "cpy_r_r0 = 0;")

    def test_assign_int(self) -> None:
        self.assert_emit(Assign(self.m, self.n),
                         "cpy_r_m = cpy_r_n;")

    def test_int_add(self) -> None:
        self.assert_emit_binary_op(
            '+', self.n, self.m, self.k,
            "cpy_r_r0 = CPyTagged_Add(cpy_r_m, cpy_r_k);")

    def test_int_sub(self) -> None:
        self.assert_emit_binary_op(
            '-', self.n, self.m, self.k,
            "cpy_r_r0 = CPyTagged_Subtract(cpy_r_m, cpy_r_k);")

    def test_list_repeat(self) -> None:
        self.assert_emit_binary_op(
            '*', self.ll, self.l, self.n,
            """Py_ssize_t __tmp1;
               __tmp1 = CPyTagged_AsSsize_t(cpy_r_n);
               if (__tmp1 == -1 && PyErr_Occurred())
                   CPyError_OutOfMemory();
               cpy_r_r0 = PySequence_Repeat(cpy_r_l, __tmp1);
            """)

    def test_int_neg(self) -> None:
        self.assert_emit(PrimitiveOp([self.m], int_neg_op, 55),
                         "cpy_r_r0 = CPyTagged_Negate(cpy_r_m);")

    def test_list_len(self) -> None:
        self.assert_emit(PrimitiveOp([self.l], list_len_op, 55),
                         """Py_ssize_t __tmp1;
                            __tmp1 = PyList_GET_SIZE(cpy_r_l);
                            cpy_r_r0 = CPyTagged_ShortFromSsize_t(__tmp1);
                         """)

    def test_branch(self) -> None:
        self.assert_emit(Branch(self.b, BasicBlock(8), BasicBlock(9), Branch.BOOL_EXPR),
                         """if (cpy_r_b) {
                                goto CPyL8;
                            } else
                                goto CPyL9;
                         """)
        b = Branch(self.b, BasicBlock(8), BasicBlock(9), Branch.BOOL_EXPR)
        b.negated = True
        self.assert_emit(b,
                         """if (!cpy_r_b) {
                                goto CPyL8;
                            } else
                                goto CPyL9;
                         """)

    def test_call(self) -> None:
        decl = FuncDecl('myfn', None, 'mod',
                        FuncSignature([RuntimeArg('m', int_rprimitive)], int_rprimitive))
        self.assert_emit(Call(decl, [self.m], 55),
                         "cpy_r_r0 = CPyDef_myfn(cpy_r_m);")

    def test_call_two_args(self) -> None:
        decl = FuncDecl('myfn', None, 'mod',
                        FuncSignature([RuntimeArg('m', int_rprimitive),
                                       RuntimeArg('n', int_rprimitive)],
                                      int_rprimitive))
        self.assert_emit(Call(decl, [self.m, self.k], 55),
                         "cpy_r_r0 = CPyDef_myfn(cpy_r_m, cpy_r_k);")

    def test_inc_ref(self) -> None:
        self.assert_emit(IncRef(self.m),
                         "CPyTagged_IncRef(cpy_r_m);")

    def test_dec_ref(self) -> None:
        self.assert_emit(DecRef(self.m),
                         "CPyTagged_DecRef(cpy_r_m);")

    def test_dec_ref_tuple(self) -> None:
        self.assert_emit(DecRef(self.t), 'CPyTagged_DecRef(cpy_r_t.f0);')

    def test_dec_ref_tuple_nested(self) -> None:
        self.assert_emit(DecRef(self.tt), 'CPyTagged_DecRef(cpy_r_tt.f0.f0);')

    def test_list_get_item(self) -> None:
        self.assert_emit(PrimitiveOp([self.m, self.k], list_get_item_op, 55),
                         """cpy_r_r0 = CPyList_GetItem(cpy_r_m, cpy_r_k);""")

    def test_list_set_item(self) -> None:
        self.assert_emit(PrimitiveOp([self.l, self.n, self.o], list_set_item_op, 55),
                         """cpy_r_r0 = CPyList_SetItem(cpy_r_l, cpy_r_n, cpy_r_o);""")

    def test_box(self) -> None:
        self.assert_emit(Box(self.n),
                         """cpy_r_r0 = CPyTagged_StealAsObject(cpy_r_n);""")

    def test_unbox(self) -> None:
        self.assert_emit(Unbox(self.m, int_rprimitive, 55),
                         """if (likely(PyLong_Check(cpy_r_m)))
                                cpy_r_r0 = CPyTagged_FromObject(cpy_r_m);
                            else {
                                CPy_TypeError("int", cpy_r_m);
                                cpy_r_r0 = CPY_INT_TAG;
                            }
                         """)

    def test_new_list(self) -> None:
        self.assert_emit(PrimitiveOp([self.n, self.m], new_list_op, 55),
                         """cpy_r_r0 = PyList_New(2);
                            if (likely(cpy_r_r0 != NULL)) {
                                PyList_SET_ITEM(cpy_r_r0, 0, cpy_r_n);
                                PyList_SET_ITEM(cpy_r_r0, 1, cpy_r_m);
                            }
                         """)

    def test_list_append(self) -> None:
        self.assert_emit(PrimitiveOp([self.l, self.o], list_append_op, 1),
                         """cpy_r_r0 = PyList_Append(cpy_r_l, cpy_r_o) >= 0;""")

    def test_get_attr(self) -> None:
        self.assert_emit(
            GetAttr(self.r, 'y', 1),
            """cpy_r_r0 = native_A_gety((mod___AObject *)cpy_r_r); /* y */""")

    def test_set_attr(self) -> None:
        self.assert_emit(
            SetAttr(self.r, 'y', self.m, 1),
            "cpy_r_r0 = native_A_sety((mod___AObject *)cpy_r_r, cpy_r_m); /* y */")

    def test_dict_get_item(self) -> None:
        self.assert_emit(PrimitiveOp([self.d, self.o2], dict_get_item_op, 1),
                         """cpy_r_r0 = CPyDict_GetItem(cpy_r_d, cpy_r_o2);""")

    def test_dict_set_item(self) -> None:
        self.assert_emit(PrimitiveOp([self.d, self.o, self.o2], dict_set_item_op, 1),
                         """cpy_r_r0 = CPyDict_SetItem(cpy_r_d, cpy_r_o, cpy_r_o2) >= 0;""")

    def test_dict_update(self) -> None:
        self.assert_emit(PrimitiveOp([self.d, self.o], dict_update_op, 1),
                        """cpy_r_r0 = CPyDict_Update(cpy_r_d, cpy_r_o) >= 0;""")

    def test_new_dict(self) -> None:
        self.assert_emit(PrimitiveOp([], new_dict_op, 1),
                         """cpy_r_r0 = PyDict_New();""")

    def test_dict_contains(self) -> None:
        self.assert_emit_binary_op(
            'in', self.b, self.o, self.d,
            """int __tmp1 = PyDict_Contains(cpy_r_d, cpy_r_o);
               if (__tmp1 < 0)
                   cpy_r_r0 = 2;
               else
                   cpy_r_r0 = __tmp1;
            """)

    def assert_emit(self, op: Op, expected: str) -> None:
        self.emitter.fragments = []
        self.declarations.fragments = []
        self.env.temp_index = 0
        if isinstance(op, RegisterOp):
            self.env.add_op(op)
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
                              dest: Value,
                              left: Value,
                              right: Value,
                              expected: str) -> None:
        ops = binary_ops[op]
        for desc in ops:
            if (is_subtype(left.type, desc.arg_types[0])
                    and is_subtype(right.type, desc.arg_types[1])):
                self.assert_emit(PrimitiveOp([left, right], desc, 55), expected)
                break
        else:
            assert False, 'Could not find matching op'


class TestGenerateFunction(unittest.TestCase):
    def setUp(self) -> None:
        self.var = Var('arg')
        self.arg = RuntimeArg('arg', int_rprimitive)
        self.env = Environment()
        self.reg = self.env.add_local(self.var, int_rprimitive)
        self.block = BasicBlock(0)

    def test_simple(self) -> None:
        self.block.ops.append(Return(self.reg))
        fn = FuncIR(FuncDecl('myfunc', None, 'mod', FuncSignature([self.arg], int_rprimitive)),
                    [self.block], self.env)
        emitter = Emitter(EmitterContext(NameGenerator([['mod']])))
        generate_native_function(fn, emitter, 'prog.py', 'prog')
        result = emitter.fragments
        assert_string_arrays_equal(
            [
                'CPyTagged CPyDef_myfunc(CPyTagged cpy_r_arg) {\n',
                'CPyL0: ;\n',
                '    return cpy_r_arg;\n',
                '}\n',
            ],
            result, msg='Generated code invalid')

    def test_register(self) -> None:
        self.env.temp_index = 0
        op = LoadInt(5)
        self.block.ops.append(op)
        self.env.add_op(op)
        fn = FuncIR(FuncDecl('myfunc', None, 'mod', FuncSignature([self.arg], list_rprimitive)),
                    [self.block], self.env)
        emitter = Emitter(EmitterContext(NameGenerator([['mod']])))
        generate_native_function(fn, emitter, 'prog.py', 'prog')
        result = emitter.fragments
        assert_string_arrays_equal(
            [
                'PyObject *CPyDef_myfunc(CPyTagged cpy_r_arg) {\n',
                '    CPyTagged cpy_r_r0;\n',
                'CPyL0: ;\n',
                '    cpy_r_r0 = 10;\n',
                '}\n',
            ],
            result, msg='Generated code invalid')
