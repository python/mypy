"""Representation of low-level opcodes for compiler intermediate representation (IR).

Opcodes operate on abstract registers in a register machine. Each
register has a type and a name, specified in an environment. A register
can hold various things:

- local variables
- intermediate values of expressions
- condition flags (true/false)
- literals (integer literals, True, False, etc.)
"""

from abc import abstractmethod
import re
from typing import List, Dict, Generic, TypeVar, Optional, Any, NamedTuple, Tuple, NewType

from mypy.nodes import Var


T = TypeVar('T')

Register = NewType('Register', int)
Label = NewType('Label', int)


# Unfortunately we have visitors which are statement-like rather than expression-like.
# It doesn't make sense to have the visitor return Optional[Register] because every
# method either always returns no register or returns a register.
#
# Eventually we may want to separate expression visitors and statement-like visitors at
# the type level but until then returning INVALID_REGISTER from a statement-like visitor
# seems acceptable.
INVALID_REGISTER = Register(-99999)


# Similarly this is used for placeholder labels which aren't assigned yet (but will
# be eventually. Its kind of a hack.
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
        return '<RPrimitive %s>'% self.name


# Used to represent arbitrary objects and dynamically typed values
object_rprimitive = RPrimitive('builtins.object', is_unboxed=False, is_refcounted=True)

int_rprimitive = RPrimitive('builtins.int', is_unboxed=True, is_refcounted=True, ctype='CPyTagged')

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
    """Keep track of names and types of registers."""

    def __init__(self) -> None:
        self.names = []  # type: List[str]
        self.types = []  # type: List[RType]
        self.symtable = {}  # type: Dict[Var, Register]
        self.temp_index = 0

    def num_regs(self) -> int:
        return len(self.names)

    def add_local(self, var: Var, typ: RType) -> Register:
        assert isinstance(var, Var)
        self.names.append(var.name())
        self.types.append(typ)

        i = len(self.names) - 1

        reg = Register(i)
        self.symtable[var] = reg
        return reg

    def lookup(self, var: Var) -> Register:
        return self.symtable[var]

    def add_temp(self, typ: RType) -> Register:
        assert isinstance(typ, RType)
        self.names.append('r%d' % self.temp_index)
        self.temp_index += 1
        self.types.append(typ)
        return Register(len(self.names) - 1)

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
                    result.append(self.names[arg])
                elif typespec == 'd':
                    result.append('%d' % arg)
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
        n = len(self.names)
        while i < n:
            i0 = i
            while i + 1 < n and self.types[i + 1] == self.types[i0]:
                i += 1
            i += 1
            result.append('%s :: %s' % (', '.join(self.names[i0:i]), self.types[i0]))
        return result


ERR_NEVER = 0  # Never generates an exception
ERR_MAGIC = 1  # Generates magic value (c_error_value) based on target RType on exception
ERR_FALSE = 2  # Generates false (bool) on exception


