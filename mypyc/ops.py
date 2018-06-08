"""Representation of low-level opcodes for compiler intermediate representation (IR).

Opcodes operate on abstract registers in a register machine. Each
register has a type and a name, specified in an environment. A register
can hold various things:

- local variables
- intermediate values of expressions
- condition flags (true/false)
- literals (integer literals, True, False, etc.)
"""

from abc import abstractmethod, abstractproperty
import re
from typing import (
    List, Dict, Generic, TypeVar, Optional, Any, NamedTuple, Tuple, NewType, Callable, Union,
    Iterable,
)
from collections import OrderedDict

from mypy.nodes import Var


T = TypeVar('T')

# TODO: Use pointers to BasicBlocks instead?
Label = NewType('Label', int)

# This is used for placeholder labels which aren't assigned yet (but will
# be eventually. It's kind of a hack.
INVALID_LABEL = Label(-88888)


def c_module_name(module_name: str) -> str:
    return 'module_{}'.format(module_name.replace('.', '__dot__'))


def short_name(name: str) -> str:
    if name.startswith('builtins.'):
        return name[9:]
    return name


class RType:
    """Abstract base class for runtime types (erased, only concrete; no generics)."""

    name = None  # type: str
    ctype = None  # type: str
    is_unboxed = False
    c_undefined = None  # type: str
    is_refcounted = True  # If unboxed: does the unboxed version use reference counting?

    @abstractmethod
    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        raise NotImplementedError

    @abstractmethod
    def c_undefined_value(self) -> str:
        raise NotImplementedError

    def ctype_spaced(self) -> str:
        """Adds a space after ctype for non-pointers."""
        if self.ctype[-1] == '*':
            return self.ctype
        else:
            return self.ctype + ' '

    def c_error_value(self) -> str:
        return self.c_undefined_value()

    def short_name(self) -> str:
        return short_name(self.name)

    def __str__(self) -> str:
        return short_name(self.name)

    def __repr__(self) -> str:
        return '<%s>' % self.__class__.__name__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RType) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)


class RVoid(RType):
    """void"""

    is_unboxed = False
    name = 'void'
    ctype = 'void'

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rvoid(self)

    def c_undefined_value(self) -> str:
        return ''


void_rtype = RVoid()


class RPrimitive(RType):
    """Primitive type such as 'object' or 'int'.

    These often have custom ops associated with them.
    """

    def __init__(self,
                 name: str,
                 is_unboxed: bool,
                 is_refcounted: bool,
                 ctype: str = 'PyObject *') -> None:
        self.name = name
        self.is_unboxed = is_unboxed
        self.ctype = ctype
        self.is_refcounted = is_refcounted
        if ctype == 'CPyTagged':
            self.c_undefined = 'CPY_INT_TAG'
        elif ctype == 'PyObject *':
            self.c_undefined = 'NULL'
        elif ctype == 'char':
            self.c_undefined = '2'
        else:
            assert False, 'Uncognized ctype: %r' % ctype

    def c_undefined_value(self) -> str:
        return self.c_undefined

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rprimitive(self)

    def __repr__(self) -> str:
        return '<RPrimitive %s>' % self.name


# Used to represent arbitrary objects and dynamically typed values
object_rprimitive = RPrimitive('builtins.object', is_unboxed=False, is_refcounted=True)

int_rprimitive = RPrimitive('builtins.int', is_unboxed=True, is_refcounted=True, ctype='CPyTagged')

float_rprimitive = RPrimitive('builtins.float', is_unboxed=False, is_refcounted=True)

bool_rprimitive = RPrimitive('builtins.bool', is_unboxed=True, is_refcounted=False, ctype='char')

none_rprimitive = RPrimitive('builtins.None', is_unboxed=False, is_refcounted=True)

list_rprimitive = RPrimitive('builtins.list', is_unboxed=False, is_refcounted=True)

dict_rprimitive = RPrimitive('builtins.dict', is_unboxed=False, is_refcounted=True)

# At the C layer, str is refered to as unicode (PyUnicode)
str_rprimitive = RPrimitive('builtins.str', is_unboxed=False, is_refcounted=True)

# Tuple of an arbitrary length (corresponds to Tuple[t, ...], with explicit '...')
tuple_rprimitive = RPrimitive('builtins.tuple', is_unboxed=False, is_refcounted=True)


