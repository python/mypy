"""Types used in the intermediate representation.

These are runtime types (RTypes), as opposed to mypy Type objects.
The latter are only used during type checking and not directly used at
runtime.  Runtime types are derived from mypy types, but there's no
simple one-to-one correspondence. (Here 'runtime' means 'runtime
checked'.)

The generated IR ensures some runtime type safety properties based on
RTypes. Compiled code can assume that the runtime value matches the
static RType of a value. If the RType of a register is 'builtins.str'
(str_rprimitive), for example, the generated IR will ensure that the
register will have a 'str' object.

RTypes are simpler and less expressive than mypy (or PEP 484)
types. For example, all mypy types of form 'list[T]' (for arbitrary T)
are erased to the single RType 'builtins.list' (list_rprimitive).

mypyc.irbuild.mapper.Mapper.type_to_rtype converts mypy Types to mypyc
RTypes.
"""

from abc import abstractmethod
from typing import Optional, Union, List, Dict, Generic, TypeVar, Tuple

from typing_extensions import Final, ClassVar, TYPE_CHECKING

from mypyc.common import JsonDict, short_name, IS_32_BIT_PLATFORM, PLATFORM_SIZE
from mypyc.namegen import NameGenerator

if TYPE_CHECKING:
    from mypyc.ir.ops import DeserMaps
    from mypyc.ir.class_ir import ClassIR

T = TypeVar('T')


class RType:
    """Abstract base class for runtime types (erased, only concrete; no generics)."""

    name = None  # type: str
    # If True, the type has a special unboxed representation. If False, the
    # type is represented as PyObject *. Even if True, the representation
    # may contain pointers.
    is_unboxed = False
    # This is the C undefined value for this type. It's used for initialization
    # if there's no value yet, and for function return value on error/exception.
    c_undefined = None  # type: str
    # If unboxed: does the unboxed version use reference counting?
    is_refcounted = True
    # C type; use Emitter.ctype() to access
    _ctype = None  # type: str

    @abstractmethod
    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        raise NotImplementedError

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

    def serialize(self) -> Union[JsonDict, str]:
        raise NotImplementedError('Cannot serialize {} instance'.format(self.__class__.__name__))


def deserialize_type(data: Union[JsonDict, str], ctx: 'DeserMaps') -> 'RType':
    """Deserialize a JSON-serialized RType.

    Arguments:
        data: The decoded JSON of the serialized type
        ctx: The deserialization maps to use
    """
    # Since there are so few types, we just case on them directly.  If
    # more get added we should switch to a system like mypy.types
    # uses.
    if isinstance(data, str):
        if data in ctx.classes:
            return RInstance(ctx.classes[data])
        elif data in RPrimitive.primitive_map:
            return RPrimitive.primitive_map[data]
        elif data == "void":
            return RVoid()
        else:
            assert False, "Can't find class {}".format(data)
    elif data['.class'] == 'RTuple':
        return RTuple.deserialize(data, ctx)
    elif data['.class'] == 'RUnion':
        return RUnion.deserialize(data, ctx)
    raise NotImplementedError('unexpected .class {}'.format(data['.class']))


class RTypeVisitor(Generic[T]):
    """Generic visitor over RTypes (uses the visitor design pattern)."""

    @abstractmethod
    def visit_rprimitive(self, typ: 'RPrimitive') -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_rinstance(self, typ: 'RInstance') -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_runion(self, typ: 'RUnion') -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_rtuple(self, typ: 'RTuple') -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_rstruct(self, typ: 'RStruct') -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_rvoid(self, typ: 'RVoid') -> T:
        raise NotImplementedError


class RVoid(RType):
    """The void type (no value).

    This is a singleton -- use void_rtype (below) to refer to this instead of
    constructing a new instace.
    """

    is_unboxed = False
    name = 'void'
    ctype = 'void'

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rvoid(self)

    def serialize(self) -> str:
        return 'void'


# Singleton instance of RVoid
void_rtype = RVoid()  # type: Final