class Op:
    # Source line number
    line = -1

    def __init__(self, line: int) -> None:
        self.line = line

    def can_raise(self) -> bool:
        # Override this is if Op may raise an exception. Note that currently the fact that
        # only RegisterOps may raise an exception in hard coded in some places.
        return False

    @abstractmethod
    def to_str(self, env: Environment) -> str:
        raise NotImplementedError

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
    """if [not] r1 op r2 goto 1 else goto 2"""

    # Branch ops must *not* raise an exception. If a comparison, for example, can raise an
    # exception, it needs to split into two opcodes and only the first one may fail.
    error_kind = ERR_NEVER

    INT_EQ = 10
    INT_NE = 11
    INT_LT = 12
    INT_LE = 13
    INT_GT = 14
    INT_GE = 15

    # Unlike the above, these are unary operations so they only uses the "left" register
    # ("right" should be INVALID_REGISTER).
    BOOL_EXPR = 100
    IS_NONE = 101
    IS_ERROR = 102  # Check for magic c_error_value (works for arbitary types)

    op_names = {
        INT_EQ:  ('==', 'int'),
        INT_NE:  ('!=', 'int'),
        INT_LT:  ('<', 'int'),
        INT_LE:  ('<=', 'int'),
        INT_GT:  ('>', 'int'),
        INT_GE:  ('>=', 'int'),
    }

    unary_op_names = {
        BOOL_EXPR: ('%r', 'bool'),
        IS_NONE: ('%r is None', 'object'),
        IS_ERROR: ('is_error(%r)', ''),
    }

    def __init__(self, left: Register, right: Register, true_label: Label,
                 false_label: Label, op: int, line: int = -1) -> None:
        super().__init__(line)
        self.left = left
        self.right = right
        self.true = true_label
        self.false = false_label
        self.op = op
        self.negated = False
        # If not None, the true label should generate a traceback entry (func name, line number)
        self.traceback_entry = None  # type: Optional[Tuple[str, int]]

    def sources(self) -> List[Register]:
        if self.right != INVALID_REGISTER:
            return [self.left, self.right]
        else:
            return [self.left]

    def to_str(self, env: Environment) -> str:
        # Right not used for BOOL_EXPR
        if self.op in self.op_names:
            if self.negated:
                fmt = 'not %r {} %r'
            else:
                fmt = '%r {} %r'
            op, typ = self.op_names[self.op]
            fmt = fmt.format(op)
        else:
            fmt, typ = self.unary_op_names[self.op]
            if self.negated:
                fmt = 'not {}'.format(fmt)

        cond = env.format(fmt, self.left, self.right)
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

    def __init__(self, reg: Register, line: int = -1) -> None:
        super().__init__(line)
        assert isinstance(reg, int), 'Invalid register: %r' % reg
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

    def __init__(self, dest: Optional[Register], line: int) -> None:
        super().__init__(line)
        assert dest != INVALID_REGISTER
        assert self.error_kind != -1, 'error_kind not defined'
        self._dest = dest

    # This is a read-only property so that subclasses can override it
    # without the Optional.
    @property
    def dest(self) -> Optional[Register]:
        return self._dest

    @abstractmethod
    def sources(self) -> List[Register]:
        pass

    def can_raise(self) -> bool:
        return self.error_kind != ERR_NEVER

    def unique_sources(self) -> List[Register]:
        result = []  # type: List[Register]
        for reg in self.sources():
            if reg not in result:
                result.append(reg)
        return result


class StrictRegisterOp(RegisterOp):
    """An operation that can be written as r1 = f(r2, ..., rn), where r1 must exist.

    Like RegisterOp but without the option of r1 being None.
    """

    def __init__(self, dest: Register, line: int) -> None:
        super().__init__(dest, line)

    @property
    def dest(self) -> Register:
        # We could do this soundly without any checks by duplicating
        # the _dest field, but that is kind of silly...
        assert self._dest is not None
        return self._dest

class IncRef(StrictRegisterOp):
    """inc_ref r"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, typ: RType, line: int = -1) -> None:
        assert typ.is_refcounted
        super().__init__(dest, line)
        self.target_type = typ

    def to_str(self, env: Environment) -> str:
        s = env.format('inc_ref %r', self.dest)
        if is_bool_rprimitive(self.target_type) or is_int_rprimitive(self.target_type):
            s += ' :: {}'.format(short_name(self.target_type.name))
        return s

    def sources(self) -> List[Register]:
        return [self.dest]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_inc_ref(self)


class DecRef(StrictRegisterOp):
    """dec_ref r"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, typ: RType, line: int = -1) -> None:
        assert typ.is_refcounted
        super().__init__(dest, line)
        self.target_type = typ

    def __repr__(self) -> str:
        return '<DecRef %d>' % self.dest

    def to_str(self, env: Environment) -> str:
        s = env.format('dec_ref %r', self.dest)
        if is_bool_rprimitive(self.target_type) or is_int_rprimitive(self.target_type):
            s += ' :: {}'.format(short_name(self.target_type.name))
        return s

    def sources(self) -> List[Register]:
        return [self.dest]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_dec_ref(self)


class Call(RegisterOp):
    """Native call f(arg, ...)

    The call target can be a module-level function or a class.
    """

    error_kind = ERR_MAGIC

    def __init__(self, dest: Optional[Register], fn: str, args: List[Register], line: int) -> None:
        super().__init__(dest, line)
        self.fn = fn
        self.args = args

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        s = '%s(%s)' % (self.fn, args)
        if self.dest is not None:
            s = env.format('%r = ', self.dest) + s
        return s

    def sources(self) -> List[Register]:
        return self.args[:]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_call(self)


# Python-interopability operations are prefixed with Py. Typically these act as a replacement
# for native operations (without the Py prefix) which call into Python rather than compiled
# native code. For example, this is needed to call builtins.


class PyCall(RegisterOp):
    """Python call f(arg, ...).

    All registers must be unboxed. Corresponds to PyObject_CallFunctionObjArgs in C.
    """

    error_kind = ERR_MAGIC

    def __init__(self, dest: Optional[Register], function: Register, args: List[Register],
                 line: int) -> None:
        super().__init__(dest, line)
        self.function = function
        self.args = args

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        s = env.format('%r(%s)', self.function, args)
        if self.dest is not None:
            s = env.format('%r = ', self.dest) + s
        return s + ' :: py'

    def sources(self) -> List[Register]:
        return self.args[:] + [self.function]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_py_call(self)


