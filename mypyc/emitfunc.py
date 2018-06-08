"""Code generation for native function bodies."""

from typing import Optional, List

from mypyc.common import REG_PREFIX, NATIVE_PREFIX
from mypyc.emit import Emitter
from mypyc.ops import (
    FuncIR, OpVisitor, Goto, Branch, Return, Assign, LoadInt, LoadFloat, LoadErrorValue, GetAttr,
    SetAttr, LoadStatic, TupleGet, TupleSet, Call, PyCall, PyGetAttr, IncRef, DecRef, Box, Cast,
    Unbox, Label, Value, Register, RType, RTuple, MethodCall, PyMethodCall,
    PrimitiveOp, EmitterInterface, PySetAttr, Unreachable, is_int_rprimitive
)


def native_function_type(fn: FuncIR) -> str:
    args = ', '.join(arg.type.ctype for arg in fn.args)
    ret = fn.ret_type.ctype
    return '{} (*)({})'.format(ret, args)


def native_function_header(fn: FuncIR) -> str:
    args = []
    for arg in fn.args:
        args.append('{}{}{}'.format(arg.type.ctype_spaced(), REG_PREFIX, arg.name))

    return 'static {ret_type}{prefix}{name}({args})'.format(
        ret_type=fn.ret_type.ctype_spaced(),
        prefix=NATIVE_PREFIX,
        name=fn.cname,
        args=', '.join(args) or 'void')


def generate_native_function(fn: FuncIR, emitter: Emitter, source_path: str) -> None:
    declarations = Emitter(emitter.context, fn.env)
    body = Emitter(emitter.context, fn.env)
    visitor = FunctionEmitterVisitor(body, declarations, fn.name, source_path)

    declarations.emit_line('{} {{'.format(native_function_header(fn)))
    body.indent()

    for r, i in fn.env.indexes.items():
        if i < len(fn.args):
            continue  # skip the arguments
        ctype = r.type.ctype
        declarations.emit_line('{ctype} {prefix}{name};'.format(ctype=ctype,
                                                                prefix=REG_PREFIX,
                                                                name=r.name))

    for block in fn.blocks:
        body.emit_label(block.label)
        for op in block.ops:
            op.accept(visitor)

    body.emit_line('}')

    emitter.emit_from_emitter(declarations)
    emitter.emit_from_emitter(body)


