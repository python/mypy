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
from typing import (
    List, Sequence, Dict, Generic, TypeVar, Optional, Any, NamedTuple, Tuple, Callable,
    Union, Iterable, Set
)
from collections import OrderedDict

from typing_extensions import Final, Type, TYPE_CHECKING
from mypy_extensions import trait

from mypy.nodes import SymbolNode

from mypyc.ir.rtypes import (
    RType, RInstance, RTuple, RVoid, is_bool_rprimitive, is_int_rprimitive,
    is_short_int_rprimitive, is_none_rprimitive, object_rprimitive, bool_rprimitive,
    short_int_rprimitive, int_rprimitive, void_rtype
)
from mypyc.common import short_name

if TYPE_CHECKING:
    from mypyc.ir.class_ir import ClassIR  # noqa
    from mypyc.ir.func_ir import FuncIR, FuncDecl  # noqa

T = TypeVar('T')


# We do a three-pass deserialization scheme in order to resolve name
# references.
#  1. Create an empty ClassIR for each class in an SCC.
#  2. Deserialize all of the functions, which can contain references
#     to ClassIRs in their types
#  3. Deserialize all of the classes, which contain lots of references
#     to the functions they contain. (And to other classes.)
#
# Note that this approach differs from how we deserialize ASTs in mypy itself,
# where everything is deserialized in one pass then a second pass cleans up
# 'cross_refs'. We don't follow that approach here because it seems to be more
# code for not a lot of gain since it is easy in mypyc to identify all the objects
# we might need to reference.
#
# Because of these references, we need to maintain maps from class
# names to ClassIRs and func names to FuncIRs.
#
# These are tracked in a DeserMaps which is passed to every
# deserialization function.
#
# (Serialization and deserialization *will* be used for incremental
# compilation but so far it is not hooked up to anything.)
DeserMaps = NamedTuple('DeserMaps',
                       [('classes', Dict[str, 'ClassIR']), ('functions', Dict[str, 'FuncIR'])])


class AssignmentTarget(object):
    """Abstract base class for assignment targets in IR"""

    type = None  # type: RType

    @abstractmethod
    def to_str(self, env: 'Environment') -> str:
        raise NotImplementedError


class AssignmentTargetRegister(AssignmentTarget):
    """Register as assignment target"""

    def __init__(self, register: 'Register') -> None:
        self.register = register
        self.type = register.type

    def to_str(self, env: 'Environment') -> str:
        return self.register.name


class AssignmentTargetIndex(AssignmentTarget):
    """base[index] as assignment target"""

    def __init__(self, base: 'Value', index: 'Value') -> None:
        self.base = base
        self.index = index
        # TODO: This won't be right for user-defined classes. Store the
        #       lvalue type in mypy and remove this special case.
        self.type = object_rprimitive

    def to_str(self, env: 'Environment') -> str:
        return '{}[{}]'.format(self.base.name, self.index.name)


class AssignmentTargetAttr(AssignmentTarget):
    """obj.attr as assignment target"""

    def __init__(self, obj: 'Value', attr: str) -> None:
        self.obj = obj
        self.attr = attr
        if isinstance(obj.type, RInstance) and obj.type.class_ir.has_attr(attr):
            # Native attribute reference
            self.obj_type = obj.type  # type: RType
            self.type = obj.type.attr_type(attr)
        else:
            # Python attribute reference
            self.obj_type = object_rprimitive
            self.type = object_rprimitive

    def to_str(self, env: 'Environment') -> str:
        return '{}.{}'.format(self.obj.to_str(env), self.attr)


class AssignmentTargetTuple(AssignmentTarget):
    """x, ..., y as assignment target"""

    def __init__(self, items: List[AssignmentTarget],
                 star_idx: Optional[int] = None) -> None:
        self.items = items
        self.star_idx = star_idx
        # The shouldn't be relevant, but provide it just in case.
        self.type = object_rprimitive

    def to_str(self, env: 'Environment') -> str:
        return '({})'.format(', '.join(item.to_str(env) for item in self.items))