class RPrimitive(RType):
    """Primitive type such as 'object' or 'int'.

    These often have custom ops associated with them. The 'object'
    primitive type can be used to hold arbitrary Python objects.

    Different primitive types have different representations, and
    primitives may be unboxed or boxed. Primitive types don't need to
    directly correspond to Python types, but most do.

    NOTE: All supported primitive types are defined below
    (e.g. object_rprimitive).
    """

    # Map from primitive names to primitive types and is used by deserialization
    primitive_map = {}  # type: ClassVar[Dict[str, RPrimitive]]

    def __init__(self,
                 name: str,
                 is_unboxed: bool,
                 is_refcounted: bool,
                 ctype: str = 'PyObject *',
                 size: int = PLATFORM_SIZE) -> None:
        RPrimitive.primitive_map[name] = self

        self.name = name
        self.is_unboxed = is_unboxed
        self._ctype = ctype
        self.is_refcounted = is_refcounted
        self.size = size
        # TODO: For low-level integers, they actually don't have undefined values
        #       we need to figure out some way to represent here.
        if ctype == 'CPyTagged':
            self.c_undefined = 'CPY_INT_TAG'
        elif ctype in ('int32_t', 'int64_t', 'CPyPtr'):
            self.c_undefined = '0'
        elif ctype in ('PyObject *', 'PyTypeObject *'):
            # Boxed types use the null pointer as the error value.
            self.c_undefined = 'NULL'
        elif ctype == 'char':
            self.c_undefined = '2'
        else:
            assert False, 'Unrecognized ctype: %r' % ctype

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rprimitive(self)

    def serialize(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return '<RPrimitive %s>' % self.name


# NOTE: All the supported instances of RPrimitive are defined
# below. Use these instead of creating new instances.

# Used to represent arbitrary objects and dynamically typed (Any)
# values. There are various ops that let you perform generic, runtime
# checked operations on these (that match Python semantics). See the
# ops in mypyc.primitives.misc_ops, including py_getattr_op,
# py_call_op, and many others.
#
# If there is no more specific RType available for some value, we fall
# back to using this type.
#
# NOTE: Even though this is very flexible, this type should be used as
# little as possible, as generic ops are typically slow. Other types,
# including other primitive types and RInstance, are usually much
# faster.
object_rprimitive = RPrimitive('builtins.object', is_unboxed=False,
                               is_refcounted=True)  # type: Final

# Used to represent type object
#
# NOTE: For now it should only be used with misc ops that require type cast
# if in the future this type is used in more places where requires information to
# some/all its fields, consider refactor this type with RStruct
type_object_rprimitive = RPrimitive('type_object', is_unboxed=False, is_refcounted=True,
                                  ctype='PyTypeObject *')  # type: Final

# Arbitrary-precision integer (corresponds to Python 'int'). Small
# enough values are stored unboxed, while large integers are
# represented as a tagged pointer to a Python 'int' PyObject. The
# lowest bit is used as the tag to decide whether it is a signed
# unboxed value (shifted left by one) or a PyObject * pointing to an
# 'int' object. Pointers have the least significant bit set.
#
# The undefined/error value is the null pointer (1 -- only the least
# significant bit is set)).
#
# This cannot represent a subclass of int. An instance of a subclass
# of int is coerced to the corresponding 'int' value.
int_rprimitive = RPrimitive('builtins.int', is_unboxed=True, is_refcounted=True,
                            ctype='CPyTagged')  # type: Final

# An unboxed integer. The representation is the same as for unboxed
# int_rprimitive (shifted left by one). These can be used when an
# integer is known to be small enough to fit size_t (CPyTagged).
short_int_rprimitive = RPrimitive('short_int', is_unboxed=True, is_refcounted=False,
                                  ctype='CPyTagged')  # type: Final

# low level integer (corresponds to C's 'int's).
int32_rprimitive = RPrimitive('int32', is_unboxed=True, is_refcounted=False,
                              ctype='int32_t', size=4)  # type: Final
int64_rprimitive = RPrimitive('int64', is_unboxed=True, is_refcounted=False,
                              ctype='int64_t', size=8)  # type: Final
# integer alias
c_int_rprimitive = int32_rprimitive
if IS_32_BIT_PLATFORM:
    c_pyssize_t_rprimitive = int32_rprimitive
else:
    c_pyssize_t_rprimitive = int64_rprimitive

# low level pointer, represented as integer in C backends
pointer_rprimitive = RPrimitive('ptr', is_unboxed=True, is_refcounted=False,
                              ctype='CPyPtr')  # type: Final

# Floats are represent as 'float' PyObject * values. (In the future
# we'll likely switch to a more efficient, unboxed representation.)
float_rprimitive = RPrimitive('builtins.float', is_unboxed=False,
                              is_refcounted=True)  # type: Final

# An unboxed boolean value. This actually has three possible values
# (0 -> False, 1 -> True, 2 -> error).
bool_rprimitive = RPrimitive('builtins.bool', is_unboxed=True, is_refcounted=False,
                             ctype='char', size=1)  # type: Final

# The 'None' value. The possible values are 0 -> None and 2 -> error.
none_rprimitive = RPrimitive('builtins.None', is_unboxed=True, is_refcounted=False,
                             ctype='char', size=1)  # type: Final

# Python list object (or an instance of a subclass of list).
list_rprimitive = RPrimitive('builtins.list', is_unboxed=False, is_refcounted=True)  # type: Final

# Python dict object (or an instance of a subclass of dict).
dict_rprimitive = RPrimitive('builtins.dict', is_unboxed=False, is_refcounted=True)  # type: Final

# Python set object (or an instance of a subclass of set).
set_rprimitive = RPrimitive('builtins.set', is_unboxed=False, is_refcounted=True)  # type: Final

# Python str object. At the C layer, str is referred to as unicode
# (PyUnicode).
str_rprimitive = RPrimitive('builtins.str', is_unboxed=False, is_refcounted=True)  # type: Final

# Tuple of an arbitrary length (corresponds to Tuple[t, ...], with
# explicit '...').
tuple_rprimitive = RPrimitive('builtins.tuple', is_unboxed=False,
                              is_refcounted=True)  # type: Final


def is_tagged(rtype: RType) -> bool:
    return rtype is int_rprimitive or rtype is short_int_rprimitive


def is_int_rprimitive(rtype: RType) -> bool:
    return rtype is int_rprimitive


def is_short_int_rprimitive(rtype: RType) -> bool:
    return rtype is short_int_rprimitive


def is_int32_rprimitive(rtype: RType) -> bool:
    return rtype is int32_rprimitive


def is_int64_rprimitive(rtype: RType) -> bool:
    return rtype is int64_rprimitive


def is_c_py_ssize_t_rprimitive(rtype: RType) -> bool:
    return rtype is c_pyssize_t_rprimitive


def is_pointer_rprimitive(rtype: RType) -> bool:
    return rtype is pointer_rprimitive


def is_float_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.float'


def is_bool_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.bool'


def is_object_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.object'


def is_type_object_rprimitive(rtype: RType) -> bool:
    return rtype is type_object_rprimitive


def is_none_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.None'


def is_list_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.list'


def is_dict_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.dict'


def is_set_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.set'


def is_str_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.str'


def is_tuple_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and rtype.name == 'builtins.tuple'


def is_sequence_rprimitive(rtype: RType) -> bool:
    return isinstance(rtype, RPrimitive) and (
        is_list_rprimitive(rtype) or is_tuple_rprimitive(rtype) or is_str_rprimitive(rtype)
    )


class TupleNameVisitor(RTypeVisitor[str]):
    """Produce a tuple name based on the concrete representations of types."""

    def visit_rinstance(self, t: 'RInstance') -> str:
        return "O"

    def visit_runion(self, t: 'RUnion') -> str:
        return "O"

    def visit_rprimitive(self, t: 'RPrimitive') -> str:
        if t._ctype == 'CPyTagged':
            return 'I'
        elif t._ctype == 'char':
            return 'C'
        assert not t.is_unboxed, "{} unexpected unboxed type".format(t)
        return 'O'

    def visit_rtuple(self, t: 'RTuple') -> str:
        parts = [elem.accept(self) for elem in t.types]
        return 'T{}{}'.format(len(parts), ''.join(parts))

    def visit_rstruct(self, t: 'RStruct') -> str:
        assert False
        return ""

    def visit_rvoid(self, t: 'RVoid') -> str:
        assert False, "rvoid in tuple?"


class RTuple(RType):
    """Fixed-length unboxed tuple (represented as a C struct).

    These are used to represent mypy TupleType values (fixed-length
    Python tuples). Since this is unboxed, the identity of a tuple
    object is not preserved within compiled code. If the identity of a
    tuple is important, or there is a need to have multiple references
    to a single tuple object, a variable-length tuple should be used
    (tuple_rprimitive or Tuple[T, ...]  with explicit '...'), as they
    are boxed.

    These aren't immutable. However, user code won't be able to mutate
    individual tuple items.
    """

    is_unboxed = True

    def __init__(self, types: List[RType]) -> None:
        self.name = 'tuple'
        self.types = tuple(types)
        self.is_refcounted = any(t.is_refcounted for t in self.types)
        # Generate a unique id which is used in naming corresponding C identifiers.
        # This is necessary since C does not have anonymous structural type equivalence
        # in the same way python can just assign a Tuple[int, bool] to a Tuple[int, bool].
        self.unique_id = self.accept(TupleNameVisitor())
        # Nominally the max c length is 31 chars, but I'm not honestly worried about this.
        self.struct_name = 'tuple_{}'.format(self.unique_id)
        self._ctype = '{}'.format(self.struct_name)

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rtuple(self)

    def __str__(self) -> str:
        return 'tuple[%s]' % ', '.join(str(typ) for typ in self.types)

    def __repr__(self) -> str:
        return '<RTuple %s>' % ', '.join(repr(typ) for typ in self.types)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RTuple) and self.types == other.types

    def __hash__(self) -> int:
        return hash((self.name, self.types))

    def serialize(self) -> JsonDict:
        types = [x.serialize() for x in self.types]
        return {'.class': 'RTuple', 'types': types}

    @classmethod
    def deserialize(cls, data: JsonDict, ctx: 'DeserMaps') -> 'RTuple':
        types = [deserialize_type(t, ctx) for t in data['types']]
        return RTuple(types)