def is_int_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.int'


def is_float_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.float'


def is_bool_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.bool'


def is_object_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.object'


def is_none_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.None'


def is_list_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.list'


def is_dict_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.dict'


def is_str_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.str'


def is_tuple_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.tuple'


class RTuple(RType):
    """Fixed-length tuple."""

    is_unboxed = True

    def __init__(self, types: List[RType]) -> None:
        self.name = 'tuple'
        self.types = tuple(types)
        self.ctype = 'struct {}'.format(self.struct_name())
        self.is_refcounted = any(t.is_refcounted for t in self.types)

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rtuple(self)

    def c_undefined_value(self) -> str:
        # This doesn't work since this is expected to return a C expression, but
        # defining an undefined tuple requires declaring a temp variable, such as:
        #
        #    struct foo _tmp = { <item0-undefined>, <item1-undefined>, ... };
        assert False, "Tuple undefined value can't be represented as a C expression"

    @property
    def unique_id(self) -> str:
        """Generate a unique id which is used in naming corresponding C identifiers.

        This is necessary since C does not have anonymous structural type equivalence
        in the same way python can just assign a Tuple[int, bool] to a Tuple[int, bool].

        TODO: a better unique id. (#38)
        """
        return str(abs(hash(self)))[0:15]

    def struct_name(self) -> str:
        # max c length is 31 charas, this should be enough entropy to be unique.
        return 'tuple_def_' + self.unique_id

    def __str__(self) -> str:
        return 'tuple[%s]' % ', '.join(str(typ) for typ in self.types)

    def __repr__(self) -> str:
        return '<RTuple %s>' % ', '.join(repr(typ) for typ in self.types)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RTuple) and self.types == other.types

    def __hash__(self) -> int:
        return hash((self.name, self.types))

    def get_c_declaration(self) -> List[str]:
        result = ['struct {} {{'.format(self.struct_name())]
        i = 0
        for typ in self.types:
            result.append('    {}f{};'.format(typ.ctype_spaced(), i))
            i += 1
        result.append('};')
        result.append('')

        return result


class RInstance(RType):
    """Instance of user-defined class (compiled to C extension class)."""

    is_unboxed = False

    def __init__(self, class_ir: 'ClassIR') -> None:
        self.name = class_ir.name
        self.class_ir = class_ir
        self.ctype = 'PyObject *'

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rinstance(self)

    def c_undefined_value(self) -> str:
        return 'NULL'

    def struct_name(self) -> str:
        return self.class_ir.struct_name()

    def getter_index(self, name: str) -> int:
        for i, (attr, _) in enumerate(self.class_ir.attributes):
            if attr == name:
                return i * 2
        assert False, '%r has no attribute %r' % (self.name, name)

    def setter_index(self, name: str) -> int:
        return self.getter_index(name) + 1

    def method_index(self, name: str) -> int:
        base = len(self.class_ir.attributes) * 2
        for i, fn in enumerate(self.class_ir.methods):
            if fn.name == name:
                return base + i
        assert False, '%r has no attribute %r' % (self.name, name)

    def attr_type(self, name: str) -> RType:
        for i, (attr, rtype) in enumerate(self.class_ir.attributes):
            if attr == name:
                return rtype
        assert False, '%r has no attribute %r' % (self.name, name)

    def __repr__(self) -> str:
        return '<RInstance %s>' % self.name


class ROptional(RType):
    """Optional[x]"""

    is_unboxed = False

    def __init__(self, value_type: RType) -> None:
        self.name = 'optional'
        self.value_type = value_type
        self.ctype = 'PyObject *'

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_roptional(self)

    def c_undefined_value(self) -> str:
        return 'NULL'

    def __repr__(self) -> str:
        return '<ROptional %s>' % self.value_type

    def __str__(self) -> str:
        return 'optional[%s]' % self.value_type

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ROptional) and other.value_type == self.value_type

    def __hash__(self) -> int:
        return hash(('optional', self.value_type))


