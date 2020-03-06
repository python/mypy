"""Types used in the intermediate representation.

These are runtime types (RTypes) as opposed to mypy Type objects.  The
latter are only used during type checking and ignored at runtime.  The
generated IR ensures some runtime type safety properties based on
RTypes.

RTypes are simpler and less expressive than mypy (or PEP 484)
types. For example, all mypy types of form 'list[T]' (for arbitrary T)
are erased to the single RType 'builtins.list' (list_rprimitive).

mypyc.irbuild.mapper.Mapper.type_to_rtype converts mypy Types to mypyc
RTypes.
"""

from abc import abstractmethod
from typing import Optional, Union, List, Dict, Generic, TypeVar

from typing_extensions import Final, ClassVar, TYPE_CHECKING

from mypyc.common import JsonDict, short_name
from mypyc.namegen import NameGenerator

if TYPE_CHECKING:
    from mypyc.ir.ops import DeserMaps
    from mypyc.ir.class_ir import ClassIR

T = TypeVar('T')


class RType:
    """Abstract base class for runtime types (erased, only concrete; no generics)."""

    name = None  # type: str
    is_unboxed = False
    c_undefined = None  # type: str
    is_refcounted = True  # If unboxed: does the unboxed version use reference counting?
    _ctype = None  # type: str  # C type; use Emitter.ctype() to access

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
    def visit_rvoid(self, typ: 'RVoid') -> T:
        raise NotImplementedError


class RVoid(RType):
    """void"""

    is_unboxed = False
    name = 'void'
    ctype = 'void'

    def accept(self, visitor: 'RTypeVisitor[T]') -> T:
        return visitor.visit_rvoid(self)

    def serialize(self) -> str:
        return 'void'


void_rtype = RVoid()  # type: Final


class RPrimitive(RType):
    """Primitive type such as 'object' or 'int'.

    These often have custom ops associated with them.
    """

    # Map from primitive names to primitive types and is used by deserialization
    primitive_map = {}  # type: ClassVar[Dict[str, RPrimitive]]

    def __init__(self,
                 name: str,
                 is_unboxed: bool,
                 is_refcounted: bool,
                 ctype: str = 'PyObject *') -> None:
        RPrimitive.primitive_map[name] = self

        self.name = name
        self.is_unboxed = is_unboxed
        self._ctype = ctype
        self.is_refcounted = is_refcounted
        if ctype == 'CPyTagged':
            self.c_undefined = 'CPY_INT_TAG'
        elif ctype == 'PyObject *':
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


# Used to represent arbitrary objects and dynamically typed values
object_rprimitive = RPrimitive('builtins.object', is_unboxed=False,
                               is_refcounted=True)  # type: Final

int_rprimitive = RPrimitive('builtins.int', is_unboxed=True, is_refcounted=True,
                            ctype='CPyTagged')  # type: Final

short_int_rprimitive = RPrimitive('short_int', is_unboxed=True, is_refcounted=False,
                                  ctype='CPyTagged')  # type: Final

float_rprimitive = RPrimitive('builtins.float', is_unboxed=False,
                              is_refcounted=True)  # type: Final

bool_rprimitive = RPrimitive('builtins.bool', is_unboxed=True, is_refcounted=False,
                             ctype='char')  # type: Final

none_rprimitive = RPrimitive('builtins.None', is_unboxed=True, is_refcounted=False,
                             ctype='char')  # type: Final

list_rprimitive = RPrimitive('builtins.list', is_unboxed=False, is_refcounted=True)  # type: Final

dict_rprimitive = RPrimitive('builtins.dict', is_unboxed=False, is_refcounted=True)  # type: Final

set_rprimitive = RPrimitive('builtins.set', is_unboxed=False, is_refcounted=True)  # type: Final

# At the C layer, str is refered to as unicode (PyUnicode)
str_rprimitive = RPrimitive('builtins.str', is_unboxed=False, is_refcounted=True)  # type: Final

# Tuple of an arbitrary length (corresponds to Tuple[t, ...], with explicit '...')
tuple_rprimitive = RPrimitive('builtins.tuple', is_unboxed=False,
                              is_refcounted=True)  # type: Final


def is_int_rprimitive(rtype: RType) -> bool:
    return rtype is int_rprimitive


def is_short_int_rprimitive(rtype: RType) -> bool:
    return rtype is short_int_rprimitive


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

    def visit_rvoid(self, t: 'RVoid') -> str:
        assert False, "rvoid in tuple?"


class RTuple(RType):
    """Fixed-length unboxed tuple (represented as a C struct)."""

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


exc_rtuple = RTuple([object_rprimitive, object_rprimitive, object_rprimitive])


class RInstance(RType):
    """Instance of user-defined class (compiled to C extension class)."""

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
    if isinstance(rtype, RUnion) and len(rtype.items) == 2:
        if rtype.items[0] == none_rprimitive:
            return rtype.items[1]
        elif rtype.items[1] == none_rprimitive:
            return rtype.items[0]
    return None


def is_optional_type(rtype: RType) -> bool:
    return optional_value_type(rtype) is not None
