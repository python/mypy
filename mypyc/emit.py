"""Utilities for emitting C code."""

from typing import List, Set, Dict

from mypyc.common import REG_PREFIX
from mypyc.ops import (
    Environment, Label, Register, RTType, TupleRTType, UserRTType, type_struct_name
)


class HeaderDeclaration:
    def __init__(self, dependencies: Set[str], body: List[str]) -> None:
        self.dependencies = dependencies
        self.body = body


class EmitterContext:
    """Shared emitter state for an entire module."""

    def __init__(self) -> None:
        self.temp_counter = 0

        # A map of a C identifier to whatever the C identifier declares. Currently this is
        # used for declaring structs and the key corresponds to the name of the struct.
        # The declaration contains the body of the struct.
        self.declarations = {} # type: Dict[str, HeaderDeclaration]


class Emitter:
    """Helper for C code generation."""

    def __init__(self, context: EmitterContext, env: Environment = None) -> None:
        self.context = context
        self.env = env or Environment()
        self.fragments = []  # type: List[str]
        self._indent = 0

    # Low-level operations

    def indent(self) -> None:
        self._indent += 4

    def dedent(self) -> None:
        self._indent -= 4
        assert self._indent >= 0

    def label(self, label: Label) -> str:
        return 'CPyL%d' % label

    def reg(self, reg: Register) -> str:
        name = self.env.names[reg]
        return REG_PREFIX + name

    def emit_line(self, line: str = '') -> None:
        if line.startswith('}'):
            self.dedent()
        self.fragments.append(self._indent * ' ' + line + '\n')
        if line.endswith('{'):
            self.indent()

    def emit_lines(self, *lines: str) -> None:
        for line in lines:
            self.emit_line(line)

    def emit_label(self, label: Label) -> None:
        # Extra semicolon prevents an error when the next line declares a tempvar
        self.fragments.append('{}: ;\n'.format(self.label(label)))

    def emit_from_emitter(self, emitter: 'Emitter') -> None:
        self.fragments.extend(emitter.fragments)

    def temp_name(self) -> str:
        self.context.temp_counter += 1
        return '__tmp%d' % self.context.temp_counter

    # Higher-level operations

    def declare_tuple_struct(self, tuple_type: TupleRTType) -> None:
        if tuple_type.struct_name not in self.context.declarations:
            dependencies = set()
            for typ in tuple_type.types:
                # XXX other types might eventually need similar behavior
                if isinstance(typ, TupleRTType):
                    dependencies.add(typ.struct_name)

            self.context.declarations[tuple_type.struct_name] = HeaderDeclaration(
                dependencies,
                tuple_type.get_c_declaration(),
            )

    def emit_inc_ref(self, dest: str, rtype: RTType) -> None:
        """Increment reference count of C expression `dest`.

        For composite unboxed structures (e.g. tuples) recursively
        increment reference counts for each component.
        """
        if rtype.name == 'int':
            self.emit_line('CPyTagged_IncRef(%s);' % dest)
        elif isinstance(rtype, TupleRTType):
            for i, item_type in enumerate(rtype.types):
                self.emit_inc_ref('{}.f{}'.format(dest, i), item_type)
        elif not rtype.supports_unbox:
            self.emit_line('Py_INCREF(%s);' % dest)
        # Otherwise assume it's an unboxed, pointerless value and do nothing.

    def emit_dec_ref(self, dest: str, rtype: RTType) -> None:
        """Decrement reference count of C expression `dest`.

        For composite unboxed structures (e.g. tuples) recursively
        decrement reference counts for each component.
        """
        if rtype.name == 'int':
            self.emit_line('CPyTagged_DecRef(%s);' % dest)
        elif isinstance(rtype, TupleRTType):
            for i, item_type in enumerate(rtype.types):
                self.emit_dec_ref('{}.f{}'.format(dest, i), item_type)
        elif not rtype.supports_unbox:
            self.emit_line('Py_DECREF(%s);' % dest)
        # Otherwise assume it's an unboxed, pointerless value and do nothing.

    def emit_unbox_or_cast(self, src: str, dest: str, typ: RTType, failure: str,
                           declare_dest: bool = False) -> None:
        """Emit code for unboxing a value of given type (from PyObject *).

        Generate a cast if no actual unboxing is needed. Evaluate C code in 'failure'
        if the value has an incompatible type.

        Args:
            src: Name of source C variable
            dest: Name of target C variable
            typ: Type of value
            failure: What happens on error
            declare_dest: If True, also declare the variable 'dest'
        """
        failure = '    ' + failure
        if typ.name == 'int':
            if declare_dest:
                self.emit_line('CPyTagged {};'.format(dest))
            self.emit_lines(
                'if (PyLong_Check({}))'.format(src),
                '    {} = CPyTagged_FromObject({});'.format(dest, src),
                'else',
                failure)
        elif typ.name == 'bool':
            self.emit_lines(
                'if (!PyBool_Check({}))'.format(src),
                failure)
            conversion = 'PyObject_IsTrue({})'.format(src)
            if declare_dest:
                self.emit_line('char {} = {};'.format(dest, conversion))
            else:
                self.emit_line('{} = {};'.format(dest, conversion))
        elif typ.name == 'list':
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_lines(
                'if (PyList_Check({}))'.format(src),
                '    {} = {};'.format(dest, src),
                'else',
                failure)
        elif typ.name == 'sequence_tuple':
            self.emit_lines(
                'if (!PyTuple_Check({}))'.format(src),
                failure)
            if declare_dest:
                self.emit_line('{} {} = {};'.format(typ.ctype, dest, src))
            else:
                self.emit_line('{} = {};'.format(dest, src))
        elif typ.name == 'tuple':
            assert isinstance(typ, TupleRTType)
            self.declare_tuple_struct(typ)
            self.emit_lines(
                'if (!PyTuple_Check({}) || PyTuple_Size({}) != {})'.format(src, src,
                                                                           len(typ.types)),
                failure)
            if declare_dest:
                self.emit_line('{} {};'.format(typ.ctype, dest))
            for i in range(0, len(typ.types)):
                temp = self.temp_name()
                self.emit_line('PyObject *{} = PyTuple_GetItem({}, {});'.format(temp, src, i))

                temp2 = self.temp_name()
                # Unbox and check the sub-argument
                self.emit_unbox_or_cast('{}'.format(temp), temp2, typ.types[i], failure,
                                        declare_dest=True)
                self.emit_line('{}.f{} = {};'.format(dest, i, temp2))
        elif isinstance(typ, UserRTType):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_lines(
                'if (PyObject_TypeCheck({}, &{}))'.format(src, type_struct_name(typ.name)),
                '    {} = {};'.format(dest, src),
                'else',
                failure)
        elif typ.name == 'None':
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_line('{} = {};'.format(dest, src))
        else:
            assert False, 'Unboxing not implemented: %s' % typ

    def emit_box(self, src: str, dest: str, typ: RTType, failure: str) -> None:
        """Emit code for boxing a value of give type.

        Generate a simple assignment if no boxing is needed.
        """
        if typ.name == 'int':
            self.emit_line('PyObject *{} = CPyTagged_AsObject({});'.format(dest, src))
        elif typ.name == 'bool':
            # The Py_RETURN macros return the correct PyObject * with reference count handling.
            self.emit_lines('PyObject *{} = PyBool_FromLong({});'.format(dest, src))
        elif typ.name == 'tuple':
            assert isinstance(typ, TupleRTType)
            self.declare_tuple_struct(typ)
            self.emit_line('PyObject *{} = PyTuple_New({});'.format(dest, len(typ.types)))
            self.emit_line('if ({} == NULL) {{'.format(dest))
            self.emit_line('{}'.format(failure))
            self.emit_line('}')
            # TODO: Fail if dest is None
            for i in range(0, len(typ.types)):
                if not typ.supports_unbox:
                    self.emit_line('PyTuple_SetItem({}, {}, {}.f{}'.format(dest, i, src, i))
                else:
                    inner_name = self.temp_name()
                    self.emit_box('{}.f{}'.format(src, i), inner_name, typ.types[i], failure)
                    self.emit_line('PyTuple_SetItem({}, {}, {});'.format(dest, i, inner_name, i))
        else:
            # Type is boxed -- trivially just assign.
            self.emit_line('PyObject *{} = {};'.format(dest, src))

    def emit_error_check(self, value: str, rtype: RTType, failure: str) -> None:
        """Emit code for checking a native function return value for uncaught exception."""
        if not isinstance(rtype, TupleRTType):
            self.emit_line('if ({} == {}) {{'.format(value, rtype.c_error_value))
        else:
            self.emit_line('if ({}.f0 == {}) {{'.format(value, rtype.types[0].c_error_value))
        self.emit_lines(failure, '}')