class PyMethodCall(RegisterOp):
    """Python method call obj.m(arg, ...)

    All registers must be unboxed. Corresponds to PyObject_CallMethodObjArgs in C.
    """

    error_kind = ERR_MAGIC

    def __init__(self,
            dest: Optional[Register],
            obj: Register,
            method: Register,
            args: List[Register],
            line: int = -1) -> None:
        super().__init__(dest, line)
        self.obj = obj
        self.method = method
        self.args = args

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        s = env.format('%r.%r(%s)', self.obj, self.method, args)
        if self.dest is not None:
            s = env.format('%r = ', self.dest) + s
        return s + ' :: py'

    def sources(self) -> List[Register]:
        return self.args[:] + [self.obj, self.method]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_py_method_call(self)


class PyGetAttr(StrictRegisterOp):
    """dest = left.right :: py"""

    error_kind = ERR_MAGIC

    def __init__(self, dest: Register, left: Register, right: str, line: int) -> None:
        super().__init__(dest, line)
        self.left = left
        self.right = right

    def sources(self) -> List[Register]:
        return [self.left]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r.%s', self.dest, self.left, self.right)

    def can_raise(self) -> bool:
        return True

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_py_get_attr(self)


VAR_ARG = -1

# Primitive op inds
OP_MISC = 0    # No specific kind
OP_BINARY = 1  # Regular binary operation such as +
OP_SPECIAL_METHOD_CALL = 2

OpDesc = NamedTuple('OpDesc', [('name', str),        # Symbolic name of the operation
                               ('num_args', int),    # Number of args (or VAR_ARG for any number)
                               ('type', str),        # Type string, used for disambiguation
                               ('format_str', str),  # Format string for pretty printing
                               ('is_void', bool),    # Is this a void op (no value produced)?
                               ('kind', int),
                               ('error_kind', int)])


def make_op(name: str, num_args: int, typ: str, format_str: Optional[str] = None,
            is_void: bool = False, kind: int = OP_MISC, error_kind: int = ERR_NEVER) -> OpDesc:
    if format_str is None:
        # Default format strings for some common things.
        if name == '[]':
            format_str = '{dest} = {args[0]}[{args[1]}] :: %s' % typ
        elif name == '[]=':
            if not is_void:
                assert error_kind == ERR_FALSE
                format_str = '{args[0]}[{args[1]}] = {args[2]} :: %s; {dest} = is_error' % typ
            else:
                format_str = '{args[0]}[{args[1]}] = {args[2]} :: %s' % typ
        elif kind == OP_BINARY:
            assert not is_void
            format_str = '{dest} = {args[0]} %s {args[1]} :: %s' % (name, typ)
        elif kind == OP_SPECIAL_METHOD_CALL:
            args_joined = ', '.join(['{args[%d]}' % i for i in range (1, num_args)])
            if is_void:
                format_str = ('{args[0]}.%s ' + args_joined + ' :: %s') % (name, typ)
            else:
                format_str = ('{dest} = {args[0]}.%s ' + args_joined + ' :: %s') % (name, typ)
        elif num_args == 1:
            if name[-1].isalpha():
                name += ' '
            format_str = '{dest} = %s{args[0]} :: %s' % (name, typ)
        else:
            assert False, 'format_str must be defined; no default format available'
    return OpDesc(name, num_args, typ, format_str, is_void, kind, error_kind)


