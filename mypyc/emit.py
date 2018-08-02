"""Utilities for emitting C code."""

from collections import OrderedDict
from typing import List, Set, Dict, Optional, List, Callable, Union

from mypyc.common import REG_PREFIX, STATIC_PREFIX, TYPE_PREFIX, NATIVE_PREFIX
from mypyc.ops import (
    Any, AssignmentTarget, Environment, BasicBlock, Value, Register, RType, RTuple, RInstance,
    RUnion, RPrimitive, RUnion, is_int_rprimitive, is_float_rprimitive, is_bool_rprimitive,
    short_name, is_list_rprimitive, is_dict_rprimitive, is_set_rprimitive, is_tuple_rprimitive,
    is_none_rprimitive, is_object_rprimitive, object_rprimitive, is_str_rprimitive, ClassIR,
    FuncIR, FuncDecl, int_rprimitive, is_optional_type, optional_value_type
)
from mypyc.namegen import NameGenerator
from mypyc.sametype import is_same_type


class HeaderDeclaration:
    def __init__(self, dependencies: Set[str], body: List[str]) -> None:
        self.dependencies = dependencies
        self.body = body


class EmitterContext:
    """Shared emitter state for an entire compilation unit."""

    def __init__(self, module_names: List[str]) -> None:
        self.temp_counter = 0
        self.names = NameGenerator(module_names)

        # The two maps below are used for generating declarations or
        # definitions at the top of the C file. The main idea is that they can
        # be generated at any time during the emit phase.

        # A map of a C identifier to whatever the C identifier declares. Currently this is
        # used for declaring structs and the key corresponds to the name of the struct.
        # The declaration contains the body of the struct.
        self.declarations = OrderedDict()  # type: Dict[str, HeaderDeclaration]

        # A map from C identifier to code that defined the C identifier. This
        # is similar to to 'declarations', but these may appear after the
        # declarations in the generated code.
        self.statics = OrderedDict()  # type: Dict[str, str]


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

    def emit_label(self, label: Union[BasicBlock, str]) -> None:
        if isinstance(label, str):
            text = label
        else:
            text = self.label(label)
        # Extra semicolon prevents an error when the next line declares a tempvar
        self.fragments.append('{}: ;\n'.format(text))

    def emit_from_emitter(self, emitter: 'Emitter') -> None:
        self.fragments.extend(emitter.fragments)

    def emit_printf(self, fmt: str, *args: str) -> None:
        fmt = fmt.replace('\n', '\\n')
        self.emit_line('printf(%s);' % ', '.join(['"%s"' % fmt] + list(args)))
        self.emit_line('fflush(stdout);')

    def temp_name(self) -> str:
        self.context.temp_counter += 1
        return '__tmp%d' % self.context.temp_counter

    def new_label(self) -> str:
        self.context.temp_counter += 1
        return '__LL%d' % self.context.temp_counter

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

    def ctype(self, rtype: RType) -> str:
        if isinstance(rtype, RTuple):
            return 'struct {}'.format(self.tuple_struct_name(rtype))
        return rtype._ctype

    def ctype_spaced(self, rtype: RType) -> str:
        """Adds a space after ctype for non-pointers."""
        ctype = self.ctype(rtype)
        if ctype[-1] == '*':
            return ctype
        else:
            return ctype + ' '

    def c_undefined_value(self, rtype: RType) -> str:
        if not rtype.is_unboxed:
            return 'NULL'
        elif isinstance(rtype, RPrimitive):
            return rtype.c_undefined
        elif isinstance(rtype, RTuple):
            return self.tuple_undefined_value(rtype)
        assert False, rtype

    def c_error_value(self, rtype: RType) -> str:
        return self.c_undefined_value(rtype)

    def native_function_name(self, fn: FuncDecl) -> str:
        return '{}{}'.format(NATIVE_PREFIX, fn.cname(self.names))

    def tuple_ctype(self, rtuple: RTuple) -> str:
        return 'struct {}'.format(self.tuple_struct_name(rtuple))

    def tuple_unique_id(self, rtuple: RTuple) -> str:
        """Generate a unique id which is used in naming corresponding C identifiers.

        This is necessary since C does not have anonymous structural type equivalence
        in the same way python can just assign a Tuple[int, bool] to a Tuple[int, bool].

        TODO: a better unique id. (#38)
        """
        return str(abs(hash(rtuple)))[0:15]

    def tuple_struct_name(self, rtuple: RTuple) -> str:
        # max c length is 31 chars, this should be enough entropy to be unique.
        return 'tuple_def_' + self.tuple_unique_id(rtuple)

    def tuple_c_declaration(self, rtuple: RTuple) -> List[str]:
        result = ['struct {} {{'.format(self.tuple_struct_name(rtuple))]
        if len(rtuple.types) == 0:  # empty tuple
            # The behavior of empty structs in C is compiler dependent so we add a dummy variable
            # to avoid empty tuples being defined as empty structs.
            result.append('int dummy_var_to_avoid_empty_struct;')
        else:
            i = 0
            for typ in rtuple.types:
                result.append('    {}f{};'.format(self.ctype_spaced(typ), i))
                i += 1
        result.append('};')
        result.append('')

        return result

    def tuple_undefined_check_cond(
            self, rtuple: RTuple, tuple_expr_in_c: str,
            c_type_compare_val: Callable[[RType], str], compare: str) -> str:
        item_type = rtuple.types[0]
        if not isinstance(item_type, RTuple):
            return '{}.f0 {} {}'.format(
                tuple_expr_in_c, compare, c_type_compare_val(item_type))
        elif isinstance(item_type, RTuple) and len(item_type.types) == 0:
            # empty tuple
            return '{}.dummy_var_to_avoid_empty_struct {} {}'.format(
                tuple_expr_in_c, compare, c_type_compare_val(int_rprimitive))
        else:
            return self.tuple_undefined_check_cond(
                item_type, tuple_expr_in_c + '.f0', c_type_compare_val, compare)

    def tuple_undefined_value(self, rtuple: RTuple) -> str:
        context = self.context
        id = self.tuple_unique_id(rtuple)
        name = 'tuple_undefined_' + id
        if name not in context.statics:
            struct_name = self.tuple_struct_name(rtuple)
            values = self.tuple_undefined_value_helper(rtuple)
            init = 'struct {} {} = {{ {} }};'.format(struct_name, name, ''.join(values))
            context.statics[name] = init
        return name

    def tuple_undefined_value_helper(self, rtuple: RTuple) -> List[str]:
        res = []
        # see tuple_c_declaration()
        if len(rtuple.types) == 0:
            return [self.c_undefined_value(int_rprimitive)]
        for item in rtuple.types:
            if not isinstance(item, RTuple):
                res.append(self.c_undefined_value(item))
            else:
                sub_list = self.tuple_undefined_value_helper(item)
                res.append('{ ')
                res.extend(sub_list)
                res.append(' }')
            res.append(', ')
        return res[:-1]

    # Higher-level operations

    def declare_tuple_struct(self, tuple_type: RTuple) -> None:
        struct_name = self.tuple_struct_name(tuple_type)
        if struct_name not in self.context.declarations:
            dependencies = set()
            for typ in tuple_type.types:
                # XXX other types might eventually need similar behavior
                if isinstance(typ, RTuple):
                    dependencies.add(self.tuple_struct_name(typ))

            self.context.declarations[struct_name] = HeaderDeclaration(
                dependencies,
                self.tuple_c_declaration(tuple_type),
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
            self.emit_line('CPy_INCREF(%s);' % dest)
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
            self.emit_line('CPy_DECREF(%s);' % dest)
        # Otherwise assume it's an unboxed, pointerless value and do nothing.

    def pretty_name(self, typ: RType) -> str:
        pretty_name = typ.name
        value_type = optional_value_type(typ)
        if value_type is not None:
            pretty_name = '%s or None' % self.pretty_name(value_type)
        return short_name(pretty_name)

    def emit_cast(self, src: str, dest: str, typ: RType, declare_dest: bool = False,
                  custom_message: Optional[str] = None, optional: bool = False,
                  src_type: Optional[RType] = None) -> None:
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

        # Special case casting *from* optional
        if src_type and is_optional_type(src_type) and not is_object_rprimitive(typ):
            value_type = optional_value_type(src_type)
            assert value_type is not None
            if is_same_type(value_type, typ):
                if declare_dest:
                    self.emit_line('PyObject *{};'.format(dest))
                self.emit_arg_check(src, dest, typ, '({} != Py_None)'.format(src), optional)
                self.emit_lines(
                    '    {} = {};'.format(dest, src),
                    'else {',
                    err,
                    '{} = NULL;'.format(dest),
                    '}')

        # TODO: Verify refcount handling.
        elif (is_list_rprimitive(typ) or is_dict_rprimitive(typ) or is_set_rprimitive(typ) or
                is_float_rprimitive(typ) or is_str_rprimitive(typ) or is_int_rprimitive(typ) or
                is_bool_rprimitive(typ)):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            if is_list_rprimitive(typ):
                prefix = 'PyList'
            elif is_dict_rprimitive(typ):
                prefix = 'PyDict'
            elif is_set_rprimitive(typ):
                prefix = 'PySet'
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
            self.emit_arg_check(src, dest, typ, '({}_Check({}))'.format(prefix, src), optional)
            self.emit_lines(
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif is_tuple_rprimitive(typ):
            if declare_dest:
                self.emit_line('{} {};'.format(self.ctype(typ), dest))
            self.emit_arg_check(src, dest, typ, '(PyTuple_Check({}))'.format(src), optional)
            self.emit_lines(
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif isinstance(typ, RInstance):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_arg_check(src, dest, typ, '(PyObject_TypeCheck({}, {}))'.format(src,
                    self.type_struct_name(typ.class_ir)), optional)
            self.emit_lines(
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif is_none_rprimitive(typ):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_arg_check(src, dest, typ, '({} == Py_None)'.format(src), optional)
            self.emit_lines(
                '    {} = {};'.format(dest, src),
                'else {',
                err,
                '{} = NULL;'.format(dest),
                '}')
        elif is_object_rprimitive(typ):
            if declare_dest:
                self.emit_line('PyObject *{};'.format(dest))
            self.emit_arg_check(src, dest, typ, '', optional)
            self.emit_line('{} = {};'.format(dest, src))
            if optional:
                self.emit_line('}')
        elif isinstance(typ, RUnion):
            self.emit_union_cast(src, dest, typ, declare_dest, err, optional, src_type)
        else:
            assert False, 'Cast not implemented: %s' % typ

    def emit_union_cast(self, src: str, dest: str, typ: RUnion, declare_dest: bool,
                        err: str, optional: bool, src_type: Optional[RType]) -> None:
        """Emit cast to a union type.

        The arguments are similar to emit_cast.
        """
        if declare_dest:
            self.emit_line('PyObject *{};'.format(dest))
        good_label = self.new_label()
        for item in typ.items:
            self.emit_cast(src,
                           dest,
                           item,
                           declare_dest=False,
                           custom_message='',
                           optional=optional)
            self.emit_line('if ({} != NULL) goto {};'.format(dest, good_label))
        # Handle cast failure.
        self.emit_line(err)
        self.emit_label(good_label)

    def emit_arg_check(self, src: str, dest: str, typ: RType, check: str, optional: bool) -> None:
        if optional:
            self.emit_line('if ({} == NULL) {{'.format(src))
            self.emit_line('{} = {};'.format(dest, self.c_error_value(typ)))
        if check != '':
            self.emit_line('{}if {}'.format('} else ' if optional else '', check))
        elif optional:
            self.emit_line('else {')

    def emit_unbox(self, src: str, dest: str, typ: RType, custom_failure: Optional[str] = None,
                   declare_dest: bool = False, borrow: bool = False,
                   optional: bool = False) -> None:
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
                       '%s = %s;' % (dest, self.c_error_value(typ))]
        if is_int_rprimitive(typ):
            if declare_dest:
                self.emit_line('CPyTagged {};'.format(dest))
            self.emit_arg_check(src, dest, typ, '(PyLong_Check({}))'.format(src), optional)
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
            self.emit_arg_check(src, dest, typ, '(!PyBool_Check({})) {{'.format(src), optional)
            self.emit_lines(*failure)
            self.emit_line('} else')
            conversion = 'PyObject_IsTrue({})'.format(src)
            self.emit_line('    {} = {};'.format(dest, conversion))
        elif isinstance(typ, RTuple):
            self.declare_tuple_struct(typ)
            if declare_dest:
                self.emit_line('{} {};'.format(self.ctype(typ), dest))
            self.emit_arg_check(src, dest, typ,
                '(!PyTuple_Check({}) || PyTuple_Size({}) != {}) {{'.format(
                    src, src, len(typ.types)), optional)
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
            self.emit_line('if ({} == {}) {{'.format(value, self.c_error_value(rtype)))
        else:
            if len(rtype.types) == 0:
                return  # empty tuples can't fail.
            else:
                cond = self.tuple_undefined_check_cond(rtype, value, self.c_error_value, '==')
                self.emit_line('if ({}) {{'.format(cond))
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
        elif self.ctype(rtype) == 'PyObject *':
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
            self.emit_line('{} = {};'.format(target, self.c_undefined_value(rtype)))
            self.emit_line('Py_XDECREF(CPyTagged_LongAsObject(__tmp));')
            self.emit_line('}')
        elif isinstance(rtype, RTuple):
            for i, item_type in enumerate(rtype.types):
                self.emit_gc_clear('{}.f{}'.format(target, i), item_type)
        elif self.ctype(rtype) == 'PyObject *' and self.c_undefined_value(rtype) == 'NULL':
            # The simplest case.
            self.emit_line('Py_CLEAR({});'.format(target))
        else:
            assert False, 'emit_gc_clear() not implemented for %s' % repr(rtype)
