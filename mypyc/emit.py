"""Utilities for emitting C code."""

from collections import OrderedDict
from typing import List, Set, Dict, Optional

from mypyc.common import REG_PREFIX, STATIC_PREFIX, TYPE_PREFIX
from mypyc.ops import (
    Environment, BasicBlock, Value, Register, RType, RTuple, RInstance, ROptional,
    RPrimitive, is_int_rprimitive, is_float_rprimitive, is_bool_rprimitive,
    short_name, is_list_rprimitive, is_dict_rprimitive, is_tuple_rprimitive, is_none_rprimitive,
    is_object_rprimitive, object_rprimitive, is_str_rprimitive, ClassIR
)
from mypyc.namegen import NameGenerator


class HeaderDeclaration:
    def __init__(self, dependencies: Set[str], body: List[str]) -> None:
        self.dependencies = dependencies
        self.body = body


class EmitterContext:
    """Shared emitter state for an entire compilation unit."""

    def __init__(self, module_names: List[str]) -> None:
        self.temp_counter = 0
        self.names = NameGenerator(module_names)

        # A map of a C identifier to whatever the C identifier declares. Currently this is
        # used for declaring structs and the key corresponds to the name of the struct.
        # The declaration contains the body of the struct.
        self.declarations = OrderedDict()  # type: Dict[str, HeaderDeclaration]


