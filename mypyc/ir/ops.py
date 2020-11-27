"""Low-level opcodes for compiler intermediate representation (IR).

Opcodes operate on abstract values (Value) in a register machine. Each
value has a type (RType). A value can hold various things:

- local variables (Register)
- intermediate values of expressions (RegisterOp subclasses)
- condition flags (true/false)
- literals (integer literals, True, False, etc.)
"""

from abc import abstractmethod
from typing import (
    List, Sequence, Dict, Generic, TypeVar, Optional, NamedTuple, Tuple, Union
)

from typing_extensions import Final, Type, TYPE_CHECKING
from mypy_extensions import trait

from mypyc.ir.rtypes import (
    RType, RInstance, RTuple, RVoid, is_bool_rprimitive, is_int_rprimitive,
    is_short_int_rprimitive, is_none_rprimitive, object_rprimitive, bool_rprimitive,
    short_int_rprimitive, int_rprimitive, void_rtype, pointer_rprimitive, is_pointer_rprimitive,
    bit_rprimitive, is_bit_rprimitive
)

if TYPE_CHECKING:
    from mypyc.ir.class_ir import ClassIR  # noqa
    from mypyc.ir.func_ir import FuncIR, FuncDecl  # noqa

T = TypeVar('T')


class BasicBlock:
    """Basic IR block.

    Constains a sequence of ops and ends with a jump, branch, or return.

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
# Always fails
ERR_ALWAYS = 3  # type: Final

# Hack: using this line number for an op will suppress it in tracebacks
NO_TRACEBACK_LINE_NO = -10000


class Value:
    """Abstract base class for all IR values.

    These include references to registers, literals, and various operations.
    """

    # Source line number (-1 for no/unknown line)
    line = -1
    # Type of the value or the result of the operation
    type = void_rtype  # type: RType
    is_borrowed = False

    @property
    def is_void(self) -> bool:
        return isinstance(self.type, RVoid)


class Register(Value):
    """A register holds a value of a specific type, and it can be read and mutated.

    Each local variable maps to a register, and they are also used for some
    (but not all) temporary values.
    """

    def __init__(self, type: RType, name: str = '', is_arg: bool = False, line: int = -1) -> None:
        self.type = type
        self.name = name
        self.is_arg = is_arg
        self.is_borrowed = is_arg
        self.line = line

    @property
    def is_void(self) -> bool:
        return False

    def __repr__(self) -> str:
        return '<Register %r at %s>' % (self.name, hex(id(self)))


class Op(Value):
    """Abstract base class for all operations (as opposed to values)."""

    def __init__(self, line: int) -> None:
        self.line = line

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

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_goto(self)


class Branch(ControlOp):
    """Branch based on a value.

    If op is BOOL, branch based on a bit/bool value:
       if [not] r1 goto L1 else goto L2

    If op is IS_ERROR, branch based on whether there is an error value:
       if [not] is_error(r1) goto L1 else goto L2
    """

    # Branch ops must *not* raise an exception. If a comparison, for example, can raise an
    # exception, it needs to split into two opcodes and only the first one may fail.
    error_kind = ERR_NEVER

    BOOL = 100  # type: Final
    IS_ERROR = 101  # type: Final

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
        # BOOL (boolean check) or IS_ERROR (error value check)
        self.op = op
        self.negated = False
        # If not None, the true label should generate a traceback entry (func name, line number)
        self.traceback_entry = None  # type: Optional[Tuple[str, int]]
        # If True, the condition is expected to be usually False (for optimization purposes)
        self.rare = rare

    def sources(self) -> List[Value]:
        return [self.left]

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

    def sources(self) -> List[Value]:
        return []

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_unreachable(self)


class RegisterOp(Op):
    """Abstract base class for operations that can be written as r1 = f(r2, ..., rn).

    Takes some values, performs an operation and generates an output.
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

    def sources(self) -> List[Value]:
        return [self.src]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_inc_ref(self)


