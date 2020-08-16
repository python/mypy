import unittest

from typing import Dict

from mypy.ordered_dict import OrderedDict

from mypy.nodes import Var
from mypy.test.helpers import assert_string_arrays_equal

from mypyc.ir.ops import (
    Environment, BasicBlock, Goto, Return, LoadInt, Assign, IncRef, DecRef, Branch,
    Call, Unbox, Box, TupleGet, GetAttr, PrimitiveOp, RegisterOp,
    SetAttr, Op, Value, CallC, BinaryIntOp, LoadMem, GetElementPtr, LoadAddress
)
from mypyc.ir.rtypes import (
    RTuple, RInstance, int_rprimitive, bool_rprimitive, list_rprimitive,
    dict_rprimitive, object_rprimitive, c_int_rprimitive, short_int_rprimitive, int32_rprimitive,
    int64_rprimitive, RStruct, pointer_rprimitive
)
from mypyc.ir.func_ir import FuncIR, FuncDecl, RuntimeArg, FuncSignature
from mypyc.ir.class_ir import ClassIR
from mypyc.irbuild.vtable import compute_vtable
from mypyc.codegen.emit import Emitter, EmitterContext
from mypyc.codegen.emitfunc import generate_native_function, FunctionEmitterVisitor
from mypyc.primitives.registry import binary_ops, c_binary_ops
from mypyc.primitives.misc_ops import none_object_op
from mypyc.primitives.list_ops import (
    list_get_item_op, list_set_item_op, new_list_op, list_append_op
)
from mypyc.primitives.dict_ops import (
    dict_new_op, dict_update_op, dict_get_item_op, dict_set_item_op
)
from mypyc.primitives.int_ops import int_neg_op
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
        self.s1 = self.env.add_local(Var('s1'), short_int_rprimitive)
        self.s2 = self.env.add_local(Var('s2'), short_int_rprimitive)
        self.i32 = self.env.add_local(Var('i32'), int32_rprimitive)
        self.i32_1 = self.env.add_local(Var('i32_1'), int32_rprimitive)
        self.i64 = self.env.add_local(Var('i64'), int64_rprimitive)
        self.i64_1 = self.env.add_local(Var('i64_1'), int64_rprimitive)
        self.ptr = self.env.add_local(Var('ptr'), pointer_rprimitive)
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

        const_int_regs = {}  # type: Dict[str, int]
        self.visitor = FunctionEmitterVisitor(self.emitter, self.declarations, 'prog.py', 'prog',
                                              const_int_regs)

    def test_goto(self) -> None:
        self.assert_emit(Goto(BasicBlock(2)),
                         "goto CPyL2;")

    def test_return(self) -> None:
        self.assert_emit(Return(self.m),
                         "return cpy_r_m;")

    def test_load_int(self) -> None:
        self.assert_emit(LoadInt(5),
                         "cpy_r_i0 = 10;")
        self.assert_emit(LoadInt(5, -1, c_int_rprimitive),
                         "cpy_r_i1 = 5;")

    def test_tuple_get(self) -> None:
        self.assert_emit(TupleGet(self.t, 1, 0), 'cpy_r_r0 = cpy_r_t.f1;')

    def test_load_None(self) -> None:
        self.assert_emit(PrimitiveOp([], none_object_op, 0), "cpy_r_r0 = Py_None;")

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

    def test_int_neg(self) -> None:
        self.assert_emit(CallC(int_neg_op.c_function_name, [self.m], int_neg_op.return_type,
                               int_neg_op.steals, int_neg_op.error_kind, 55),
                         "cpy_r_r0 = CPyTagged_Negate(cpy_r_m);")

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
        self.assert_emit(CallC(list_get_item_op.c_function_name, [self.m, self.k],
                               list_get_item_op.return_type, list_get_item_op.steals,
                               list_get_item_op.error_kind, 55),
                         """cpy_r_r0 = CPyList_GetItem(cpy_r_m, cpy_r_k);""")

    def test_list_set_item(self) -> None:
        self.assert_emit(CallC(list_set_item_op.c_function_name, [self.l, self.n, self.o],
                               list_set_item_op.return_type, list_set_item_op.steals,
                               list_set_item_op.error_kind, 55),
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
        self.assert_emit(CallC(list_append_op.c_function_name, [self.l, self.o],
                               list_append_op.return_type, list_append_op.steals,
                               list_append_op.error_kind, 1),
                         """cpy_r_r0 = PyList_Append(cpy_r_l, cpy_r_o);""")

    def test_get_attr(self) -> None:
        self.assert_emit(
            GetAttr(self.r, 'y', 1),
            """cpy_r_r0 = ((mod___AObject *)cpy_r_r)->_y;
               if (unlikely(((mod___AObject *)cpy_r_r)->_y == CPY_INT_TAG)) {
                   PyErr_SetString(PyExc_AttributeError, "attribute 'y' of 'A' undefined");
               } else {
                   CPyTagged_IncRef(((mod___AObject *)cpy_r_r)->_y);
               }
            """)

    def test_set_attr(self) -> None:
        self.assert_emit(
            SetAttr(self.r, 'y', self.m, 1),
            """if (((mod___AObject *)cpy_r_r)->_y != CPY_INT_TAG) {
                   CPyTagged_DecRef(((mod___AObject *)cpy_r_r)->_y);
               }
               ((mod___AObject *)cpy_r_r)->_y = cpy_r_m;
               cpy_r_r0 = 1;
            """)

    def test_dict_get_item(self) -> None:
        self.assert_emit(CallC(dict_get_item_op.c_function_name, [self.d, self.o2],
                               dict_get_item_op.return_type, dict_get_item_op.steals,
                               dict_get_item_op.error_kind, 1),
                         """cpy_r_r0 = CPyDict_GetItem(cpy_r_d, cpy_r_o2);""")

    def test_dict_set_item(self) -> None:
        self.assert_emit(CallC(dict_set_item_op.c_function_name, [self.d, self.o, self.o2],
                               dict_set_item_op.return_type, dict_set_item_op.steals,
                               dict_set_item_op.error_kind, 1),
                        """cpy_r_r0 = CPyDict_SetItem(cpy_r_d, cpy_r_o, cpy_r_o2);""")

    def test_dict_update(self) -> None:
        self.assert_emit(CallC(dict_update_op.c_function_name, [self.d, self.o],
                               dict_update_op.return_type, dict_update_op.steals,
                               dict_update_op.error_kind, 1),
                        """cpy_r_r0 = CPyDict_Update(cpy_r_d, cpy_r_o);""")

    def test_new_dict(self) -> None:
        self.assert_emit(CallC(dict_new_op.c_function_name, [], dict_new_op.return_type,
                               dict_new_op.steals, dict_new_op.error_kind, 1),
                         """cpy_r_r0 = PyDict_New();""")

    def test_dict_contains(self) -> None:
        self.assert_emit_binary_op(
            'in', self.b, self.o, self.d,
            """cpy_r_r0 = PyDict_Contains(cpy_r_d, cpy_r_o);""")

    def test_binary_int_op(self) -> None:
        # signed
        self.assert_emit(BinaryIntOp(bool_rprimitive, self.s1, self.s2, BinaryIntOp.SLT, 1),
                         """cpy_r_r0 = (Py_ssize_t)cpy_r_s1 < (Py_ssize_t)cpy_r_s2;""")
        self.assert_emit(BinaryIntOp(bool_rprimitive, self.i32, self.i32_1, BinaryIntOp.SLT, 1),
                         """cpy_r_r00 = cpy_r_i32 < cpy_r_i32_1;""")
        self.assert_emit(BinaryIntOp(bool_rprimitive, self.i64, self.i64_1, BinaryIntOp.SLT, 1),
                         """cpy_r_r01 = cpy_r_i64 < cpy_r_i64_1;""")
        # unsigned
        self.assert_emit(BinaryIntOp(bool_rprimitive, self.s1, self.s2, BinaryIntOp.ULT, 1),
                         """cpy_r_r02 = cpy_r_s1 < cpy_r_s2;""")
        self.assert_emit(BinaryIntOp(bool_rprimitive, self.i32, self.i32_1, BinaryIntOp.ULT, 1),
                         """cpy_r_r03 = (uint32_t)cpy_r_i32 < (uint32_t)cpy_r_i32_1;""")
        self.assert_emit(BinaryIntOp(bool_rprimitive, self.i64, self.i64_1, BinaryIntOp.ULT, 1),
                         """cpy_r_r04 = (uint64_t)cpy_r_i64 < (uint64_t)cpy_r_i64_1;""")

    def test_load_mem(self) -> None:
        self.assert_emit(LoadMem(bool_rprimitive, self.ptr, None),
                         """cpy_r_r0 = *(char *)cpy_r_ptr;""")
        self.assert_emit(LoadMem(bool_rprimitive, self.ptr, self.s1),
                         """cpy_r_r00 = *(char *)cpy_r_ptr;""")

    def test_get_element_ptr(self) -> None:
        r = RStruct("Foo", ["b", "i32", "i64"], [bool_rprimitive,
                                                 int32_rprimitive, int64_rprimitive])
        self.assert_emit(GetElementPtr(self.o, r, "b"),
                        """cpy_r_r0 = (CPyPtr)&((Foo *)cpy_r_o)->b;""")
        self.assert_emit(GetElementPtr(self.o, r, "i32"),
                        """cpy_r_r00 = (CPyPtr)&((Foo *)cpy_r_o)->i32;""")
        self.assert_emit(GetElementPtr(self.o, r, "i64"),
                        """cpy_r_r01 = (CPyPtr)&((Foo *)cpy_r_o)->i64;""")

    def test_load_address(self) -> None:
        self.assert_emit(LoadAddress(object_rprimitive, "PyDict_Type"),
                         """cpy_r_r0 = (PyObject *)&PyDict_Type;""")

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
        # TODO: merge this
        if op in c_binary_ops:
            c_ops = c_binary_ops[op]
            for c_desc in c_ops:
                if (is_subtype(left.type, c_desc.arg_types[0])
                        and is_subtype(right.type, c_desc.arg_types[1])):
                    args = [left, right]
                    if c_desc.ordering is not None:
                        args = [args[i] for i in c_desc.ordering]
                    self.assert_emit(CallC(c_desc.c_function_name, args, c_desc.return_type,
                                           c_desc.steals, c_desc.error_kind, 55), expected)
                    return
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
        generate_native_function(fn, emitter, 'prog.py', 'prog', optimize_int=False)
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
        generate_native_function(fn, emitter, 'prog.py', 'prog', optimize_int=False)
        result = emitter.fragments
        assert_string_arrays_equal(
            [
                'PyObject *CPyDef_myfunc(CPyTagged cpy_r_arg) {\n',
                '    CPyTagged cpy_r_i0;\n',
                'CPyL0: ;\n',
                '    cpy_r_i0 = 10;\n',
                '}\n',
            ],
            result, msg='Generated code invalid')