class Emitter:
    """Helper for C code generation."""

    def __init__(self, context: EmitterContext, env: Optional[Environment] = None) -> None:
        self.context = context
        self.names = context.names
        self.env = env or Environment()
        self.fragments = []  # type: List[str]
        self._indent = 0

    # Low-level operations

    def indent(self) -> None:
        self._indent += 4

    def dedent(self) -> None:
        self._indent -= 4
        assert self._indent >= 0

    def label(self, label: BasicBlock) -> str:
        return 'CPyL%s' % label.label

    def reg(self, reg: Value) -> str:
        return REG_PREFIX + reg.name

    def emit_line(self, line: str = '') -> None:
        if line.startswith('}'):
            self.dedent()
        self.fragments.append(self._indent * ' ' + line + '\n')
        if line.endswith('{'):
            self.indent()

    def emit_lines(self, *lines: str) -> None:
        for line in lines:
            self.emit_line(line)

    def emit_label(self, label: BasicBlock) -> None:
        # Extra semicolon prevents an error when the next line declares a tempvar
        self.fragments.append('{}: ;\n'.format(self.label(label)))

    def emit_from_emitter(self, emitter: 'Emitter') -> None:
        self.fragments.extend(emitter.fragments)

    def emit_printf(self, fmt: str, *args: str) -> None:
        fmt = fmt.replace('\n', '\\n')
        self.emit_line('printf(%s);' % ', '.join(['"%s"' % fmt] + list(args)))
        self.emit_line('fflush(stdout);')

    def temp_name(self) -> str:
        self.context.temp_counter += 1
        return '__tmp%d' % self.context.temp_counter

    def static_name(self, id: str, module: Optional[str], prefix: str = STATIC_PREFIX) -> str:
        """Create name of a C static variable.

        These are used for literals and imported modules, among other
        things.

        The caller should ensure that the (id, module) pair cannot
        overlap with other calls to this method within a compilation
        unit.
        """
        suffix = self.names.private_name(module or '', id)
        return '{}{}'.format(prefix, suffix)

    def type_struct_name(self, cl: ClassIR) -> str:
        return self.static_name(cl.name, cl.module_name, prefix=TYPE_PREFIX)

    # Higher-level operations

    def declare_tuple_struct(self, tuple_type: RTuple) -> None:
        if tuple_type.struct_name() not in self.context.declarations:
            dependencies = set()
            for typ in tuple_type.types:
                # XXX other types might eventually need similar behavior
                if isinstance(typ, RTuple):
                    dependencies.add(typ.struct_name())

            self.context.declarations[tuple_type.struct_name()] = HeaderDeclaration(
                dependencies,
                tuple_type.get_c_declaration(),
            )

    def emit_inc_ref(self, dest: str, rtype: RType) -> None:
        """Increment reference count of C expression `dest`.

        For composite unboxed structures (e.g. tuples) recursively
        increment reference counts for each component.
        """
        if is_int_rprimitive(rtype):
            self.emit_line('CPyTagged_IncRef(%s);' % dest)
        elif isinstance(rtype, RTuple):
            for i, item_type in enumerate(rtype.types):
                self.emit_inc_ref('{}.f{}'.format(dest, i), item_type)
        elif not rtype.is_unboxed:
            self.emit_line('Py_INCREF(%s);' % dest)
        # Otherwise assume it's an unboxed, pointerless value and do nothing.

    def emit_dec_ref(self, dest: str, rtype: RType) -> None:
        """Decrement reference count of C expression `dest`.

        For composite unboxed structures (e.g. tuples) recursively
        decrement reference counts for each component.
        """
        if is_int_rprimitive(rtype):
            self.emit_line('CPyTagged_DecRef(%s);' % dest)
        elif isinstance(rtype, RTuple):
            for i, item_type in enumerate(rtype.types):
                self.emit_dec_ref('{}.f{}'.format(dest, i), item_type)
        elif not rtype.is_unboxed:
            self.emit_line('Py_DECREF(%s);' % dest)
        # Otherwise assume it's an unboxed, pointerless value and do nothing.

    def pretty_name(self, typ: RType) -> str:
        pretty_name = typ.name
        if isinstance(typ, ROptional):
            pretty_name = '%s or None' % self.pretty_name(typ.value_type)
        return short_name(pretty_name)

    def emit_cast(self, src: str, dest: str, typ: RType, declare_dest: bool = False,
                  custom_message: Optional[str] = None) -> None:
        """Emit code for casting a value of given type.

        Somewhat strangely, this supports unboxed types but only
        operates on boxed versions.  This is necessary to properly
        handle types such as Optional[int] in compatability glue.

        Assign NULL (error value) to dest if the value has an incompatible type.

        Always copy/steal the reference in src.

        Args:
            src: Name of source C variable
            dest: Name of target C variable
            typ: Type of value
            declare_dest: If True, also declare the variable 'dest'

        """
        if custom_message is not None:
            err = custom_message
        else:
            err = 'PyErr_SetString(PyExc_TypeError, "{} object expected");'.format(
                self.pretty_name(typ))
        # TODO: Verify refcount handling.
        if (is_list_rprimitive(typ) or is_dict_rprimitive(typ) or is_float_rprimitive(typ) or
                is_str_rprimitive(typ) or is_int_rprimitive(typ) or is_bool_rprimitive(typ)):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            if is_list_rprimitive(typ):
                prefix = 'PyList'
            elif is_dict_rprimitive(typ):
                prefix = 'PyDict'
            elif is_float_rprimitive(typ):
                prefix = 'PyFloat'
            elif is_str_rprimitive(typ):
                prefix = 'PyUnicode'
            elif is_int_rprimitive(typ):
                prefix = 'PyLong'
            elif is_bool_rprimitive(typ):
                prefix = 'PyBool'
            else:
                assert False, prefix
            self.emit_lines(
                'if ({}_Check({}))'.format(prefix, src),
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif is_tuple_rprimitive(typ):
            if declare_dest:
                self.emit_line('{} {};'.format(typ.ctype, dest))
            self.emit_lines(
                'if (PyTuple_Check({}))'.format(src),
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif isinstance(typ, RInstance):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_lines(
                'if (PyObject_TypeCheck({}, &{}))'.format(
                    src,
                    self.type_struct_name(typ.class_ir)),
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif is_none_rprimitive(typ):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_lines(
                'if ({} == Py_None)'.format(src),
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif is_object_rprimitive(typ):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_line('{} = {};'.format(dest, src))
        elif isinstance(typ, ROptional):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_lines(
                'if ({} == Py_None)'.format(src),
                '    {} = {};'.format(dest, src),
                'else {')
            self.emit_cast(src, dest, typ.value_type, custom_message=err)
            self.emit_line('}')
        else:
            assert False, 'Cast not implemented: %s' % typ

    def emit_unbox(self, src: str, dest: str, typ: RType, custom_failure: Optional[str] = None,
                   declare_dest: bool = False, borrow: bool = False) -> None:
        """Emit code for unboxing a value of given type (from PyObject *).

        Evaluate C code in 'failure' if the value has an incompatible type.

        Always generate a new reference.

        Args:
            src: Name of source C variable
            dest: Name of target C variable
            typ: Type of value
            failure: What happens on error
            declare_dest: If True, also declare the variable 'dest'
            borrow: If True, create a borrowed reference
        """
        # TODO: Raise exception on failure.
        # TODO: Verify refcount handling.
        raise_exc = 'PyErr_SetString(PyExc_TypeError, "%s object expected");' % (
            self.pretty_name(typ))
        if custom_failure is not None:
            failure = [raise_exc,
                       custom_failure]
        else:
            failure = [raise_exc,
                       '%s = %s;' % (dest, typ.c_error_value())]
        if is_int_rprimitive(typ):
            if declare_dest:
                self.emit_line('CPyTagged {};'.format(dest))
            self.emit_line('if (PyLong_Check({}))'.format(src))
            if borrow:
                self.emit_line('    {} = CPyTagged_BorrowFromObject({});'.format(dest, src))
            else:
                self.emit_line('    {} = CPyTagged_FromObject({});'.format(dest, src))
            self.emit_line('else {')
            self.emit_lines(*failure)
            self.emit_line('}')
        elif is_bool_rprimitive(typ):
            # Whether we are borrowing or not makes no difference.
            if declare_dest:
                self.emit_line('char {};'.format(dest))
            self.emit_line('if (!PyBool_Check(%s)) {' % src)
            self.emit_lines(*failure)
            self.emit_line('} else')
            conversion = 'PyObject_IsTrue({})'.format(src)
            self.emit_line('    {} = {};'.format(dest, conversion))
        elif isinstance(typ, RTuple):
            self.declare_tuple_struct(typ)
            if declare_dest:
                self.emit_line('{} {};'.format(typ.ctype, dest))
            self.emit_line(
                'if (!PyTuple_Check({}) || PyTuple_Size({}) != {}) {{'.format(src, src,
                                                                              len(typ.types)))
            self.emit_lines(*failure)  # TODO: Decrease refcount?
            self.emit_line('} else {')
            for i, item_type in enumerate(typ.types):
                temp = self.temp_name()
                self.emit_line('PyObject *{} = PyTuple_GetItem({}, {});'.format(temp, src, i))
                temp2 = self.temp_name()
                # Unbox or check the item.
                if item_type.is_unboxed:
                    self.emit_unbox(temp, temp2, item_type, custom_failure, declare_dest=True,
                                    borrow=borrow)
                else:
                    if not borrow:
                        self.emit_inc_ref(temp, object_rprimitive)
                    self.emit_cast(temp, temp2, item_type, declare_dest=True)
                self.emit_line('{}.f{} = {};'.format(dest, i, temp2))
            self.emit_line('}')
        else:
            assert False, 'Unboxing not implemented: %s' % typ

    def emit_box(self, src: str, dest: str, typ: RType, declare_dest: bool = False) -> None:
        """Emit code for boxing a value of give type.

        Generate a simple assignment if no boxing is needed.

        The source reference count is stolen for the result (no need to decref afterwards).
        """
        # TODO: Always generate a new reference (if a reference type)
        if declare_dest:
            declaration = 'PyObject *'
        else:
            declaration = ''
        if is_int_rprimitive(typ):
            # Steal the existing reference if it exists.
            self.emit_line('{}{} = CPyTagged_StealAsObject({});'.format(declaration, dest, src))
        elif is_bool_rprimitive(typ):
            # TODO: The Py_RETURN macros return the correct PyObject * with reference count
            #       handling. Relevant here?
            self.emit_lines('{}{} = PyBool_FromLong({});'.format(declaration, dest, src))
        elif isinstance(typ, RTuple):
            self.declare_tuple_struct(typ)
            self.emit_line('{}{} = PyTuple_New({});'.format(declaration, dest, len(typ.types)))
            self.emit_line('if ({} == NULL)'.format(dest))
            self.emit_line('    CPyError_OutOfMemory();')
            # TODO: Fail if dest is None
            for i in range(0, len(typ.types)):
                if not typ.is_unboxed:
                    self.emit_line('PyTuple_SetItem({}, {}, {}.f{}'.format(dest, i, src, i))
                else:
                    inner_name = self.temp_name()
                    self.emit_box('{}.f{}'.format(src, i), inner_name, typ.types[i],
                                  declare_dest=True)
                    self.emit_line('PyTuple_SetItem({}, {}, {});'.format(dest, i, inner_name, i))
        else:
            assert not typ.is_unboxed
            # Type is boxed -- trivially just assign.
            self.emit_line('{}{} = {};'.format(declaration, dest, src))

    def emit_error_check(self, value: str, rtype: RType, failure: str) -> None:
        """Emit code for checking a native function return value for uncaught exception."""
        if not isinstance(rtype, RTuple):
            self.emit_line('if ({} == {}) {{'.format(value, rtype.c_error_value()))
        else:
            self.emit_line('if ({}.f0 == {}) {{'.format(value, rtype.types[0].c_error_value()))
        self.emit_lines(failure, '}')

    def emit_gc_visit(self, target: str, rtype: RType) -> None:
        """Emit code for GC visiting a C variable reference.

        Assume that 'target' represents a C expression that refers to a
        struct member, such as 'self->x'.
        """
        if not rtype.is_refcounted:
            # Not refcounted -> no pointers -> no GC interaction.
            return
        elif isinstance(rtype, RPrimitive) and rtype.name == 'builtins.int':
            self.emit_line('if (CPyTagged_CheckLong({})) {{'.format(target))
            self.emit_line('Py_VISIT(CPyTagged_LongAsObject({}));'.format(target))
            self.emit_line('}')
        elif isinstance(rtype, RTuple):
            for i, item_type in enumerate(rtype.types):
                self.emit_gc_visit('{}.f{}'.format(target, i), item_type)
        elif rtype.ctype == 'PyObject *':
            # The simplest case.
            self.emit_line('Py_VISIT({});'.format(target))
        else:
            assert False, 'emit_gc_visit() not implemented for %s' % repr(rtype)

    def emit_gc_clear(self, target: str, rtype: RType) -> None:
        """Emit code for clearing a C attribute reference for GC.

        Assume that 'target' represents a C expression that refers to a
        struct member, such as 'self->x'.
        """
        if not rtype.is_refcounted:
            # Not refcounted -> no pointers -> no GC interaction.
            return
        elif isinstance(rtype, RPrimitive) and rtype.name == 'builtins.int':
            self.emit_line('if (CPyTagged_CheckLong({})) {{'.format(target))
            self.emit_line('CPyTagged __tmp = {};'.format(target))
            self.emit_line('{} = {};'.format(target, rtype.c_undefined_value()))
            self.emit_line('Py_XDECREF(CPyTagged_LongAsObject(__tmp));')
            self.emit_line('}')
        elif isinstance(rtype, RTuple):
            for i, item_type in enumerate(rtype.types):
                self.emit_gc_clear('{}.f{}'.format(target, i), item_type)
        elif rtype.ctype == 'PyObject *' and rtype.c_undefined_value() == 'NULL':
            # The simplest case.
            self.emit_line('Py_CLEAR({});'.format(target))
        else:
            assert False, 'emit_gc_clear() not implemented for %s' % repr(rtype)
