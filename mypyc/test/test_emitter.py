import unittest

from mypy.nodes import Var
from mypy.test.helpers import assert_string_arrays_equal

from mypyc.ops import (
    Environment, BasicBlock, FuncIR, RuntimeArg, RTType, Goto, Return, LoadInt, Assign,
    PrimitiveOp, IncRef, DecRef, Branch, Call, Unbox, Box, TupleRTType, TupleGet, GetAttr,
    ClassIR, UserRTType, SetAttr
)
from mypyc.emitter import (
    EmitterVisitor,
    Emitter,
    CodeGenerator,
)


class TestEmitter(unittest.TestCase):
    def setUp(self):
        self.env = Environment()
        self.n = self.env.add_local(Var('n'), RTType('int'))
        self.emitter = Emitter(self.env)

    def test_label(self):
        assert self.emitter.label(4) == 'CPyL4'

    def test_reg(self):
        assert self.emitter.reg(self.n) == 'cpy_r_n'

    def test_emit_line(self):
        self.emitter.emit_line('line;')
        self.emitter.emit_line('a', indent=0)
        self.emitter.emit_line('b', indent=8)
        assert self.emitter.fragments == ['    line;\n',
                                          'a\n',
                                          '        b\n']


class TestEmitterVisitor(unittest.TestCase):
    def setUp(self):
        self.env = Environment()
        self.n = self.env.add_local(Var('n'), RTType('int'))
        self.m = self.env.add_local(Var('m'), RTType('int'))
        self.k = self.env.add_local(Var('k'), RTType('int'))
        self.l = self.env.add_local(Var('l'), RTType('list'))
        self.ll = self.env.add_local(Var('ll'), RTType('list'))
        self.o = self.env.add_local(Var('o'), RTType('object'))
        self.emitter = Emitter(self.env)
        self.declarations = Emitter(self.env)
        self.visitor = EmitterVisitor(self.emitter, self.declarations, CodeGenerator())

    def test_goto(self):
        self.assert_emit(Goto(2),
                         "goto CPyL2;")

    def test_return(self):
        self.assert_emit(Return(self.m),
                         "return cpy_r_m;")

    def test_load_int(self):
        self.assert_emit(LoadInt(self.m, 5),
                         "cpy_r_m = 10;")

    def test_tuple_get(self):
        self.assert_emit(TupleGet(self.m, self.n, 1, RTType('bool')), 'cpy_r_m = cpy_r_n.f1;')

    def test_load_None(self):
        self.assert_emit(PrimitiveOp(self.m, PrimitiveOp.NONE),
                         """cpy_r_m = Py_None;
                            Py_INCREF(cpy_r_m);
                         """)

    def test_load_True(self):
        self.assert_emit(PrimitiveOp(self.m, PrimitiveOp.TRUE), "cpy_r_m = 1;")

    def test_load_False(self):
        self.assert_emit(PrimitiveOp(self.m, PrimitiveOp.FALSE), "cpy_r_m = 0;")

    def test_assign_int(self):
        self.assert_emit(Assign(self.m, self.n),
                         "cpy_r_m = cpy_r_n;")

    def test_int_add(self):
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.INT_ADD, self.m, self.k),
                         "cpy_r_n = CPyTagged_Add(cpy_r_m, cpy_r_k);")

    def test_int_sub(self):
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.INT_SUB, self.m, self.k),
                         "cpy_r_n = CPyTagged_Subtract(cpy_r_m, cpy_r_k);")

    def test_list_repeat(self):
        self.assert_emit(PrimitiveOp(self.ll, PrimitiveOp.LIST_REPEAT, self.l, self.n),
                         """long long __tmp1;
                            __tmp1 = CPyTagged_AsLongLong(cpy_r_n);
                            if (__tmp1 == -1 && PyErr_Occurred())
                                abort();
                            cpy_r_ll = PySequence_Repeat(cpy_r_l, __tmp1);
                            if (!cpy_r_ll)
                                abort();
                         """)

    def test_int_neg(self):
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.INT_NEG, self.m),
                         "cpy_r_n = CPy_NegateInt(cpy_r_m);")

    def test_list_len(self):
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.LIST_LEN, self.l),
                         """long long __tmp1;
                            __tmp1 = PyList_GET_SIZE(cpy_r_l);
                            cpy_r_n = CPyTagged_ShortFromLongLong(__tmp1);
                         """)

    def test_branch_eq(self):
        self.assert_emit(Branch(self.n, self.m, 8, 9, Branch.INT_EQ),
                         """if (CPyTagged_IsEq(cpy_r_n, cpy_r_m))
                                goto CPyL8;
                            else
                                goto CPyL9;
                         """)
        b = Branch(self.n, self.m, 8, 9, Branch.INT_LT)
        b.negated = True
        self.assert_emit(b,
                         """if (!CPyTagged_IsLt(cpy_r_n, cpy_r_m))
                                goto CPyL8;
                            else
                                goto CPyL9;
                         """)

    def test_call(self):
        self.assert_emit(Call(self.n, 'myfn', [self.m]),
                         "cpy_r_n = CPyDef_myfn(cpy_r_m);")

    def test_call_two_args(self):
        self.assert_emit(Call(self.n, 'myfn', [self.m, self.k]),
                         "cpy_r_n = CPyDef_myfn(cpy_r_m, cpy_r_k);")

    def test_call_no_return(self):
        self.assert_emit(Call(None, 'myfn', [self.m, self.k]),
                         "CPyDef_myfn(cpy_r_m, cpy_r_k);")

    def test_inc_ref(self):
        self.assert_emit(IncRef(self.m, RTType('int')),
                         "CPyTagged_IncRef(cpy_r_m);")

    def test_dec_ref(self):
        self.assert_emit(DecRef(self.m, RTType('int')),
                         "CPyTagged_DecRef(cpy_r_m);")

    def test_dec_ref_tuple(self):
        tuple_type = TupleRTType([RTType('int'), RTType('bool')])
        self.assert_emit(DecRef(self.m, tuple_type), 'CPyTagged_DecRef(cpy_r_m.f0);')

    def test_dec_ref_tuple_nested(self):
        tuple_type = TupleRTType([TupleRTType([RTType('int'), RTType('bool')]), RTType('bool')])
        self.assert_emit(DecRef(self.m, tuple_type), 'CPyTagged_DecRef(cpy_r_m.f0.f0);')

    def test_list_get_item(self):
        self.assert_emit(PrimitiveOp(self.n, PrimitiveOp.LIST_GET, self.m, self.k),
                         """cpy_r_n = CPyList_GetItem(cpy_r_m, cpy_r_k);
                            if (!cpy_r_n)
                                abort();
                         """)

    def test_list_set_item(self):
        self.assert_emit(PrimitiveOp(None, PrimitiveOp.LIST_SET, self.l, self.n, self.o),
                         """if (!CPyList_SetItem(cpy_r_l, cpy_r_n, cpy_r_o))
                                abort();
                         """)

    def test_box(self):
        self.assert_emit(Box(self.o, self.n, RTType('int')),
                         """PyObject *__tmp1 = CPyTagged_AsObject(cpy_r_n);
                            cpy_r_o = __tmp1;
                         """)

    def test_unbox(self):
        self.assert_emit(Unbox(self.n, self.m, RTType('int')),
                         """CPyTagged __tmp1;
                            if (PyLong_Check(cpy_r_m))
                                __tmp1 = CPyTagged_FromObject(cpy_r_m);
                            else
                                abort();
                            cpy_r_n = __tmp1;
                         """)

    def test_new_list(self):
        self.assert_emit(PrimitiveOp(self.l, PrimitiveOp.NEW_LIST, self.n, self.m),
                         """cpy_r_l = PyList_New(2);
                            Py_INCREF(cpy_r_n);
                            PyList_SET_ITEM(cpy_r_l, 0, cpy_r_n);
                            Py_INCREF(cpy_r_m);
                            PyList_SET_ITEM(cpy_r_l, 1, cpy_r_m);
                         """)

    def test_list_append(self):
        self.assert_emit(PrimitiveOp(None, PrimitiveOp.LIST_APPEND, self.l, self.o),
                         """if (PyList_Append(cpy_r_l, cpy_r_o) == -1)
                                abort();
                         """)

    def test_get_attr(self):
        ir = ClassIR('A', [('x', RTType('bool')),
                           ('y', RTType('int'))])
        rtype = UserRTType(ir)
        self.assert_emit(GetAttr(self.n, self.m, 'y', rtype),
                         """cpy_r_n = CPY_GET_ATTR(cpy_r_m, 2, AObject, CPyTagged);""")

    def test_set_attr(self):
        ir = ClassIR('A', [('x', RTType('bool')),
                           ('y', RTType('int'))])
        rtype = UserRTType(ir)
        self.assert_emit(SetAttr(self.n, 'y', self.m, rtype),
                         """CPY_SET_ATTR(cpy_r_n, 3, cpy_r_m, AObject, CPyTagged);""")

    def assert_emit(self, op, expected):
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
    def setUp(self):
        self.var = Var('arg')
        self.arg = RuntimeArg('arg', RTType('int'))
        self.env = Environment()
        self.id = self.env.add_local(self.var, RTType('int'))
        self.block = BasicBlock(0)
        self.code_generator = CodeGenerator()

    def test_simple(self):
        self.block.ops.append(Return(self.id))
        fn = FuncIR('myfunc', [self.arg], RTType('int'), [self.block], self.env)
        result = self.code_generator.generate_c_for_function(fn)
        assert_string_arrays_equal(
            [
                'static CPyTagged CPyDef_myfunc(CPyTagged cpy_r_arg) {\n',
                'CPyL0: ;\n',
                '    return cpy_r_arg;\n',
                '}\n',
            ],
            result, msg='Generated code invalid')

    def test_register(self):
        self.temp = self.env.add_temp(RTType('int'))
        self.block.ops.append(LoadInt(self.temp, 5))
        fn = FuncIR('myfunc', [self.arg], RTType('list'), [self.block], self.env)
        result = self.code_generator.generate_c_for_function(fn)
        assert_string_arrays_equal(
            [
                'static PyObject * CPyDef_myfunc(CPyTagged cpy_r_arg) {\n',
                '    CPyTagged cpy_r_r0;\n',
                'CPyL0: ;\n',
                '    cpy_r_r0 = 10;\n',
                '}\n',
            ],
            result, msg='Generated code invalid')


class TestArgCheck(unittest.TestCase):
    def setUp(self):
        self.code_generator = CodeGenerator()

    def test_check_list(self):
        lines = self.code_generator.generate_arg_check('x', RTType('list'))
        assert lines == [
            '    PyObject *arg_x;',
            '    if (PyList_Check(obj_x))',
            '        arg_x = obj_x;',
            '    else',
            '        return NULL;',
        ]