class FunctionEmitterVisitor(OpVisitor[None], EmitterInterface):
    def __init__(self,
                 emitter: Emitter,
                 declarations: Emitter,
                 func_name: str,
                 source_path: str) -> None:
        self.emitter = emitter
        self.declarations = declarations
        self.env = self.emitter.env
        self.func_name = func_name
        self.source_path = source_path

    def temp_name(self) -> str:
        return self.emitter.temp_name()

    def visit_goto(self, op: Goto) -> None:
        self.emit_line('goto %s;' % self.label(op.label))

    def visit_branch(self, op: Branch) -> None:
        neg = '!' if op.negated else ''

        cond = ''
        if op.op == Branch.BOOL_EXPR:
            expr_result = self.reg(op.left)  # right isn't used
            cond = '{}{}'.format(neg, expr_result)
        elif op.op == Branch.IS_NONE:
            compare = '!=' if op.negated else '=='
            cond = '{} {} Py_None'.format(self.reg(op.left), compare)
        elif op.op == Branch.IS_ERROR:
            typ = op.left.type
            compare = '!=' if op.negated else '=='
            if isinstance(typ, RTuple):
                # TODO: What about empty tuple?
                item_type = typ.types[0]
                cond = '{}.f0 {} {}'.format(self.reg(op.left),
                                            compare,
                                            item_type.c_error_value())
            else:
                cond = '{} {} {}'.format(self.reg(op.left),
                                         compare,
                                         typ.c_error_value())
        else:
            assert False, "Invalid branch"

        # For error checks, tell the compiler the branch is unlikely
        if op.traceback_entry is not None:
            cond = 'unlikely({})'.format(cond)

        self.emit_line('if ({}) {{'.format(cond))

        if op.traceback_entry is not None:
            self.emit_line('CPy_AddTraceback("%s", "%s", %d, _globals);' % (self.source_path,
                                                                            self.func_name,
                                                                            op.line))
        self.emit_lines(
            'goto %s;' % self.label(op.true),
            '} else',
            '    goto %s;' % self.label(op.false)
        )

    def visit_return(self, op: Return) -> None:
        regstr = self.reg(op.reg)
        self.emit_line('return %s;' % regstr)

    def visit_primitive_op(self, op: PrimitiveOp) -> None:
        args = [self.reg(arg) for arg in op.args]
        if not op.is_void:
            dest = self.reg(op)
        else:
            # This will generate a C compile error if used. The reason for this
            # is that we don't want to insert "assert dest is not None" checks
            # everywhere.
            dest = '<undefined dest>'
        op.desc.emit(self, args, dest)

    def visit_tuple_set(self, op: TupleSet) -> None:
        dest = self.reg(op)
        tuple_type = op.tuple_type
        self.emitter.declare_tuple_struct(tuple_type)
        for i, item in enumerate(op.items):
            self.emit_line('{}.f{} = {};'.format(dest, i, self.reg(item)))
        self.emit_inc_ref(dest, tuple_type)

    def visit_assign(self, op: Assign) -> None:
        dest = self.reg(op.dest)
        src = self.reg(op.src)
        self.emit_line('%s = %s;' % (dest, src))

    def visit_load_int(self, op: LoadInt) -> None:
        dest = self.reg(op)
        self.emit_line('%s = %d;' % (dest, op.value * 2))

    def visit_load_float(self, op: LoadFloat) -> None:
        dest = self.reg(op)
        self.emit_line('%s = PyFloat_FromDouble(%f);' % (dest, op.value))

    def visit_load_error_value(self, op: LoadErrorValue) -> None:
        if isinstance(op.type, RTuple):
            values = [item.c_undefined_value() for item in op.type.types]
            tmp = self.temp_name()
            self.emit_line('%s %s = { %s };' % (op.type.ctype, tmp, ', '.join(values)))
            self.emit_line('%s = %s;' % (self.reg(op), tmp))
        else:
            self.emit_line('%s = %s;' % (self.reg(op),
                                         op.type.c_error_value()))

    def visit_get_attr(self, op: GetAttr) -> None:
        dest = self.reg(op)
        obj = self.reg(op.obj)
        rtype = op.class_type
        self.emit_line('%s = CPY_GET_ATTR(%s, %d, %s, %s);' % (
            dest, obj,
            rtype.getter_index(op.attr),
            rtype.struct_name(),
            rtype.attr_type(op.attr).ctype))

    def visit_set_attr(self, op: SetAttr) -> None:
        dest = self.reg(op)
        obj = self.reg(op.obj)
        src = self.reg(op.src)
        rtype = op.class_type
        # TODO: Track errors
        self.emit_line('%s = CPY_SET_ATTR(%s, %d, %s, %s, %s);' % (
            dest,
            obj,
            rtype.setter_index(op.attr),
            src,
            rtype.struct_name(),
            rtype.attr_type(op.attr).ctype))

    def visit_load_static(self, op: LoadStatic) -> None:
        dest = self.reg(op)
        if is_int_rprimitive(op.type):
            self.emit_line('%s = CPyTagged_FromObject(%s);' % (dest, op.identifier))
        else:
            self.emit_line('%s = %s;' % (dest, op.identifier))

    def visit_py_get_attr(self, op: PyGetAttr) -> None:
        dest = self.reg(op)
        obj = self.reg(op.obj)
        self.emit_line('{} = PyObject_GetAttrString({}, "{}");'.format(dest, obj, op.attr))

    def visit_py_set_attr(self, op: PySetAttr) -> None:
        dest = self.reg(op)
        obj = self.reg(op.obj)
        value = self.reg(op.value)
        self.emit_line('{} = PyObject_SetAttrString({}, "{}", {}) >= 0;'.format(
            dest, obj, op.attr, value))

    def visit_tuple_get(self, op: TupleGet) -> None:
        dest = self.reg(op)
        src = self.reg(op.src)
        self.emit_line('{} = {}.f{};'.format(dest, src, op.index))
        self.emit_inc_ref(dest, op.type)

    def get_dest_assign(self, dest: Value) -> str:
        if not dest.is_void:
            return self.reg(dest) + ' = '
        else:
            return ''

    def visit_call(self, op: Call) -> None:
        dest = self.get_dest_assign(op)
        args = ', '.join(self.reg(arg) for arg in op.args)
        self.emit_line('%s%s%s(%s);' % (dest, NATIVE_PREFIX, op.fn, args))

    def visit_method_call(self, op: MethodCall) -> None:
        dest = self.get_dest_assign(op)
        obj = self.reg(op.obj)

        rtype = op.receiver_type
        method_idx = rtype.method_index(op.method)
        args = ', '.join([obj] + [self.reg(arg) for arg in op.args])
        method = rtype.class_ir.get_method(op.method)
        assert method is not None
        mtype = native_function_type(method)
        self.emit_line('{}CPY_GET_METHOD({}, {}, {}, {})({});'.format(
            dest, obj, method_idx, rtype.struct_name(), mtype, args))

    def visit_py_call(self, op: PyCall) -> None:
        dest = self.get_dest_assign(op)
        function = self.reg(op.function)
        args = ', '.join(self.reg(arg) for arg in op.args)
        if args:
            args += ', '
        self.emit_line('{}PyObject_CallFunctionObjArgs({}, {}NULL);'.format(dest, function, args))

    def visit_py_method_call(self, op: PyMethodCall) -> None:
        dest = self.get_dest_assign(op)
        obj = self.reg(op.obj)
        method = self.reg(op.method)
        args = ', '.join(self.reg(arg) for arg in op.args)
        if args:
            args += ', '
        self.emit_line('{}PyObject_CallMethodObjArgs({}, {}, {}NULL);'.format(
            dest, obj, method, args))

    def visit_inc_ref(self, op: IncRef) -> None:
        src = self.reg(op.src)
        self.emit_inc_ref(src, op.src.type)

    def visit_dec_ref(self, op: DecRef) -> None:
        src = self.reg(op.src)
        self.emit_dec_ref(src, op.src.type)

    def visit_box(self, op: Box) -> None:
        self.emitter.emit_box(self.reg(op.src), self.reg(op), op.src.type)

    def visit_cast(self, op: Cast) -> None:
        self.emitter.emit_cast(self.reg(op.src), self.reg(op), op.type)

    def visit_unbox(self, op: Unbox) -> None:
        self.emitter.emit_unbox(self.reg(op.src), self.reg(op), op.type)

    def visit_unreachable(self, op: Unreachable) -> None:
        pass  # Nothing to do

    # Helpers

    def label(self, label: Label) -> str:
        return self.emitter.label(label)

    def reg(self, reg: Value) -> str:
        return self.emitter.reg(reg)

    def emit_line(self, line: str) -> None:
        self.emitter.emit_line(line)

    def emit_lines(self, *lines: str) -> None:
        self.emitter.emit_lines(*lines)

    def emit_inc_ref(self, dest: str, rtype: RType) -> None:
        self.emitter.emit_inc_ref(dest, rtype)

    def emit_dec_ref(self, dest: str, rtype: RType) -> None:
        self.emitter.emit_dec_ref(dest, rtype)

    def emit_declaration(self, line: str) -> None:
        self.declarations.emit_line(line)