# Exception tuple: (exception class, exception instance, traceback object)
exc_rtuple = RTuple([object_rprimitive, object_rprimitive, object_rprimitive])

# Dictionary iterator tuple: (should continue, internal offset, key, value)
# See mypyc.irbuild.for_helpers.ForDictionaryCommon for more details.
dict_next_rtuple_pair = RTuple(
    [bool_rprimitive, int_rprimitive, object_rprimitive, object_rprimitive]
)
# Same as above but just for key or value.
dict_next_rtuple_single = RTuple(
    [bool_rprimitive, int_rprimitive, object_rprimitive]
)


def compute_rtype_alignment(typ: RType) -> int:
    """Compute alignment of a given type based on platform alignment rule"""
    platform_alignment = PLATFORM_SIZE
    if isinstance(typ, RPrimitive):
        return typ.size
    elif isinstance(typ, RInstance):
        return platform_alignment
    elif isinstance(typ, RUnion):
        return platform_alignment
    else:
        if isinstance(typ, RTuple):
            items = list(typ.types)
        elif isinstance(typ, RStruct):
            items = typ.types
        else:
            assert False, "invalid rtype for computing alignment"
        max_alignment = max([compute_rtype_alignment(item) for item in items])
        return max_alignment


def compute_rtype_size(typ: RType) -> int:
    """Compute unaligned size of rtype"""
    if isinstance(typ, RPrimitive):
        return typ.size
    elif isinstance(typ, RTuple):
        return compute_aligned_offsets_and_size(list(typ.types))[1]
    elif isinstance(typ, RUnion):
        return PLATFORM_SIZE
    elif isinstance(typ, RStruct):
        return compute_aligned_offsets_and_size(typ.types)[1]
    elif isinstance(typ, RInstance):
        return PLATFORM_SIZE
    else:
        assert False, "invalid rtype for computing size"