class PrimitiveOp(RegisterOp):
    """dest = op(reg, ...)

    These are register-based primitive operations that typically work on
    specific operand types.
    """

    # Binary
    INT_ADD = make_op('+', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_SUB = make_op('-', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_MUL = make_op('*', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_DIV = make_op('//', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_MOD = make_op('%', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_AND = make_op('&', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_OR =  make_op('|', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_XOR = make_op('^', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_SHL = make_op('<<', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)
    INT_SHR = make_op('>>', 2, 'int', kind=OP_BINARY, error_kind=ERR_NEVER)

    # Unary
    INT_NEG = make_op('-', 1, 'int', error_kind=ERR_NEVER)
    LIST_LEN = make_op('len', 1, 'list', error_kind=ERR_NEVER)
    HOMOGENOUS_TUPLE_LEN = make_op('len', 1, 'sequence_tuple', error_kind=ERR_NEVER)
    LIST_TO_HOMOGENOUS_TUPLE = make_op('tuple', 1, 'list', error_kind=ERR_NEVER)

    # Other
    NONE = make_op('None', 0, 'None', format_str='{dest} = None', error_kind=ERR_NEVER)
    TRUE = make_op('True', 0, 'True', format_str='{dest} = True', error_kind=ERR_NEVER)
    FALSE = make_op('False', 0, 'False', format_str='{dest} = False', error_kind=ERR_NEVER)

    # List
    LIST_GET = make_op('[]', 2, 'list', kind=OP_BINARY, error_kind=ERR_MAGIC)
    LIST_REPEAT = make_op('*', 2, 'list', kind=OP_BINARY, error_kind=ERR_MAGIC)
    LIST_SET = make_op('[]=', 3, 'list', error_kind=ERR_FALSE)
    NEW_LIST = make_op('new', VAR_ARG, 'list', format_str='{dest} = [{comma_args}]',
                       error_kind=ERR_MAGIC)
    LIST_APPEND = make_op('append', 2, 'list', format_str='{dest} = {args[0]}.append({args[1]})',
                          error_kind=ERR_FALSE)

    # Dict
    DICT_GET = make_op('[]', 2, 'dict', kind=OP_BINARY, error_kind=ERR_MAGIC)
    DICT_SET = make_op('[]=', 3, 'dict', error_kind=ERR_FALSE)
    NEW_DICT = make_op('new', 0, 'dict', format_str='{dest} = {{}}', error_kind=ERR_MAGIC)
    DICT_CONTAINS = make_op('in', 2, 'dict', kind=OP_BINARY, error_kind=ERR_MAGIC)
    DICT_UPDATE = make_op('update', 2, 'dict', kind=OP_SPECIAL_METHOD_CALL, error_kind=ERR_FALSE)

    # Sequence Tuple
    HOMOGENOUS_TUPLE_GET = make_op('[]', 2, 'sequence_tuple', kind=OP_BINARY, error_kind=ERR_MAGIC)

    # Tuple
    NEW_TUPLE = make_op('new', VAR_ARG, 'tuple', format_str='{dest} = ({comma_args})',
                        error_kind=ERR_MAGIC)

    def __init__(self, dest: Optional[Register], desc: OpDesc, args: List[Register],
                 line: int) -> None:
        """Create a primitive op.

        If desc.is_void is true, dest should be None.
        """
        self.error_kind = desc.error_kind
        super().__init__(dest, line)
        if desc.num_args != VAR_ARG:
            assert len(args) == desc.num_args
        self.desc = desc
        self.args = args

    def sources(self) -> List[Register]:
        return list(self.args)

    def __repr__(self) -> str:
        return '<PrimiveOp name=%r type=%s dest=%s args=%s>' % (self.desc.name,
                                                                self.desc.type,
                                                                self.dest,
                                                                self.args)

    def to_str(self, env: Environment) -> str:
        params = {}  # type: Dict[str, Any]
        if self.dest is not None and self.dest != INVALID_REGISTER:
            params['dest'] = env.format('%r', self.dest)
        args = [env.format('%r', arg) for arg in self.args]
        params['args'] = args
        params['comma_args'] = ', '.join(args)
        return self.desc.format_str.format(**params)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_primitive_op(self)


class Assign(StrictRegisterOp):
    """dest = int"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, src: Register, line: int = -1) -> None:
        super().__init__(dest, line)
        self.src = src

    def sources(self) -> List[Register]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r', self.dest, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_assign(self)


class LoadInt(StrictRegisterOp):
    """dest = int"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, value: int, line: int = -1) -> None:
        super().__init__(dest, line)
        self.value = value

    def sources(self) -> List[Register]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %d', self.dest, self.value)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_int(self)


class LoadErrorValue(StrictRegisterOp):
    """dest = <error value for type>"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, rtype: RType, line: int = -1) -> None:
        super().__init__(dest, line)
        self.rtype = rtype

    def sources(self) -> List[Register]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = <error> :: %s', self.dest, self.rtype)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_error_value(self)


class GetAttr(StrictRegisterOp):
    """dest = obj.attr (for a native object)"""

    error_kind = ERR_MAGIC

    def __init__(self, dest: Register, obj: Register, attr: str, rtype: RInstance,
                 line: int) -> None:
        super().__init__(dest, line)
        self.obj = obj
        self.attr = attr
        self.rtype = rtype

    def sources(self) -> List[Register]:
        return [self.obj]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r.%s', self.dest, self.obj, self.attr)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_get_attr(self)


class SetAttr(StrictRegisterOp):
    """obj.attr = src (for a native object)"""

    error_kind = ERR_FALSE

    def __init__(self, dest: Register, obj: Register, attr: str, src: Register, rtype: RInstance,
                 line: int) -> None:
        super().__init__(dest, line)
        self.obj = obj
        self.attr = attr
        self.src = src
        self.rtype = rtype

    def sources(self) -> List[Register]:
        return [self.obj, self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r.%s = %r; %r = is_error', self.obj, self.attr, self.src, self.dest)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_set_attr(self)


class LoadStatic(StrictRegisterOp):
    """dest = name :: static"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, identifier: str, line: int = -1) -> None:
        super().__init__(dest, line)
        self.identifier = identifier

    def sources(self) -> List[Register]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %s :: static', self.dest, self.identifier)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_static(self)


class TupleGet(StrictRegisterOp):
    """dest = src[n] (for fixed-length tuple)"""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, src: Register, index: int, target_type: RType,
                 line: int) -> None:
        super().__init__(dest, line)
        self.src = src
        self.index = index
        self.target_type = target_type

    def sources(self) -> List[Register]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r[%d]', self.dest, self.src, self.index)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_tuple_get(self)


class Cast(StrictRegisterOp):
    """dest = cast(type, src)

    Perform a runtime type check (no representation or value conversion).

    DO NOT increment reference counts.
    """

    error_kind = ERR_MAGIC

    def __init__(self, dest: Register, src: Register, typ: RType, line: int) -> None:
        super().__init__(dest, line)
        self.src = src
        self.typ = typ

    def sources(self) -> List[Register]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = cast(%s, %r)', self.dest, self.typ, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_cast(self)


class Box(StrictRegisterOp):
    """dest = box(type, src)

    This converts from a potentially unboxed representation to a straight Python object.
    Only supported for types with an unboxed representation.
    """

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, src: Register, typ: RType, line: int = -1) -> None:
        super().__init__(dest, line)
        self.src = src
        self.type = typ

    def sources(self) -> List[Register]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = box(%s, %r)', self.dest, self.type, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_box(self)


class Unbox(StrictRegisterOp):
    """dest = unbox(type, src)

    This is similar to a cast, but it also changes to a (potentially) unboxed runtime
    representation. Only supported for types with an unboxed representation.
    """

    error_kind = ERR_MAGIC

    def __init__(self, dest: Register, src: Register, typ: RType, line: int) -> None:
        super().__init__(dest, line)
        self.src = src
        self.type = typ

    def sources(self) -> List[Register]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = unbox(%s, %r)', self.dest, self.type, self.src)

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

    def __init__(self,
                 name: str,
                 attributes: List[Tuple[str, RType]]) -> None:
        self.name = name
        self.attributes = attributes
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
            functions: List[FuncIR],
            classes: List[ClassIR]) -> None:
        self.imports = imports[:]
        self.unicode_literals = unicode_literals
        self.functions = functions
        self.classes = classes

        if 'builtins' not in self.imports:
            self.imports.insert(0, 'builtins')


def type_struct_name(class_name: str) -> str:
    return '{}Type'.format(class_name)


class OpVisitor(Generic[T]):
    def visit_goto(self, op: Goto) -> T:
        pass

    def visit_branch(self, op: Branch) -> T:
        pass

    def visit_return(self, op: Return) -> T:
        pass

    def visit_unreachable(self, op: Unreachable) -> T:
        pass

    def visit_primitive_op(self, op: PrimitiveOp) -> T:
        pass

    def visit_assign(self, op: Assign) -> T:
        pass

    def visit_load_int(self, op: LoadInt) -> T:
        pass

    def visit_load_error_value(self, op: LoadErrorValue) -> T:
        pass

    def visit_get_attr(self, op: GetAttr) -> T:
        pass

    def visit_set_attr(self, op: SetAttr) -> T:
        pass

    def visit_load_static(self, op: LoadStatic) -> T:
        pass

    def visit_py_get_attr(self, op: PyGetAttr) -> T:
        pass

    def visit_tuple_get(self, op: TupleGet) -> T:
        pass

    def visit_inc_ref(self, op: IncRef) -> T:
        pass

    def visit_dec_ref(self, op: DecRef) -> T:
        pass

    def visit_call(self, op: Call) -> T:
        pass

    def visit_py_call(self, op: PyCall) -> T:
        pass

    def visit_py_method_call(self, op: PyMethodCall) -> T:
        pass

    def visit_cast(self, op: Cast) -> T:
        pass

    def visit_box(self, op: Box) -> T:
        pass

    def visit_unbox(self, op: Unbox) -> T:
        pass


def format_blocks(blocks: List[BasicBlock], env: Environment) -> List[str]:
    lines = []
    for i, block in enumerate(blocks):
        last = i == len(blocks) - 1

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