class Environment:
    """Maintain the register symbol table and manage temp generation"""

    def __init__(self) -> None:
        self.indexes = OrderedDict()  # type: Dict[Value, int]
        self.symtable = {}  # type: Dict[Var, Register]
        self.temp_index = 0

    def regs(self) -> Iterable['Value']:
        return self.indexes.keys()

    def add(self, reg: 'Value', name: str) -> None:
        reg.name = name
        self.indexes[reg] = len(self.indexes)

    def add_local(self, var: Var, typ: RType, is_arg: bool = False) -> 'Register':
        assert isinstance(var, Var)
        reg = Register(typ, var.line, is_arg = is_arg)

        self.symtable[var] = reg
        self.add(reg, var.name())
        return reg

    def lookup(self, var: Var) -> 'Register':
        return self.symtable[var]

    def add_temp(self, typ: RType) -> 'Register':
        assert isinstance(typ, RType)
        reg = Register(typ)
        self.add(reg, 'r%d' % self.temp_index)
        self.temp_index += 1
        return reg

    def add_op(self, reg: 'RegisterOp') -> None:
        if reg.is_void:
            return
        self.add(reg, 'r%d' % self.temp_index)
        self.temp_index += 1

    def format(self, fmt: str, *args: Any) -> str:
        result = []
        i = 0
        arglist = list(args)
        while i < len(fmt):
            n = fmt.find('%', i)
            if n < 0:
                n = len(fmt)
            result.append(fmt[i:n])
            if n < len(fmt):
                typespec = fmt[n + 1]
                arg = arglist.pop(0)
                if typespec == 'r':
                    result.append(arg.name)
                elif typespec == 'd':
                    result.append('%d' % arg)
                elif typespec == 'f':
                    result.append('%f' % arg)
                elif typespec == 'l':
                    result.append('L%d' % arg)
                elif typespec == 's':
                    result.append(str(arg))
                else:
                    raise ValueError('Invalid format sequence %{}'.format(typespec))
                i = n + 2
            else:
                i = n
        return ''.join(result)

    def to_lines(self) -> List[str]:
        result = []
        i = 0
        regs = list(self.regs())

        while i < len(regs):
            i0 = i
            group = [regs[i0].name]
            while i + 1 < len(regs) and regs[i + 1].type == regs[i0].type:
                i += 1
                group.append(regs[i].name)
            i += 1
            result.append('%s :: %s' % (', '.join(group), regs[i0].type))
        return result


ERR_NEVER = 0  # Never generates an exception
ERR_MAGIC = 1  # Generates magic value (c_error_value) based on target RType on exception
ERR_FALSE = 2  # Generates false (bool) on exception


class Value:
    # Source line number
    line = -1
    name = '?'
    type = void_rtype  # type: RType
    is_borrowed = False

    def __init__(self, line: int) -> None:
        self.line = line

    @property
    def is_void(self) -> bool:
        return isinstance(self.type, RVoid)

    @abstractmethod
    def to_str(self, env: Environment) -> str:
        raise NotImplementedError


class Register(Value):
    def __init__(self, type: RType, line: int = -1, is_arg: bool = False, name: str = '') -> None:
        super().__init__(line)
        self.name = name
        self.type = type
        self.is_arg = is_arg
        self.is_borrowed = is_arg

    def to_str(self, env: Environment) -> str:
        return self.name

    @property
    def is_void(self) -> bool:
        return False


# Unfortunately we have visitors which are statement-like rather than expression-like.
# It doesn't make sense to have the visitor return Optional[Value] because every
# method either always returns no value or returns a value.
#
# Eventually we may want to separate expression visitors and statement-like visitors at
# the type level but until then returning INVALID_VALUE from a statement-like visitor
# seems acceptable.
INVALID_VALUE = Register(void_rtype, name='<INVALID_VALUE>')


class Op(Value):
    def __init__(self, line: int) -> None:
        super().__init__(line)

    def can_raise(self) -> bool:
        # Override this is if Op may raise an exception. Note that currently the fact that
        # only RegisterOps may raise an exception in hard coded in some places.
        return False

    @abstractmethod
    def accept(self, visitor: 'OpVisitor[T]') -> T:
        pass


class Goto(Op):
    """Unconditional jump."""

    error_kind = ERR_NEVER

    def __init__(self, label: Label, line: int = -1) -> None:
        super().__init__(line)
        self.label = label

    def __repr__(self) -> str:
        return '<Goto %d>' % self.label

    def to_str(self, env: Environment) -> str:
        return env.format('goto %l', self.label)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_goto(self)


