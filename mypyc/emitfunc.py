"""Code generation for native function bodies."""

from typing_extensions import Final

from mypyc.common import (
    REG_PREFIX, NATIVE_PREFIX, STATIC_PREFIX, TYPE_PREFIX, MODULE_PREFIX,
)
from mypyc.emit import Emitter
from mypyc.ops import (
    FuncIR, OpVisitor, Goto, Branch, Return, Assign, LoadInt, LoadErrorValue, GetAttr, SetAttr,
    LoadStatic, InitStatic, TupleGet, TupleSet, Call, IncRef, DecRef, Box, Cast, Unbox,
    BasicBlock, Value, RType, RTuple, MethodCall, PrimitiveOp,
    EmitterInterface, Unreachable, NAMESPACE_STATIC, NAMESPACE_TYPE, NAMESPACE_MODULE,
    RaiseStandardError, FuncDecl, ClassIR,
    FUNC_STATICMETHOD, FUNC_CLASSMETHOD,
)
from mypyc.namegen import NameGenerator

# Whether to insert debug asserts for all error handling, to quickly
# catch errors propagating without exceptions set.
DEBUG_ERRORS = False


def native_getter_name(cl: ClassIR, attribute: str, names: NameGenerator) -> str:
    return names.private_name(cl.module_name, 'native_{}_get{}'.format(cl.name, attribute))


def native_setter_name(cl: ClassIR, attribute: str, names: NameGenerator) -> str:
    return names.private_name(cl.module_name, 'native_{}_set{}'.format(cl.name, attribute))


def native_function_type(fn: FuncIR, emitter: Emitter) -> str:
    args = ', '.join(emitter.ctype(arg.type) for arg in fn.args) or 'void'
    ret = emitter.ctype(fn.ret_type)
    return '{} (*)({})'.format(ret, args)


def native_function_header(fn: FuncDecl, emitter: Emitter) -> str:
    args = []
    for arg in fn.sig.args:
        args.append('{}{}{}'.format(emitter.ctype_spaced(arg.type), REG_PREFIX, arg.name))

    return '{ret_type}{name}({args})'.format(
        ret_type=emitter.ctype_spaced(fn.sig.ret_type),
        name=emitter.native_function_name(fn),
        args=', '.join(args) or 'void')


def generate_native_function(fn: FuncIR,
                             emitter: Emitter,
                             source_path: str,
                             module_name: str) -> None:
    declarations = Emitter(emitter.context, fn.env)
    body = Emitter(emitter.context, fn.env)
    visitor = FunctionEmitterVisitor(body, declarations, source_path, module_name)

    declarations.emit_line('{} {{'.format(native_function_header(fn.decl, emitter)))
    body.indent()

    for r, i in fn.env.indexes.items():
        if isinstance(r.type, RTuple):
            emitter.declare_tuple_struct(r.type)
        if i < len(fn.args):
            continue  # skip the arguments
        ctype = emitter.ctype_spaced(r.type)
        init = ''
        if r in fn.env.vars_needing_init:
            init = ' = {}'.format(declarations.c_error_value(r.type))
        declarations.emit_line('{ctype}{prefix}{name}{init};'.format(ctype=ctype,
                                                                     prefix=REG_PREFIX,
                                                                     name=r.name,
                                                                     init=init))

    # Before we emit the blocks, give them all labels
    for i, block in enumerate(fn.blocks):
        block.label = i

    for block in fn.blocks:
        body.emit_label(block)
        for op in block.ops:
            op.accept(visitor)

    body.emit_line('}')

    emitter.emit_from_emitter(declarations)
    emitter.emit_from_emitter(body)