def compute_aligned_offsets_and_size(types: List[RType]) -> Tuple[List[int], int]:
    """Compute offsets and total size of a list of types after alignment

    Note that the types argument are types of values that are stored
    sequentially with platform default alignment.
    """
    unaligned_sizes = [compute_rtype_size(typ) for typ in types]
    alignments = [compute_rtype_alignment(typ) for typ in types]

    current_offset = 0
    offsets = []
    final_size = 0
    for i in range(len(unaligned_sizes)):
        offsets.append(current_offset)
        if i + 1 < len(unaligned_sizes):
            cur_size = unaligned_sizes[i]
            current_offset += cur_size
            next_alignment = alignments[i + 1]
            # compute aligned offset,
            # check https://en.wikipedia.org/wiki/Data_structure_alignment for more infomation
            current_offset = (current_offset + (next_alignment - 1)) & -next_alignment
        else:
            struct_alignment = max(alignments)
            final_size = current_offset + unaligned_sizes[i]
            final_size = (final_size + (struct_alignment - 1)) & -struct_alignment
    return offsets, final_size


class RStruct(RType):
    """Represent CPython structs"""
    def __init__(self,
                 name: str,
                 names: List[str],
                 types: List[RType]) -> None:
        self.name = name
        self.names = names
        self.types = types
        # generate dummy names
        if len(self.names) < len(self.types):
            for i in range(len(self.types) - len(self.names)):
                self.names.append('_item' + str(i))
        self.offsets, self.size = compute_aligned_offsets_and_size(types)
        self._ctype = name

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rstruct(self)

    def __str__(self) -> str:
        # if not tuple(unamed structs)
        return '%s{%s}' % (self.name, ', '.join(name + ":" + str(typ)
                                                for name, typ in zip(self.names, self.types)))

    def __repr__(self) -> str:
        return '<RStruct %s{%s}>' % (self.name, ', '.join(name + ":" + repr(typ) for name, typ
                                                          in zip(self.names, self.types)))

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, RStruct) and self.name == other.name
                and self.names == other.names and self.types == other.types)

    def __hash__(self) -> int:
        return hash((self.name, tuple(self.names), tuple(self.types)))

    def serialize(self) -> JsonDict:
        assert False

    @classmethod
    def deserialize(cls, data: JsonDict, ctx: 'DeserMaps') -> 'RStruct':
        assert False