class Branch(Op):
    """if [not] r1 goto 1 else goto 2"""

    # Branch ops must *not* raise an exception. If a comparison, for example, can raise an
    # exception, it needs to split into two opcodes and only the first one may fail.
    error_kind = ERR_NEVER

    BOOL_EXPR = 100
    IS_NONE = 101
    IS_ERROR = 102  # Check for magic c_error_value (works for arbitary types)

    op_names = {
        BOOL_EXPR: ('%r', 'bool'),
        IS_NONE: ('%r is None', 'object'),
        IS_ERROR: ('is_error(%r)', ''),
    }

    def __init__(self, left: Value, true_label: Label,
                 false_label: Label, op: int, line: int = -1) -> None:
        super().__init__(line)
        self.left = left
        self.true = true_label
        self.false = false_label
        self.op = op
        self.negated = False
        # If not None, the true label should generate a traceback entry (func name, line number)
        self.traceback_entry = None  # type: Optional[Tuple[str, int]]

    def sources(self) -> List[Value]:
        return [self.left]

    def to_str(self, env: Environment) -> str:
        fmt, typ = self.op_names[self.op]
        if self.negated:
            fmt = 'not {}'.format(fmt)

        cond = env.format(fmt, self.left)
        tb = ''
        if self.traceback_entry:
            tb = ' (error at %s:%d)' % self.traceback_entry
        fmt = 'if {} goto %l{} else goto %l'.format(cond, tb)
        if typ:
            fmt += ' :: {}'.format(typ)
        return env.format(fmt, self.true, self.false)

    def invert(self) -> None:
        self.true, self.false = self.false, self.true
        self.negated = not self.negated

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_branch(self)


class Return(Op):
    error_kind = ERR_NEVER

    def __init__(self, reg: Value, line: int = -1) -> None:
        super().__init__(line)
        self.reg = reg

    def to_str(self, env: Environment) -> str:
        return env.format('return %r', self.reg)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_return(self)


class Unreachable(Op):
    """Added to the end of non-None returning functions.

    Mypy statically guarantees that the end of the function is not unreachable
    if there is not a return statement.

    This prevents the block formatter from being confused due to lack of a leave
    and also leaves a nifty note in the IR. It is not generally processed by visitors.
    """

    error_kind = ERR_NEVER

    def __init__(self, line: int = -1) -> None:
        super().__init__(line)

    def to_str(self, env: Environment) -> str:
        return "unreachable"

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_unreachable(self)


class RegisterOp(Op):
    """An operation that can be written as r1 = f(r2, ..., rn).

    Takes some registers, performs an operation and generates an output.
    The output register can be None for no output.
    """

    error_kind = -1  # Can this raise exception and how is it signalled; one of ERR_*

    _type = None  # type: Optional[RType]

    def __init__(self, line: int) -> None:
        super().__init__(line)
        assert self.error_kind != -1, 'error_kind not defined'

    @abstractmethod
    def sources(self) -> List[Value]:
        pass

    def can_raise(self) -> bool:
        return self.error_kind != ERR_NEVER

    def unique_sources(self) -> List[Value]:
        result = []  # type: List[Value]
        for reg in self.sources():
            if reg not in result:
                result.append(reg)
        return result


class IncRef(RegisterOp):
    """inc_ref r"""

    error_kind = ERR_NEVER

    def __init__(self, src: Value, line: int = -1) -> None:
        assert src.type.is_refcounted
        super().__init__(line)
        self.src = src

    def to_str(self, env: Environment) -> str:
        s = env.format('inc_ref %r', self.src)
        if is_bool_rprimitive(self.src.type) or is_int_rprimitive(self.src.type):
            s += ' :: {}'.format(short_name(self.src.type.name))
        return s

    def sources(self) -> List[Value]:
        return [self.src]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_inc_ref(self)


class DecRef(RegisterOp):
    """dec_ref r"""

    error_kind = ERR_NEVER

    def __init__(self, src: Value, line: int = -1) -> None:
        assert src.type.is_refcounted
        super().__init__(line)
        self.src = src

    def __repr__(self) -> str:
        return '<DecRef %r>' % self.src

    def to_str(self, env: Environment) -> str:
        s = env.format('dec_ref %r', self.src)
        if is_bool_rprimitive(self.src.type) or is_int_rprimitive(self.src.type):
            s += ' :: {}'.format(short_name(self.src.type.name))
        return s

    def sources(self) -> List[Value]:
        return [self.src]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_dec_ref(self)