class DecRef(RegisterOp):
    """Decrease reference count and free object if zero (dec_ref r).

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

    def sources(self) -> List[Value]:
        return self.args[:] + [self.obj]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_method_call(self)


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

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_assign(self)


class LoadInt(RegisterOp):
    """Load an integer literal."""

    error_kind = ERR_NEVER

    def __init__(self, value: int, line: int = -1, rtype: RType = short_int_rprimitive) -> None:
        super().__init__(line)
        if is_short_int_rprimitive(rtype) or is_int_rprimitive(rtype):
            self.value = value * 2
        else:
            self.value = value
        self.type = rtype

    def sources(self) -> List[Value]:
        return []

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
        if (is_none_rprimitive(self.src.type)
                or is_bool_rprimitive(self.src.type)
                or is_bit_rprimitive(self.src.type)):
            self.is_borrowed = True

    def sources(self) -> List[Value]:
        return [self.src]

    def stolen(self) -> List[Value]:
        return [self.src]

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
    NAME_ERROR = 'NameError'  # type: Final

    def __init__(self, class_name: str, value: Optional[Union[str, Value]], line: int) -> None:
        super().__init__(line)
        self.class_name = class_name
        self.value = value
        self.type = bool_rprimitive

    def sources(self) -> List[Value]:
        return []

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_raise_standard_error(self)


# True steals all arguments, False steals none, a list steals those in matching positions
StealsDescription = Union[bool, List[bool]]


class CallC(RegisterOp):
    """ret = func_call(arg0, arg1, ...)

    A call to a C function
    """

    def __init__(self,
                 function_name: str,
                 args: List[Value],
                 ret_type: RType,
                 steals: StealsDescription,
                 is_borrowed: bool,
                 error_kind: int,
                 line: int,
                 var_arg_idx: int = -1) -> None:
        self.error_kind = error_kind
        super().__init__(line)
        self.function_name = function_name
        self.args = args
        self.type = ret_type
        self.steals = steals
        self.is_borrowed = is_borrowed
        self.var_arg_idx = var_arg_idx  # the position of the first variable argument in args

    def sources(self) -> List[Value]:
        return self.args

    def stolen(self) -> List[Value]:
        if isinstance(self.steals, list):
            assert len(self.steals) == len(self.args)
            return [arg for arg, steal in zip(self.args, self.steals) if steal]
        else:
            return [] if not self.steals else self.sources()

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_call_c(self)


class Truncate(RegisterOp):
    """truncate src: src_type to dst_type

    Truncate a value from type with more bits to type with less bits

    both src_type and dst_type should be non-reference counted integer types or bool
    especially note that int_rprimitive is reference counted so should never be used here
    """

    error_kind = ERR_NEVER

    def __init__(self,
                 src: Value,
                 src_type: RType,
                 dst_type: RType,
                 line: int = -1) -> None:
        super().__init__(line)
        self.src = src
        self.src_type = src_type
        self.type = dst_type

    def sources(self) -> List[Value]:
        return [self.src]

    def stolen(self) -> List[Value]:
        return []

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_truncate(self)


class LoadGlobal(RegisterOp):
    """Load a global variable/pointer"""

    error_kind = ERR_NEVER
    is_borrowed = True

    def __init__(self,
                 type: RType,
                 identifier: str,
                 line: int = -1,
                 ann: object = None) -> None:
        super().__init__(line)
        self.identifier = identifier
        self.type = type
        self.ann = ann  # An object to pretty print with the load

    def sources(self) -> List[Value]:
        return []

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_global(self)


class IntOp(RegisterOp):
    """Binary arithmetic and bitwise operations on integer types

    These ops are low-level and will be eventually generated to simple x op y form.
    The left and right values should be of low-level integer types that support those ops
    """

    error_kind = ERR_NEVER

    # arithmetic
    ADD = 0  # type: Final
    SUB = 1  # type: Final
    MUL = 2  # type: Final
    DIV = 3  # type: Final
    MOD = 4  # type: Final

    # bitwise
    AND = 200  # type: Final
    OR = 201  # type: Final
    XOR = 202  # type: Final
    LEFT_SHIFT = 203  # type: Final
    RIGHT_SHIFT = 204  # type: Final

    op_str = {
        ADD: '+',
        SUB: '-',
        MUL: '*',
        DIV: '/',
        MOD: '%',
        AND: '&',
        OR: '|',
        XOR: '^',
        LEFT_SHIFT: '<<',
        RIGHT_SHIFT: '>>',
    }  # type: Final

    def __init__(self, type: RType, lhs: Value, rhs: Value, op: int, line: int = -1) -> None:
        super().__init__(line)
        self.type = type
        self.lhs = lhs
        self.rhs = rhs
        self.op = op

    def sources(self) -> List[Value]:
        return [self.lhs, self.rhs]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_int_op(self)


class ComparisonOp(RegisterOp):
    """Low-level comparison op.

    Both unsigned and signed comparisons are supported.

    The operands are assumed to be fixed-width integers/pointers. Python
    semantics, such as calling __eq__, are not supported.

    The result is always a bit.

    Supports comparisons between fixed-width integer types and pointer
    types.
    """

    # Must be ERR_NEVER or ERR_FALSE. ERR_FALSE means that a false result
    # indicates that an exception has been raised and should be propagated.
    error_kind = ERR_NEVER

    # S for signed and U for unsigned
    EQ = 100  # type: Final
    NEQ = 101  # type: Final
    SLT = 102  # type: Final
    SGT = 103  # type: Final
    SLE = 104  # type: Final
    SGE = 105  # type: Final
    ULT = 106  # type: Final
    UGT = 107  # type: Final
    ULE = 108  # type: Final
    UGE = 109  # type: Final

    op_str = {
        EQ: '==',
        NEQ: '!=',
        SLT: '<',
        SGT: '>',
        SLE: '<=',
        SGE: '>=',
        ULT: '<',
        UGT: '>',
        ULE: '<=',
        UGE: '>=',
    }  # type: Final

    def __init__(self, lhs: Value, rhs: Value, op: int, line: int = -1) -> None:
        super().__init__(line)
        self.type = bit_rprimitive
        self.lhs = lhs
        self.rhs = rhs
        self.op = op

    def sources(self) -> List[Value]:
        return [self.lhs, self.rhs]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_comparison_op(self)


class LoadMem(RegisterOp):
    """Read a memory location.

    type ret = *(type *)src

    Attributes:
      type: Type of the read value
      src: Pointer to memory to read
      base: If not None, the object from which we are reading memory.
            It's used to avoid the target object from being freed via
            reference counting. If the target is not in reference counted
            memory, or we know that the target won't be freed, it can be
            None.
    """

    error_kind = ERR_NEVER

    def __init__(self, type: RType, src: Value, base: Optional[Value], line: int = -1) -> None:
        super().__init__(line)
        self.type = type
        # TODO: for now we enforce that the src memory address should be Py_ssize_t
        #       later we should also support same width unsigned int
        assert is_pointer_rprimitive(src.type)
        self.src = src
        self.base = base
        self.is_borrowed = True

    def sources(self) -> List[Value]:
        if self.base:
            return [self.src, self.base]
        else:
            return [self.src]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_mem(self)


class SetMem(Op):
    """Write a memory location.

    *(type *)dest = src

    Attributes:
      type: Type of the read value
      dest: Pointer to memory to write
      src: Source value
      base: If not None, the object from which we are reading memory.
            It's used to avoid the target object from being freed via
            reference counting. If the target is not in reference counted
            memory, or we know that the target won't be freed, it can be
            None.
    """

    error_kind = ERR_NEVER

    def __init__(self,
                 type: RType,
                 dest: Value,
                 src: Value,
                 base: Optional[Value],
                 line: int = -1) -> None:
        super().__init__(line)
        self.type = void_rtype
        self.dest_type = type
        self.src = src
        self.dest = dest
        self.base = base

    def sources(self) -> List[Value]:
        if self.base:
            return [self.src, self.base, self.dest]
        else:
            return [self.src, self.dest]

    def stolen(self) -> List[Value]:
        return [self.src]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_set_mem(self)


class GetElementPtr(RegisterOp):
    """Get the address of a struct element"""

    error_kind = ERR_NEVER

    def __init__(self, src: Value, src_type: RType, field: str, line: int = -1) -> None:
        super().__init__(line)
        self.type = pointer_rprimitive
        self.src = src
        self.src_type = src_type
        self.field = field

    def sources(self) -> List[Value]:
        return [self.src]

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_get_element_ptr(self)


class LoadAddress(RegisterOp):
    """Get the address of a value

    ret = (type)&src

    Attributes:
      type: Type of the loaded address(e.g. ptr/object_ptr)
      src: Source value, str for named constants like 'PyList_Type',
           Register for temporary values
    """

    error_kind = ERR_NEVER
    is_borrowed = True

    def __init__(self, type: RType, src: Union[str, Register], line: int = -1) -> None:
        super().__init__(line)
        self.type = type
        self.src = src

    def sources(self) -> List[Value]:
        if isinstance(self.src, Register):
            return [self.src]
        else:
            return []

    def accept(self, visitor: 'OpVisitor[T]') -> T:
        return visitor.visit_load_address(self)


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

    @abstractmethod
    def visit_truncate(self, op: Truncate) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_load_global(self, op: LoadGlobal) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_int_op(self, op: IntOp) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_comparison_op(self, op: ComparisonOp) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_load_mem(self, op: LoadMem) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_set_mem(self, op: SetMem) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_get_element_ptr(self, op: GetElementPtr) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_load_address(self, op: LoadAddress) -> T:
        raise NotImplementedError


# TODO: Should the following definitions live somewhere else?

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

LiteralsMap = Dict[Tuple[Type[object], Union[int, float, str, bytes, complex]], str]