class Environment:
    """Maintain the register symbol table and manage temp generation"""

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name
        self.indexes = OrderedDict()  # type: Dict[Value, int]
        self.symtable = OrderedDict()  # type: OrderedDict[SymbolNode, AssignmentTarget]
        self.temp_index = 0
        # All names genereted; value is the number of duplicates seen.
        self.names = {}  # type: Dict[str, int]
        self.vars_needing_init = set()  # type: Set[Value]

    def regs(self) -> Iterable['Value']:
        return self.indexes.keys()

    def add(self, reg: 'Value', name: str) -> None:
        # Ensure uniqueness of variable names in this environment.
        # This is needed for things like list comprehensions, which are their own scope--
        # if we don't do this and two comprehensions use the same variable, we'd try to
        # declare that variable twice.
        unique_name = name
        while unique_name in self.names:
            unique_name = name + str(self.names[name])
            self.names[name] += 1
        self.names[unique_name] = 0
        reg.name = unique_name

        self.indexes[reg] = len(self.indexes)

    def add_local(self, symbol: SymbolNode, typ: RType, is_arg: bool = False) -> 'Register':
        """Add register that represents a symbol to the symbol table.

        Args:
            is_arg: is this a function argument
        """
        assert isinstance(symbol, SymbolNode)
        reg = Register(typ, symbol.line, is_arg=is_arg)
        self.symtable[symbol] = AssignmentTargetRegister(reg)
        self.add(reg, symbol.name)
        return reg

    def add_local_reg(self, symbol: SymbolNode,
                      typ: RType, is_arg: bool = False) -> AssignmentTargetRegister:
        """Like add_local, but return an assignment target instead of value."""
        self.add_local(symbol, typ, is_arg)
        target = self.symtable[symbol]
        assert isinstance(target, AssignmentTargetRegister)
        return target

    def add_target(self, symbol: SymbolNode, target: AssignmentTarget) -> AssignmentTarget:
        self.symtable[symbol] = target
        return target

    def lookup(self, symbol: SymbolNode) -> AssignmentTarget:
        return self.symtable[symbol]

    def add_temp(self, typ: RType) -> 'Register':
        """Add register that contains a temporary value with the given type."""
        assert isinstance(typ, RType)
        reg = Register(typ)
        self.add(reg, 'r%d' % self.temp_index)
        self.temp_index += 1
        return reg

    def add_op(self, reg: 'RegisterOp') -> None:
        """Record the value of an operation."""
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
                    if isinstance(arg, BasicBlock):
                        arg = arg.label
                    result.append('L%s' % arg)
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

    BasicBlocks have an error_handler attribute that determines where
    to jump if an error occurs. If none is specified, an error will
    propagate up out of the function. This is compiled away by the
    `exceptions` module.

    Block labels are used for pretty printing and emitting C code, and get
    filled in by those passes.

    Ops that may terminate the program aren't treated as exits.
    """

    def __init__(self, label: int = -1) -> None:
        self.label = label
        self.ops = []  # type: List[Op]
        self.error_handler = None  # type: Optional[BasicBlock]

    @property
    def terminated(self) -> bool:
        """Does the block end with a jump, branch or return?

        This should always be true after the basic block has been fully built, but
        this is false during construction.
        """
        return bool(self.ops) and isinstance(self.ops[-1], ControlOp)


# Never generates an exception
ERR_NEVER = 0  # type: Final
# Generates magic value (c_error_value) based on target RType on exception
ERR_MAGIC = 1  # type: Final
# Generates false (bool) on exception
ERR_FALSE = 2  # type: Final

# Hack: using this line number for an op will suppress it in tracebacks
NO_TRACEBACK_LINE_NO = -10000


class Value:
    """Abstract base class for all values.

    These include references to registers, literals, and various operations.
    """

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
    """A register holds a value of a specific type, and it can be read and mutated.

    Each local variable maps to a register, and they are also used for some
    (but not all) temporary values.
    """

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


class Op(Value):
    """Abstract base class for all operations (as opposed to values)."""

    def __init__(self, line: int) -> None:
        super().__init__(line)

    def can_raise(self) -> bool:
        # Override this is if Op may raise an exception. Note that currently the fact that
        # only RegisterOps may raise an exception in hard coded in some places.
        return False

    @abstractmethod
    def sources(self) -> List[Value]:
        """All the values the op may read."""
        pass

    def stolen(self) -> List[Value]:
        """Return arguments that have a reference count stolen by this op"""
        return []

    def unique_sources(self) -> List[Value]:
        result = []  # type: List[Value]
        for reg in self.sources():
            if reg not in result:
                result.append(reg)
        return result

    @abstractmethod
    def accept(self, visitor: 'OpVisitor[T]') -> T:
        pass


class ControlOp(Op):
    # Basically just for hierarchy organization.
    # We could plausibly have a targets() method if we wanted.
    pass


class Goto(ControlOp):
    """Unconditional jump."""

    error_kind = ERR_NEVER

    def __init__(self, label: BasicBlock, line: int = -1) -> None:
        super().__init__(line)
        self.label = label

    def __repr__(self) -> str:
        return '<Goto %s>' % self.label.label

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('goto %l', self.label)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_goto(self)


class Branch(ControlOp):
    """if [not] r1 goto 1 else goto 2"""

    # Branch ops must *not* raise an exception. If a comparison, for example, can raise an
    # exception, it needs to split into two opcodes and only the first one may fail.
    error_kind = ERR_NEVER

    BOOL_EXPR = 100  # type: Final
    IS_ERROR = 101  # type: Final

    op_names = {
        BOOL_EXPR: ('%r', 'bool'),
        IS_ERROR: ('is_error(%r)', ''),
    }  # type: Final

    def __init__(self,
                 left: Value,
                 true_label: BasicBlock,
                 false_label: BasicBlock,
                 op: int,
                 line: int = -1,
                 *,
                 rare: bool = False) -> None:
        super().__init__(line)
        # Target value being checked
        self.left = left
        self.true = true_label
        self.false = false_label
        # BOOL_EXPR (boolean check) or IS_ERROR (error value check)
        self.op = op
        self.negated = False
        # If not None, the true label should generate a traceback entry (func name, line number)
        self.traceback_entry = None  # type: Optional[Tuple[str, int]]
        # If True, the condition is expected to be usually False (for optimization purposes)
        self.rare = rare

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
        self.negated = not self.negated

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_branch(self)


class Return(ControlOp):
    """Return a value from a function."""

    error_kind = ERR_NEVER

    def __init__(self, reg: Value, line: int = -1) -> None:
        super().__init__(line)
        self.reg = reg

    def sources(self) -> List[Value]:
        return [self.reg]

    def stolen(self) -> List[Value]:
        return [self.reg]

    def to_str(self, env: Environment) -> str:
        return env.format('return %r', self.reg)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_return(self)


class Unreachable(ControlOp):
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

    def sources(self) -> List[Value]:
        return []

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_unreachable(self)


class RegisterOp(Op):
    """Abstract base class for operations that can be written as r1 = f(r2, ..., rn).

    Takes some registers, performs an operation and generates an output.
    Doesn't do any control flow, but can raise an error.
    """

    error_kind = -1  # Can this raise exception and how is it signalled; one of ERR_*

    _type = None  # type: Optional[RType]

    def __init__(self, line: int) -> None:
        super().__init__(line)
        assert self.error_kind != -1, 'error_kind not defined'

    def can_raise(self) -> bool:
        return self.error_kind != ERR_NEVER


class IncRef(RegisterOp):
    """Increase reference count (inc_ref r)."""

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
    """Decrease referece count and free object if zero (dec_ref r).

    The is_xdec flag says to use an XDECREF, which checks if the
    pointer is NULL first.
    """

    error_kind = ERR_NEVER

    def __init__(self, src: Value, is_xdec: bool = False, line: int = -1) -> None:
        assert src.type.is_refcounted
        super().__init__(line)
        self.src = src
        self.is_xdec = is_xdec

    def __repr__(self) -> str:
        return '<%sDecRef %r>' % ('X' if self.is_xdec else '', self.src)

    def to_str(self, env: Environment) -> str:
        s = env.format('%sdec_ref %r', 'x' if self.is_xdec else '', self.src)
        if is_bool_rprimitive(self.src.type) or is_int_rprimitive(self.src.type):
            s += ' :: {}'.format(short_name(self.src.type.name))
        return s

    def sources(self) -> List[Value]:
        return [self.src]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_dec_ref(self)


class Call(RegisterOp):
    """Native call f(arg, ...).

    The call target can be a module-level function or a class.
    """

    error_kind = ERR_MAGIC

    def __init__(self, fn: 'FuncDecl', args: Sequence[Value], line: int) -> None:
        super().__init__(line)
        self.fn = fn
        self.args = list(args)
        self.type = fn.sig.ret_type

    def to_str(self, env: Environment) -> str:
        args = ', '.join(env.format('%r', arg) for arg in self.args)
        # TODO: Display long name?
        short_name = self.fn.shortname
        s = '%s(%s)' % (short_name, args)
        if not self.is_void:
            s = env.format('%r = ', self) + s
        return s

    def sources(self) -> List[Value]:
        return list(self.args[:])

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_call(self)


class MethodCall(RegisterOp):
    """Native method call obj.m(arg, ...) """

    error_kind = ERR_MAGIC

    def __init__(self,
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
        method_ir = self.receiver_type.class_ir.method_sig(method)
        assert method_ir is not None, "{} doesn't have method {}".format(
            self.receiver_type.name, method)
        self.type = method_ir.ret_type

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


@trait
class EmitterInterface:
    @abstractmethod
    def reg(self, name: Value) -> str:
        raise NotImplementedError

    @abstractmethod
    def c_error_value(self, rtype: RType) -> str:
        raise NotImplementedError

    @abstractmethod
    def temp_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def emit_line(self, line: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def emit_lines(self, *lines: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def emit_declaration(self, line: str) -> None:
        raise NotImplementedError


EmitCallback = Callable[[EmitterInterface, List[str], str], None]

# True steals all arguments, False steals none, a list steals those in matching positions
StealsDescription = Union[bool, List[bool]]

# Description of a primitive operation
OpDescription = NamedTuple(
    'OpDescription', [('name', str),
                      ('arg_types', List[RType]),
                      ('result_type', Optional[RType]),
                      ('is_var_arg', bool),
                      ('error_kind', int),
                      ('format_str', str),
                      ('emit', EmitCallback),
                      ('steals', StealsDescription),
                      ('is_borrowed', bool),
                      ('priority', int)])  # To resolve ambiguities, highest priority wins


class PrimitiveOp(RegisterOp):
    """reg = op(reg, ...)

    These are register-based primitive operations that work on specific
    operand types.

    The details of the operation are defined by the 'desc'
    attribute. The modules under mypyc.primitives define the supported
    operations. mypyc.irbuild uses the descriptions to look for suitable
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

        self.is_borrowed = desc.is_borrowed

    def sources(self) -> List[Value]:
        return list(self.args)

    def stolen(self) -> List[Value]:
        if isinstance(self.desc.steals, list):
            assert len(self.desc.steals) == len(self.args)
            return [arg for arg, steal in zip(self.args, self.desc.steals) if steal]
        else:
            return [] if not self.desc.steals else self.sources()

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
        params['colon_args'] = ', '.join(
            '{}: {}'.format(k, v) for k, v in zip(args[::2], args[1::2])
        )
        return self.desc.format_str.format(**params).strip()

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_primitive_op(self)