class Call(RegisterOp):
    """Native call f(arg, ...)

    The call target can be a module-level function or a class.
    """

    error_kind = ERR_MAGIC

    # TODO: take a FuncIR and extract the ret type
    def __init__(self, ret_type: RType, fn: str, args: List[Value], line: int) -> None:
        super().__init__(line)
        self.fn = fn
        self.args = args
        self.type = ret_type

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        s = '%s(%s)' % (self.fn, args)
        if not self.is_void:
            s = env.format('%r = ', self) + s
        return s

    def sources(self) -> List[Value]:
        return self.args[:]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_call(self)


class MethodCall(RegisterOp):
    """Native method call obj.m(arg, ...) """

    error_kind = ERR_MAGIC

    # TODO: extract the ret type from the receiver
    def __init__(self,
                 ret_type: RType,
                 obj: Value,
                 method: str,
                 args: List[Value],
                 line: int = -1) -> None:
        super().__init__(line)
        self.obj = obj
        self.method = method
        self.args = args
        assert isinstance(obj.type, RInstance), "Methods can only be called on instances"
        self.receiver_type = obj.type
        self.type = ret_type

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        s = env.format('%r.%s(%s)', self.obj, self.method, args)
        if not self.is_void:
            s = env.format('%r = ', self) + s
        return s

    def sources(self) -> List[Value]:
        return self.args[:] + [self.obj]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_method_call(self)


# Python-interopability operations are prefixed with Py. Typically these act as a replacement
# for native operations (without the Py prefix) which call into Python rather than compiled
# native code. For example, this is needed to call builtins.


class PyCall(RegisterOp):
    """Python call f(arg, ...).

    All registers must be unboxed. Corresponds to PyObject_CallFunctionObjArgs in C.
    """

    error_kind = ERR_MAGIC

    def __init__(self, function: Value, args: List[Value],
                 line: int) -> None:
        super().__init__(line)
        self.function = function
        self.args = args
        self.type = object_rprimitive

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        s = env.format('%r(%s)', self.function, args)
        if not self.is_void:
            s = env.format('%r = ', self) + s
        return s + ' :: object'

    def sources(self) -> List[Value]:
        return self.args[:] + [self.function]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_py_call(self)


class PyMethodCall(RegisterOp):
    """Python method call obj.m(arg, ...)

    All registers must be unboxed. Corresponds to PyObject_CallMethodObjArgs in C.
    """

    error_kind = ERR_MAGIC

    def __init__(self,
                 obj: Value,
                 method: Value,
                 args: List[Value],
                 line: int = -1) -> None:
        super().__init__(line)
        self.obj = obj
        self.method = method
        self.args = args
        self.type = object_rprimitive

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        s = env.format('%r.%r(%s)', self.obj, self.method, args)
        if not self.is_void:
            s = env.format('%r = ', self) + s
        return s + ' :: object'

    def sources(self) -> List[Value]:
        return self.args[:] + [self.obj, self.method]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_py_method_call(self)


class PyGetAttr(RegisterOp):
    """dest = obj.attr :: object (using C API)"""

    error_kind = ERR_MAGIC

    def __init__(self, obj: Value, attr: str, line: int) -> None:
        super().__init__(line)
        self.obj = obj
        self.attr = attr
        self.type = object_rprimitive

    def sources(self) -> List[Value]:
        return [self.obj]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r.%s :: object', self, self.obj, self.attr)

    def can_raise(self) -> bool:
        return True

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_py_get_attr(self)


class PySetAttr(RegisterOp):
    """dest = setattr(obj, 'attr', value) (using C API)"""

    error_kind = ERR_FALSE

    def __init__(self, obj: Value, attr: str, value: Value, line: int) -> None:
        super().__init__(line)
        self.obj = obj
        self.attr = attr
        self.value = value
        self.type = bool_rprimitive

    def sources(self) -> List[Value]:
        return [self.obj, self.value]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = setattr(%r, %s, %r)',
                          self, self.obj, repr(self.attr), self.value)

    def can_raise(self) -> bool:
        return True

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_py_set_attr(self)