class FunctionEmitterVisitor(OpVisitor[None], EmitterInterface):
    def __init__(self,
                 emitter: Emitter,
                 declarations: Emitter,
                 source_path: str,
                 module_name: str) -> None:
        self.emitter = emitter
        self.names = emitter.names
        self.declarations = declarations
        self.env = self.emitter.env
        self.source_path = source_path
        self.module_name = module_name

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
        elif op.op == Branch.IS_ERROR:
            typ = op.left.type
            compare = '!=' if op.negated else '=='
            if isinstance(typ, RTuple):
                # TODO: What about empty tuple?
                cond = self.emitter.tuple_undefined_check_cond(typ,
                                                               self.reg(op.left),
                                                               self.c_error_value,
                                                               compare)
            else:
                cond = '{} {} {}'.format(self.reg(op.left),
                                         compare,
                                         self.c_error_value(typ))
        else:
            assert False, "Invalid branch"

        # For error checks, tell the compiler the branch is unlikely
        if op.traceback_entry is not None or op.rare:
            cond = 'unlikely({})'.format(cond)

        self.emit_line('if ({}) {{'.format(cond))

        if op.traceback_entry is not None:
            globals_static = self.emitter.static_name('globals', self.module_name)
            self.emit_line('CPy_AddTraceback("%s", "%s", %d, %s);' % (
                self.source_path.replace("\\", "\\\\"),
                op.traceback_entry[0],
                op.traceback_entry[1],
                globals_static))
            if DEBUG_ERRORS:
                self.emit_line('assert(PyErr_Occurred() != NULL && "failure w/o err!");')

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
        if len(op.items) == 0:  # empty tuple
            self.emit_line('{}.empty_struct_error_flag = 0;'.format(dest))
        else:
            for i, item in enumerate(op.items):
                self.emit_line('{}.f{} = {};'.format(dest, i, self.reg(item)))
        self.emit_inc_ref(dest, tuple_type)

    def visit_assign(self, op: Assign) -> None:
        dest = self.reg(op.dest)
        src = self.reg(op.src)
        # clang whines about self assignment (which we might generate
        # for some casts), so don't emit it.
        if dest != src:
            self.emit_line('%s = %s;' % (dest, src))

    def visit_load_int(self, op: LoadInt) -> None:
        dest = self.reg(op)
        self.emit_line('%s = %d;' % (dest, op.value * 2))

    def visit_load_error_value(self, op: LoadErrorValue) -> None:
        if isinstance(op.type, RTuple):
            values = [self.c_undefined_value(item) for item in op.type.types]
            tmp = self.temp_name()
            self.emit_line('%s %s = { %s };' % (self.ctype(op.type), tmp, ', '.join(values)))
            self.emit_line('%s = %s;' % (self.reg(op), tmp))
        else:
            self.emit_line('%s = %s;' % (self.reg(op),
                                         self.c_error_value(op.type)))

    def visit_get_attr(self, op: GetAttr) -> None:
        dest = self.reg(op)
        obj = self.reg(op.obj)
        rtype = op.class_type
        cl = rtype.class_ir
        version = '_TRAIT' if cl.is_trait else ''
        if cl.is_trait or cl.get_method(op.attr):
            self.emit_line('%s = CPY_GET_ATTR%s(%s, %s, %d, %s, %s); /* %s */' % (
                dest,
                version,
                obj,
                self.emitter.type_struct_name(rtype.class_ir),
                rtype.getter_index(op.attr),
                rtype.struct_name(self.names),
                self.ctype(rtype.attr_type(op.attr)),
                op.attr))
        else:
            typ, decl_cl = cl.attr_details(op.attr)
            # FIXME: We use the lib_prefixed version which is an
            # indirect call we can't inline. We should investigate
            # duplicating getter/setter code.
            self.emit_line('%s = %s%s((%s *)%s); /* %s */' % (
                dest,
                self.emitter.get_group_prefix(decl_cl),
                native_getter_name(decl_cl, op.attr, self.emitter.names),
                decl_cl.struct_name(self.names),
                obj,
                op.attr))

    def visit_set_attr(self, op: SetAttr) -> None:
        dest = self.reg(op)
        obj = self.reg(op.obj)
        src = self.reg(op.src)
        rtype = op.class_type
        cl = rtype.class_ir
        version = '_TRAIT' if cl.is_trait else ''
        if cl.is_trait or cl.get_method(op.attr):
            self.emit_line('%s = CPY_SET_ATTR%s(%s, %s, %d, %s, %s, %s); /* %s */' % (
                dest,
                version,
                obj,
                self.emitter.type_struct_name(rtype.class_ir),
                rtype.setter_index(op.attr),
                src,
                rtype.struct_name(self.names),
                self.ctype(rtype.attr_type(op.attr)),
                op.attr))
        else:
            typ, decl_cl = cl.attr_details(op.attr)
            self.emit_line('%s = %s%s((%s *)%s, %s); /* %s */' % (
                dest,
                self.emitter.get_group_prefix(decl_cl),
                native_setter_name(decl_cl, op.attr, self.emitter.names),
                decl_cl.struct_name(self.names),
                obj,
                src,
                op.attr))

    PREFIX_MAP = {
        NAMESPACE_STATIC: STATIC_PREFIX,
        NAMESPACE_TYPE: TYPE_PREFIX,
        NAMESPACE_MODULE: MODULE_PREFIX,
    }  # type: Final

    def visit_load_static(self, op: LoadStatic) -> None:
        dest = self.reg(op)
        prefix = self.PREFIX_MAP[op.namespace]
        name = self.emitter.static_name(op.identifier, op.module_name, prefix)
        if op.namespace == NAMESPACE_TYPE:
            name = '(PyObject *)%s' % name
        ann = ''
        if op.ann:
            s = repr(op.ann)
            if not any(x in s for x in ('/*', '*/', '\0')):
                ann = ' /* %s */' % s
        self.emit_line('%s = %s;%s' % (dest, name, ann))

    def visit_init_static(self, op: InitStatic) -> None:
        value = self.reg(op.value)
        prefix = self.PREFIX_MAP[op.namespace]
        name = self.emitter.static_name(op.identifier, op.module_name, prefix)
        if op.namespace == NAMESPACE_TYPE:
            value = '(PyTypeObject *)%s' % value
        self.emit_line('%s = %s;' % (name, value))
        self.emit_inc_ref(name, op.value.type)

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
        """Call native function."""
        dest = self.get_dest_assign(op)
        args = ', '.join(self.reg(arg) for arg in op.args)
        lib = self.emitter.get_group_prefix(op.fn)
        cname = op.fn.cname(self.names)
        self.emit_line('%s%s%s%s(%s);' % (dest, lib, NATIVE_PREFIX, cname, args))

    def visit_method_call(self, op: MethodCall) -> None:
        """Call native method."""
        dest = self.get_dest_assign(op)
        obj = self.reg(op.obj)

        rtype = op.receiver_type
        class_ir = rtype.class_ir
        name = op.method
        method_idx = rtype.method_index(name)
        method = rtype.class_ir.get_method(name)
        assert method is not None

        # Can we call the method directly, bypassing vtable?
        is_direct = class_ir.is_method_final(name)

        # The first argument gets omitted for static methods and
        # turned into the class for class methods
        obj_args = (
            [] if method.decl.kind == FUNC_STATICMETHOD else
            ['(PyObject *)Py_TYPE({})'.format(obj)] if method.decl.kind == FUNC_CLASSMETHOD else
            [obj])
        args = ', '.join(obj_args + [self.reg(arg) for arg in op.args])
        mtype = native_function_type(method, self.emitter)
        version = '_TRAIT' if rtype.class_ir.is_trait else ''
        if is_direct:
            # Directly call method, without going through the vtable.
            lib = self.emitter.get_group_prefix(method.decl)
            self.emit_line('{}{}{}{}({});'.format(
                dest, lib, NATIVE_PREFIX, method.cname(self.names), args))
        else:
            # Call using vtable.
            self.emit_line('{}CPY_GET_METHOD{}({}, {}, {}, {}, {})({}); /* {} */'.format(
                dest, version, obj, self.emitter.type_struct_name(rtype.class_ir),
                method_idx, rtype.struct_name(self.names), mtype, args, op.method))

    def visit_inc_ref(self, op: IncRef) -> None:
        src = self.reg(op.src)
        self.emit_inc_ref(src, op.src.type)

    def visit_dec_ref(self, op: DecRef) -> None:
        src = self.reg(op.src)
        self.emit_dec_ref(src, op.src.type, op.is_xdec)

    def visit_box(self, op: Box) -> None:
        self.emitter.emit_box(self.reg(op.src), self.reg(op), op.src.type, can_borrow=True)

    def visit_cast(self, op: Cast) -> None:
        self.emitter.emit_cast(self.reg(op.src), self.reg(op), op.type,
                               src_type=op.src.type)

    def visit_unbox(self, op: Unbox) -> None:
        self.emitter.emit_unbox(self.reg(op.src), self.reg(op), op.type)

    def visit_unreachable(self, op: Unreachable) -> None:
        self.emitter.emit_line('CPy_Unreachable();')

    def visit_raise_standard_error(self, op: RaiseStandardError) -> None:
        # TODO: Better escaping of backspaces and such
        if op.value is not None:
            if isinstance(op.value, str):
                message = op.value.replace('"', '\\"')
                self.emitter.emit_line(
                    'PyErr_SetString(PyExc_{}, "{}");'.format(op.class_name, message))
            elif isinstance(op.value, Value):
                self.emitter.emit_line(
                    'PyErr_SetObject(PyExc_{}, {}{});'.format(op.class_name, REG_PREFIX,
                                                              op.value.name))
            else:
                assert False, 'op value type must be either str or Value'
        else:
            self.emitter.emit_line('PyErr_SetNone(PyExc_{});'.format(op.class_name))
        self.emitter.emit_line('{} = 0;'.format(self.reg(op)))

    # Helpers

    def label(self, label: BasicBlock) -> str:
        return self.emitter.label(label)

    def reg(self, reg: Value) -> str:
        return self.emitter.reg(reg)

    def ctype(self, rtype: RType) -> str:
        return self.emitter.ctype(rtype)

    def c_error_value(self, rtype: RType) -> str:
        return self.emitter.c_error_value(rtype)

    def c_undefined_value(self, rtype: RType) -> str:
        return self.emitter.c_undefined_value(rtype)

    def emit_line(self, line: str) -> None:
        self.emitter.emit_line(line)

    def emit_lines(self, *lines: str) -> None:
        self.emitter.emit_lines(*lines)

    def emit_inc_ref(self, dest: str, rtype: RType) -> None:
        self.emitter.emit_inc_ref(dest, rtype)

    def emit_dec_ref(self, dest: str, rtype: RType, is_xdec: bool) -> None:
        self.emitter.emit_dec_ref(dest, rtype, is_xdec)

    def emit_declaration(self, line: str) -> None:
        self.declarations.emit_line(line)