class RInstance(RType):
    """Instance of user-defined class (compiled to C extension class).

    The runtime representation is 'PyObject *', and these are always
    boxed and thus reference-counted.

    These support fast method calls and fast attribute access using
    vtables, and they usually use a dict-free, struct-based
    representation of attributes. Method calls and attribute access
    can skip the vtable if we know that there is no overriding.

    These are also sometimes called 'native' types, since these have
    the most efficient representation and ops (along with certain
    RPrimitive types and RTuple).
    """

    is_unboxed = False

    def __init__(self, class_ir: 'ClassIR') -> None:
        # name is used for formatting the name in messages and debug output
        # so we want the fullname for precision.
        self.name = class_ir.fullname
        self.class_ir = class_ir
        self._ctype = 'PyObject *'

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rinstance(self)

    def struct_name(self, names: NameGenerator) -> str:
        return self.class_ir.struct_name(names)

    def getter_index(self, name: str) -> int:
        return self.class_ir.vtable_entry(name)

    def setter_index(self, name: str) -> int:
        return self.getter_index(name) + 1

    def method_index(self, name: str) -> int:
        return self.class_ir.vtable_entry(name)

    def attr_type(self, name: str) -> RType:
        return self.class_ir.attr_type(name)

    def __repr__(self) -> str:
        return '<RInstance %s>' % self.name

    def serialize(self) -> str:
        return self.name


class RUnion(RType):
    """union[x, ..., y]"""

    is_unboxed = False

    def __init__(self, items: List[RType]) -> None:
        self.name = 'union'
        self.items = items
        self.items_set = frozenset(items)
        self._ctype = 'PyObject *'

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_runion(self)

    def __repr__(self) -> str:
        return '<RUnion %s>' % ', '.join(str(item) for item in self.items)

    def __str__(self) -> str:
        return 'union[%s]' % ', '.join(str(item) for item in self.items)

    # We compare based on the set because order in a union doesn't matter
    def __eq__(self, other: object) -> bool:
        return isinstance(other, RUnion) and self.items_set == other.items_set

    def __hash__(self) -> int:
        return hash(('union', self.items_set))

    def serialize(self) -> JsonDict:
        types = [x.serialize() for x in self.items]
        return {'.class': 'RUnion', 'types': types}

    @classmethod
    def deserialize(cls, data: JsonDict, ctx: 'DeserMaps') -> 'RUnion':
        types = [deserialize_type(t, ctx) for t in data['types']]
        return RUnion(types)


def optional_value_type(rtype: RType) -> Optional[RType]:
    """If rtype is the union of none_rprimitive and another type X, return X.

    Otherwise return None.
    """
    if isinstance(rtype, RUnion) and len(rtype.items) == 2:
        if rtype.items[0] == none_rprimitive:
            return rtype.items[1]
        elif rtype.items[1] == none_rprimitive:
            return rtype.items[0]
    return None


def is_optional_type(rtype: RType) -> bool:
    """Is rtype an optional type with exactly two union items?"""
    return optional_value_type(rtype) is not None


PyObject = RStruct(
    name='PyObject',
    names=['ob_refcnt', 'ob_type'],
    types=[c_pyssize_t_rprimitive, pointer_rprimitive])

PyVarObject = RStruct(
    name='PyVarObject',
    names=['ob_base', 'ob_size'],
    types=[PyObject, c_pyssize_t_rprimitive])

setentry = RStruct(
    name='setentry',
    names=['key', 'hash'],
    types=[pointer_rprimitive, c_pyssize_t_rprimitive])

smalltable = RStruct(
    name='smalltable',
    names=[],
    types=[setentry] * 8)

PySetObject = RStruct(
    name='PySetObject',
    names=['ob_base', 'fill', 'used', 'mask', 'table', 'hash', 'finger',
           'smalltable', 'weakreflist'],
    types=[PyObject, c_pyssize_t_rprimitive, c_pyssize_t_rprimitive, c_pyssize_t_rprimitive,
           pointer_rprimitive, c_pyssize_t_rprimitive, c_pyssize_t_rprimitive, smalltable,
           pointer_rprimitive])