class Assign(Op):
    """Assign a value to a register (dest = int)."""

    error_kind = ERR_NEVER

    def __init__(self, dest: Register, src: Value, line: int = -1) -> None:
        super().__init__(line)
        self.src = src
        self.dest = dest

    def sources(self) -> List[Value]:
        return [self.src]

    def stolen(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %r', self.dest, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_assign(self)


class LoadInt(RegisterOp):
    """Load an integer literal."""

    error_kind = ERR_NEVER

    def __init__(self, value: int, line: int = -1) -> None:
        super().__init__(line)
        self.value = value
        self.type = short_int_rprimitive

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = %d', self, self.value)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_int(self)


class LoadErrorValue(RegisterOp):
    """Load an error value.

    Each type has one reserved value that signals an error (exception). This
    loads the error value for a specific type.
    """

    error_kind = ERR_NEVER

    def __init__(self, rtype: RType, line: int = -1,
                 is_borrowed: bool = False,
                 undefines: bool = False) -> None:
        super().__init__(line)
        self.type = rtype
        self.is_borrowed = is_borrowed
        # Undefines is true if this should viewed by the definedness
        # analysis pass as making the register it is assigned to
        # undefined (and thus checks should be added on uses).
        self.undefines = undefines

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        return env.format('%r = <error> :: %s', self, self.type)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_error_value(self)


class GetAttr(RegisterOp):
    """obj.attr (for a native object)"""

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
    """obj.attr = src (for a native object)

    Steals the reference to src.
    """

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

    def stolen(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r.%s = %r; %r = is_error', self.obj, self.attr, self.src, self)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_set_attr(self)


# Default name space for statics, variables
NAMESPACE_STATIC = 'static'  # type: Final

# Static namespace for pointers to native type objects
NAMESPACE_TYPE = 'type'  # type: Final

# Namespace for modules
NAMESPACE_MODULE = 'module'  # type: Final


class LoadStatic(RegisterOp):
    """Load a static name (name :: static).

    Load a C static variable/pointer. The namespace for statics is shared
    for the entire compilation group. You can optionally provide a module
    name and a sub-namespace identifier for additional namespacing to avoid
    name conflicts. The static namespace does not overlap with other C names,
    since the final C name will get a prefix, so conflicts only must be
    avoided with other statics.
    """

    error_kind = ERR_NEVER
    is_borrowed = True

    def __init__(self,
                 type: RType,
                 identifier: str,
                 module_name: Optional[str] = None,
                 namespace: str = NAMESPACE_STATIC,
                 line: int = -1,
                 ann: object = None) -> None:
        super().__init__(line)
        self.identifier = identifier
        self.module_name = module_name
        self.namespace = namespace
        self.type = type
        self.ann = ann  # An object to pretty print with the load

    def sources(self) -> List[Value]:
        return []

    def to_str(self, env: Environment) -> str:
        ann = '  ({})'.format(repr(self.ann)) if self.ann else ''
        name = self.identifier
        if self.module_name is not None:
            name = '{}.{}'.format(self.module_name, name)
        return env.format('%r = %s :: %s%s', self, name, self.namespace, ann)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_static(self)


class InitStatic(RegisterOp):
    """static = value :: static

    Initialize a C static variable/pointer. See everything in LoadStatic.
    """

    error_kind = ERR_NEVER

    def __init__(self,
                 value: Value,
                 identifier: str,
                 module_name: Optional[str] = None,
                 namespace: str = NAMESPACE_STATIC,
                 line: int = -1) -> None:
        super().__init__(line)
        self.identifier = identifier
        self.module_name = module_name
        self.namespace = namespace
        self.value = value

    def sources(self) -> List[Value]:
        return [self.value]

    def to_str(self, env: Environment) -> str:
        name = self.identifier
        if self.module_name is not None:
            name = '{}.{}'.format(self.module_name, name)
        return env.format('%s = %r :: %s', name, self.value, self.namespace)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_init_static(self)


class TupleSet(RegisterOp):
    """dest = (reg, ...) (for fixed-length tuple)"""

    error_kind = ERR_NEVER

    def __init__(self, items: List[Value], line: int) -> None:
        super().__init__(line)
        self.items = items
        # Don't keep track of the fact that an int is short after it
        # is put into a tuple, since we don't properly implement
        # runtime subtyping for tuples.
        self.tuple_type = RTuple(
            [arg.type if not is_short_int_rprimitive(arg.type) else int_rprimitive
             for arg in items])
        self.type = self.tuple_type

    def sources(self) -> List[Value]:
        return self.items[:]

    def to_str(self, env: Environment) -> str:
        item_str = ', '.join(env.format('%r', item) for item in self.items)
        return env.format('%r = (%s)', self, item_str)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_tuple_set(self)


class TupleGet(RegisterOp):
    """Get item of a fixed-length tuple (src[n])."""

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
    """cast(type, src)

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

    def stolen(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = cast(%s, %r)', self, self.type, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_cast(self)


class Box(RegisterOp):
    """box(type, src)

    This converts from a potentially unboxed representation to a straight Python object.
    Only supported for types with an unboxed representation.
    """

    error_kind = ERR_NEVER

    def __init__(self, src: Value, line: int = -1) -> None:
        super().__init__(line)
        self.src = src
        self.type = object_rprimitive
        # When we box None and bool values, we produce a borrowed result
        if is_none_rprimitive(self.src.type) or is_bool_rprimitive(self.src.type):
            self.is_borrowed = True

    def sources(self) -> List[Value]:
        return [self.src]

    def stolen(self) -> List[Value]:
        return [self.src]

    def to_str(self, env: Environment) -> str:
        return env.format('%r = box(%s, %r)', self, self.src.type, self.src)

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_box(self)


class Unbox(RegisterOp):
    """unbox(type, src)

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


class RaiseStandardError(RegisterOp):
    """Raise built-in exception with an optional error string.

    We have a separate opcode for this for convenience and to
    generate smaller, more idiomatic C code.
    """

    # TODO: Make it more explicit at IR level that this always raises

    error_kind = ERR_FALSE

    VALUE_ERROR = 'ValueError'  # type: Final
    ASSERTION_ERROR = 'AssertionError'  # type: Final
    STOP_ITERATION = 'StopIteration'  # type: Final
    UNBOUND_LOCAL_ERROR = 'UnboundLocalError'  # type: Final
    RUNTIME_ERROR = 'RuntimeError'  # type: Final

    def __init__(self, class_name: str, value: Optional[Union[str, Value]], line: int) -> None:
        super().__init__(line)
        self.class_name = class_name
        self.value = value
        self.type = bool_rprimitive

    def to_str(self, env: Environment) -> str:
        if self.value is not None:
            if isinstance(self.value, str):
                return 'raise %s(%r)' % (self.class_name, self.value)
            elif isinstance(self.value, Value):
                return env.format('raise %s(%r)', self.class_name, self.value)
            else:
                assert False, 'value type must be either str or Value'
        else:
            return 'raise %s' % self.class_name

    def sources(self) -> List[Value]:
        return []

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_raise_standard_error(self)


class CallC(RegisterOp):
    """ret = func_call(arg0, arg1, ...)

    A call to a C function
    """

    error_kind = ERR_MAGIC

    def __init__(self, function_name: str, args: List[Value], ret_type: RType, line: int) -> None:
        super().__init__(line)
        self.function_name = function_name
        self.args = args
        self.type = ret_type

    def to_str(self, env: Environment) -> str:
        args_str = ', '.join(env.format('%r', arg) for arg in self.args)
        return env.format('%r = %s(%s)', self, self.function_name, args_str)

    def sources(self) -> List[Value]:
        return self.args

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_call_c(self)


@trait
class OpVisitor(Generic[T]):
    """Generic visitor over ops (uses the visitor design pattern)."""

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
    def visit_init_static(self, op: InitStatic) -> T:
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
    def visit_method_call(self, op: MethodCall) -> T:
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

    @abstractmethod
    def visit_raise_standard_error(self, op: RaiseStandardError) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_call_c(self, op: CallC) -> T:
        raise NotImplementedError


# TODO: Should this live somewhere else?
LiteralsMap = Dict[Tuple[Type[object], Union[int, float, str, bytes, complex]], str]


# Import mypyc.primitives.registry that will set up set up global primitives tables.
import mypyc.primitives.registry  # noqa