class EmitterInterface:
    @abstractmethod
    def reg(self, name: Value) -> str:
        raise NotImplementedError

    @abstractmethod
    def temp_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def emit_line(self, line: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def emit_lines(self, *line: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def emit_declaration(self, line: str) -> None:
        raise NotImplementedError


EmitCallback = Callable[[EmitterInterface, List[str], str], None]

OpDescription = NamedTuple(
    'OpDescription', [('name', str),
                      ('arg_types', List[RType]),
                      ('result_type', Optional[RType]),
                      ('is_var_arg', bool),
                      ('error_kind', int),
                      ('format_str', str),
                      ('emit', EmitCallback),
                      ('priority', int)])  # To resolve ambiguities, highest priority wins


class PrimitiveOp(RegisterOp):
    """reg = op(reg, ...)

    These are register-based primitive operations that work on specific
    operand types.

    The details of the operation are defined by the 'desc'
    attribute. The mypyc.ops_* modules define the supported
    operations. mypyc.genops uses the descriptions to look for suitable
    primitive ops.
    """

    def __init__(self,
                 args: List[Value],
                 desc: OpDescription,
                 line: int) -> None:
        if not desc.is_var_arg:
            assert len(args) == len(desc.arg_types)
        self.error_kind = desc.error_kind
        super().__init__(line)
        self.args = args
        self.desc = desc
        if desc.result_type is None:
            assert desc.error_kind == ERR_FALSE  # TODO: No-value ops not supported yet
            self.type = bool_rprimitive
        else:
            self.type = desc.result_type

    def sources(self) -> List[Value]:
        return list(self.args)

    def __repr__(self) -> str:
        return '<PrimitiveOp name=%r args=%s>' % (self.desc.name,
                                                  self.args)

    def to_str(self, env: Environment) -> str:
        params = {}  # type: Dict[str, Any]
        if not self.is_void:
            params['dest'] = env.format('%r', self)
        args = [env.format('%r', arg) for arg in self.args]
        params['args'] = args
        params['comma_args'] = ', '.join(args)
        return self.desc.format_str.format(**params)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_primitive_op(self)


class Assign(Op):
    """dest = int"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, src: Value, line: int = -1) -> None:
        super().__init__(line)
        self.src = src
        self.dest = dest

    def sources(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r', self.dest, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_assign(self)


class LoadInt(RegisterOp):
    """dest = int"""

    error_kind = ERR_NEVER

    def __init__(self, value: int, line: int = -1) -> None:
        super().__init__(line)
        self.value = value
        self.type = int_rprimitive

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %d', self, self.value)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_int(self)


class LoadFloat(RegisterOp):
    """dest = float"""

    error_kind = ERR_FALSE

    def __init__(self, value: float, line: int = -1) -> None:
        super().__init__(line)
        self.value = value
        self.type = float_rprimitive

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %f', self, self.value)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_float(self)


class LoadErrorValue(RegisterOp):
    """dest = <error value for type>"""

    error_kind = ERR_NEVER

    def __init__(self, rtype: RType, line: int = -1) -> None:
        super().__init__(line)
        self.type = rtype

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = <error> :: %s', self, self.type)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_error_value(self)


class GetAttr(RegisterOp):
    """dest = obj.attr (for a native object)"""

    error_kind = ERR_MAGIC

    def __init__(self, obj: Value, attr: str, line: int) -> None:
        super().__init__(line)
        self.obj = obj
        self.attr = attr
        assert isinstance(obj.type, RInstance), 'Attribute access not supported: %s' % obj.type
        self.class_type = obj.type
        self.type = obj.type.attr_type(attr)

    def sources(self) -> List[Value]:
        return [self.obj]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r.%s', self, self.obj, self.attr)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_get_attr(self)


class SetAttr(RegisterOp):
    """obj.attr = src (for a native object)"""

    error_kind = ERR_FALSE

    def __init__(self, obj: Value, attr: str, src: Value, line: int) -> None:
        super().__init__(line)
        self.obj = obj
        self.attr = attr
        self.src = src
        assert isinstance(obj.type, RInstance), 'Attribute access not supported: %s' % obj.type
        self.class_type = obj.type
        self.type = bool_rprimitive

    def sources(self) -> List[Value]:
        return [self.obj, self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r.%s = %r; %r = is_error', self.obj, self.attr, self.src, self)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_set_attr(self)


class LoadStatic(RegisterOp):
    """dest = name :: static"""

    error_kind = ERR_NEVER
    is_borrowed = True

    def __init__(self, type: RType, identifier: str, line: int = -1) -> None:
        super().__init__(line)
        self.identifier = identifier
        self.type = type

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %s :: static', self, self.identifier)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_static(self)


class TupleSet(RegisterOp):
    """dest = (reg, ...) (for fixed-length tuple)"""

    error_kind = ERR_NEVER

    def __init__(self, items: List[Value], line: int) -> None:
        super().__init__(line)
        self.items = items
        self.tuple_type = RTuple([arg.type for arg in items])
        self.type = self.tuple_type

    def sources(self) -> List[Value]:
        return self.items[:]

    def to_str(self, env: Environment) -> str:
        item_str = ', '.join(env.format('%r', item) for item in self.items)
        return env.format('%r = (%s)', self, item_str)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_tuple_set(self)


class TupleGet(RegisterOp):
    """dest = src[n] (for fixed-length tuple)"""

    error_kind = ERR_NEVER

    def __init__(self, src: Value, index: int, line: int) -> None:
        super().__init__(line)
        self.src = src
        self.index = index
        assert isinstance(src.type, RTuple), "TupleGet only operates on tuples"
        self.type = src.type.types[index]

    def sources(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r[%d]', self, self.src, self.index)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_tuple_get(self)


class Cast(RegisterOp):
    """dest = cast(type, src)

    Perform a runtime type check (no representation or value conversion).

    DO NOT increment reference counts.
    """

    error_kind = ERR_MAGIC

    def __init__(self, src: Value, typ: RType, line: int) -> None:
        super().__init__(line)
        self.src = src
        self.type = typ

    def sources(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = cast(%s, %r)', self, self.type, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_cast(self)


class Box(RegisterOp):
    """dest = box(type, src)

    This converts from a potentially unboxed representation to a straight Python object.
    Only supported for types with an unboxed representation.
    """

    error_kind = ERR_NEVER

    def __init__(self, src: Value, line: int = -1) -> None:
        super().__init__(line)
        self.src = src
        self.type = object_rprimitive

    def sources(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = box(%s, %r)', self, self.src.type, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_box(self)


class Unbox(RegisterOp):
    """dest = unbox(type, src)

    This is similar to a cast, but it also changes to a (potentially) unboxed runtime
    representation. Only supported for types with an unboxed representation.
    """

    error_kind = ERR_MAGIC

    def __init__(self, src: Value, typ: RType, line: int) -> None:
        super().__init__(line)
        self.src = src
        self.type = typ

    def sources(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = unbox(%s, %r)', self, self.type, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_unbox(self)


class BasicBlock:
    """Basic IR block.

    Ends with a jump, branch, or return.

    When building the IR, ops that raise exceptions can be included in
    the middle of a basic block, but the exceptions aren't checked.
    Afterwards we perform a transform that inserts explicit checks for
    all error conditions and splits basic blocks accordingly to preserve
    the invariant that a jump, branch or return can only ever appear
    as the final op in a block. Manually inserting error checking ops
    would be boring and error-prone.

    Ops that may terminate the program aren't treated as exits.
    """

    def __init__(self, label: Label) -> None:
        self.label = label
        self.ops = []  # type: List[Op]


class RuntimeArg:
    def __init__(self, name: str, typ: RType) -> None:
        self.name = name
        self.type = typ

    def __repr__(self) -> str:
        return 'RuntimeArg(name=%s, type=%s)' % (self.name, self.type)


class FuncIR:
    """Intermediate representation of a function with contextual information."""

    def __init__(self,
                 name: str,
                 class_name: Optional[str],
                 args: List[RuntimeArg],
                 ret_type: RType,
                 blocks: List[BasicBlock],
                 env: Environment) -> None:
        self.name = name
        self.class_name = class_name
        # TODO: escape ___ in names
        self.cname = name if not class_name else class_name + '___' + name
        self.args = args
        self.ret_type = ret_type
        self.blocks = blocks
        self.env = env

    def __str__(self) -> str:
        return '\n'.join(format_func(self))


class ClassIR:
    """Intermediate representation of a class.

    This also describes the runtime structure of native instances.
    """

    # TODO: Use dictionary for attributes in addition to (or instead of) list.

    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes = []  # type: List[Tuple[str, RType]]
        self.methods = []  # type: List[FuncIR]

    def struct_name(self) -> str:
        return '{}Object'.format(self.name)

    def get_method(self, name: str) -> Optional[FuncIR]:
        matches = [func for func in self.methods if func.name == name]
        return matches[0] if matches else None

    @property
    def type_struct(self) -> str:
        return '{}Type'.format(self.name)


class ModuleIR:
    """Intermediate representation of a module."""

    def __init__(self,
            imports: List[str],
            unicode_literals: Dict[str, str],
            integer_literals: Dict[int, str],
            functions: List[FuncIR],
            classes: List[ClassIR]) -> None:
        self.imports = imports[:]
        self.unicode_literals = unicode_literals
        self.integer_literals = integer_literals
        self.functions = functions
        self.classes = classes

        if 'builtins' not in self.imports:
            self.imports.insert(0, 'builtins')


def type_struct_name(class_name: str) -> str:
    return '{}Type'.format(class_name)


class OpVisitor(Generic[T]):
    @abstractmethod
    def visit_goto(self, op: Goto) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_branch(self, op: Branch) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_return(self, op: Return) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_unreachable(self, op: Unreachable) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_primitive_op(self, op: PrimitiveOp) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_assign(self, op: Assign) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_load_int(self, op: LoadInt) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_load_float(self, op: LoadFloat) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_load_error_value(self, op: LoadErrorValue) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_get_attr(self, op: GetAttr) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_set_attr(self, op: SetAttr) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_load_static(self, op: LoadStatic) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_py_get_attr(self, op: PyGetAttr) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_py_set_attr(self, op: PySetAttr) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_tuple_get(self, op: TupleGet) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_tuple_set(self, op: TupleSet) -> T:
        raise NotImplementedError

    def visit_inc_ref(self, op: IncRef) -> T:
        raise NotImplementedError

    def visit_dec_ref(self, op: DecRef) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_call(self, op: Call) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_py_call(self, op: PyCall) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_method_call(self, op: MethodCall) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_py_method_call(self, op: PyMethodCall) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_cast(self, op: Cast) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_box(self, op: Box) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_unbox(self, op: Unbox) -> T:
        raise NotImplementedError


def format_blocks(blocks: List[BasicBlock], env: Environment) -> List[str]:
    lines = []
    for i, block in enumerate(blocks):
        i == len(blocks) - 1

        lines.append(env.format('%l:', block.label))
        ops = block.ops
        if (isinstance(ops[-1], Goto) and i + 1 < len(blocks) and
                ops[-1].label == blocks[i + 1].label):
            # Hide the last goto if it just goes to the next basic block.
            ops = ops[:-1]
        for op in ops:
            line = '    ' + op.to_str(env)
            lines.append(line)

        if not isinstance(block.ops[-1], (Goto, Branch, Return, Unreachable)):
            # Each basic block needs to exit somewhere.
            lines.append('    [MISSING BLOCK EXIT OPCODE]')
    return lines


def format_func(fn: FuncIR) -> List[str]:
    lines = []
    lines.append('def {}({}):'.format(fn.name, ', '.join(arg.name
                                                         for arg in fn.args)))
    for line in fn.env.to_lines():
        lines.append('    ' + line)
    code = format_blocks(fn.blocks, fn.env)
    lines.extend(code)
    return lines


class RTypeVisitor(Generic[T]):
    @abstractmethod
    def visit_rprimitive(self, typ: RPrimitive) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_rinstance(self, typ: RInstance) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_roptional(self, typ: ROptional) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_rtuple(self, typ: RTuple) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_rvoid(self, typ: RVoid) -> T:
        raise NotImplementedError


# Import various modules that set up global state.
import mypyc.ops_int
import mypyc.ops_str
import mypyc.ops_list
import mypyc.ops_dict
import mypyc.ops_tuple
import mypyc.ops_misc
