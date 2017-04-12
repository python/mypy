from typing import List, Optional, Set
from mypy.nodes import (
    FuncBase, OverloadedFuncDef, Decorator, ClassDef, Var, deserialize_map,
    SymbolTable, SymbolNode, SymbolTableNode, JsonDict, get_flags, set_flags,
)
import mypy.types


class TypeInfo(SymbolNode):
    """The type structure of a single class.

    Each TypeInfo corresponds one-to-one to a ClassDef, which
    represents the AST of the class.

    In type-theory terms, this is a "type constructor", and if the
    class is generic then it will be a type constructor of higher kind.
    Where the class is used in an actual type, it's in the form of an
    Instance, which amounts to a type application of the tycon to
    the appropriate number of arguments.
    """

    _fullname = None  # type: str          # Fully qualified name
    # Fully qualified name for the module this type was defined in. This
    # information is also in the fullname, but is harder to extract in the
    # case of nested class definitions.
    module_name = None  # type: str
    defn = None  # type: ClassDef          # Corresponding ClassDef
    # Method Resolution Order: the order of looking up attributes. The first
    # value always to refers to this class.
    mro = None  # type: List[TypeInfo]

    declared_metaclass = None  # type: Optional[mypy.types.Instance]
    metaclass_type = None  # type: mypy.types.Instance

    subtypes = None  # type: Set[TypeInfo] # Direct subclasses encountered so far
    names = None  # type: SymbolTable      # Names defined directly in this type
    is_abstract = False                    # Does the class have any abstract attributes?
    abstract_attributes = None  # type: List[str]
    # Classes inheriting from Enum shadow their true members with a __getattr__, so we
    # have to treat them as a special case.
    is_enum = False
    # If true, any unknown attributes should have type 'Any' instead
    # of generating a type error.  This would be true if there is a
    # base class with type 'Any', but other use cases may be
    # possible. This is similar to having __getattr__ that returns Any
    # (and __setattr__), but without the __getattr__ method.
    fallback_to_any = False

    # Information related to type annotations.

    # Generic type variable names
    type_vars = None  # type: List[str]

    # Direct base classes.
    bases = None  # type: List[mypy.types.Instance]

    # Another type which this type will be treated as a subtype of,
    # even though it's not a subclass in Python.  The non-standard
    # `@_promote` decorator introduces this, and there are also
    # several builtin examples, in particular `int` -> `float`.
    _promote = None  # type: mypy.types.Type

    # Representation of a Tuple[...] base class, if the class has any
    # (e.g., for named tuples). If this is not None, the actual Type
    # object used for this class is not an Instance but a TupleType;
    # the corresponding Instance is set as the fallback type of the
    # tuple type.
    tuple_type = None  # type: Optional[mypy.types.TupleType]

    # Is this a named tuple type?
    is_named_tuple = False

    # If this class is defined by the TypedDict type constructor,
    # then this is not None.
    typeddict_type = None  # type: Optional[mypy.types.TypedDictType]

    # Is this a newtype type?
    is_newtype = False

    # Alternative to fullname() for 'anonymous' classes.
    alt_fullname = None  # type: Optional[str]

    FLAGS = [
        'is_abstract', 'is_enum', 'fallback_to_any', 'is_named_tuple',
        'is_newtype'
    ]

    def __init__(self, names: 'SymbolTable', defn: ClassDef, module_name: str) -> None:
        """Initialize a TypeInfo."""
        self.names = names
        self.defn = defn
        self.module_name = module_name
        self.subtypes = set()
        self.type_vars = []
        self.bases = []
        # Leave self.mro uninitialized until we compute it for real,
        # so we don't accidentally try to use it prematurely.
        self._fullname = defn.fullname
        self.is_abstract = False
        self.abstract_attributes = []
        self.add_type_vars()

    def add_type_vars(self) -> None:
        if self.defn.type_vars:
            for vd in self.defn.type_vars:
                self.type_vars.append(vd.name)

    def name(self) -> str:
        """Short name."""
        return self.defn.name

    def fullname(self) -> str:
        return self._fullname

    def is_generic(self) -> bool:
        """Is the type generic (i.e. does it have type variables)?"""
        return len(self.type_vars) > 0

    def get(self, name: str) -> 'SymbolTableNode':
        for cls in self.mro:
            n = cls.names.get(name)
            if n:
                return n
        return None

    def __getitem__(self, name: str) -> 'SymbolTableNode':
        n = self.get(name)
        if n:
            return n
        else:
            raise KeyError(name)

    def __repr__(self) -> str:
        return '<TypeInfo %s>' % self.fullname()

    # IDEA: Refactor the has* methods to be more consistent and document
    #       them.

    def has_readable_member(self, name: str) -> bool:
        return self.get(name) is not None

    def has_method(self, name: str) -> bool:
        return self.get_method(name) is not None

    def get_method(self, name: str) -> FuncBase:
        if self.mro is None:  # Might be because of a previous error.
            return None
        for cls in self.mro:
            if name in cls.names:
                node = cls.names[name].node
                if isinstance(node, FuncBase):
                    return node
                else:
                    return None
        return None

    def calculate_abstract_status(self) -> None:
        """Calculate abstract status of a class.

        Set is_abstract of the type to True if the type has an unimplemented
        abstract attribute.  Also compute a list of abstract attributes.
        """
        concrete = set()  # type: Set[str]
        abstract = []  # type: List[str]
        for base in self.mro:
            for name, symnode in base.names.items():
                node = symnode.node
                func = node
                if isinstance(node, OverloadedFuncDef):
                    # Unwrap an overloaded function definition. We can just
                    # check arbitrarily the first overload item. If the
                    # different items have a different abstract status, there
                    # should be an error reported elsewhere.
                    func = node.items[0]
                if isinstance(func, Decorator):
                    fdef = func.func
                    if fdef.is_abstract and name not in concrete:
                        self.is_abstract = True
                        abstract.append(name)
                concrete.add(name)
        self.abstract_attributes = sorted(abstract)

    def calculate_mro(self) -> None:
        """Calculate and set mro (method resolution order).

        Raise MroError if cannot determine mro.
        """
        mro = linearize_hierarchy(self)
        assert mro, "Could not produce a MRO at all for %s" % (self,)
        self.mro = mro
        self.is_enum = self._calculate_is_enum()

    def calculate_metaclass_type(self) -> 'Optional[mypy.types.Instance]':
        declared = self.declared_metaclass
        if declared is not None and not declared.type.has_base('builtins.type'):
            return declared
        if self._fullname == 'builtins.type':
            return mypy.types.Instance(self, [])
        candidates = [s.declared_metaclass
                      for s in self.mro
                      if s.declared_metaclass is not None
                      and s.declared_metaclass.type is not None]
        for c in candidates:
            if c.type.mro is None:
                continue
            if all(other.type in c.type.mro for other in candidates):
                return c
        return None

    def is_metaclass(self) -> bool:
        return (self.has_base('builtins.type') or self.fullname() == 'abc.ABCMeta' or
                self.fallback_to_any)

    def _calculate_is_enum(self) -> bool:
        """
        If this is "enum.Enum" itself, then yes, it's an enum.
        If the flag .is_enum has been set on anything in the MRO, it's an enum.
        """
        if self.fullname() == "enum.Enum":
            return True
        if self.mro:
            return any(type_info.is_enum for type_info in self.mro)
        return False

    def has_base(self, fullname: str) -> bool:
        """Return True if type has a base type with the specified name.

        This can be either via extension or via implementation.
        """
        if self.mro:
            for cls in self.mro:
                if cls.fullname() == fullname:
                    return True
        return False

    def direct_base_classes(self) -> 'List[TypeInfo]':
        """Return a direct base classes.

        Omit base classes of other base classes.
        """
        return [base.type for base in self.bases]

    def is_base_class(self, s: 'TypeInfo') -> bool:
        """Determine if self is a base class of s (but do not use mro)."""
        # Search the base class graph for t, starting from s.
        worklist = [s]
        visited = {s}
        while worklist:
            nxt = worklist.pop()
            if nxt == self:
                return True
            for base in nxt.bases:
                if base.type not in visited:
                    worklist.append(base.type)
                    visited.add(base.type)
        return False

    def __str__(self) -> str:
        """Return a string representation of the type.

        This includes the most important information about the type.
        """
        return self.dump()

    def dump(self,
             str_conv: 'mypy.strconv.StrConv' = None,
             type_str_conv: 'mypy.types.TypeStrVisitor' = None) -> str:
        """Return a string dump of the contents of the TypeInfo."""
        if not str_conv:
            str_conv = mypy.strconv.StrConv()
        base = None  # type: str

        def type_str(typ: 'mypy.types.Type') -> str:
            if type_str_conv:
                return typ.accept(type_str_conv)
            return str(typ)

        head = 'TypeInfo' + str_conv.format_id(self)
        if self.bases:
            base = 'Bases({})'.format(', '.join(type_str(base)
                                                for base in self.bases))
        mro = 'Mro({})'.format(', '.join(item.fullname() + str_conv.format_id(item)
                                         for item in self.mro))
        names = []
        for name in sorted(self.names):
            description = name + str_conv.format_id(self.names[name].node)
            node = self.names[name].node
            if isinstance(node, Var) and node.type:
                description += ' ({})'.format(type_str(node.type))
            names.append(description)
        return mypy.strconv.dump_tagged(
            ['Name({})'.format(self.fullname()),
             base,
             mro,
             ('Names', names)],
            head,
            str_conv=str_conv)

    def serialize(self) -> JsonDict:
        # NOTE: This is where all ClassDefs originate, so there shouldn't be duplicates.
        data = {'.class': 'TypeInfo',
                'module_name': self.module_name,
                'fullname': self.fullname(),
                'alt_fullname': self.alt_fullname,
                'names': self.names.serialize(self.alt_fullname or self.fullname()),
                'defn': self.defn.serialize(),
                'abstract_attributes': self.abstract_attributes,
                'type_vars': self.type_vars,
                'bases': [b.serialize() for b in self.bases],
                '_promote': None if self._promote is None else self._promote.serialize(),
                'declared_metaclass': (None if self.declared_metaclass is None
                                       else self.declared_metaclass.serialize()),
                'tuple_type': None if self.tuple_type is None else self.tuple_type.serialize(),
                'typeddict_type':
                    None if self.typeddict_type is None else self.typeddict_type.serialize(),
                'flags': get_flags(self, TypeInfo.FLAGS),
                }
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeInfo':
        names = SymbolTable.deserialize(data['names'])
        defn = ClassDef.deserialize(data['defn'])
        module_name = data['module_name']
        ti = TypeInfo(names, defn, module_name)
        ti._fullname = data['fullname']
        ti.alt_fullname = data['alt_fullname']
        # TODO: Is there a reason to reconstruct ti.subtypes?
        ti.abstract_attributes = data['abstract_attributes']
        ti.type_vars = data['type_vars']
        ti.bases = [mypy.types.Instance.deserialize(b) for b in data['bases']]
        ti._promote = (None if data['_promote'] is None
                       else mypy.types.deserialize_type(data['_promote']))
        ti.declared_metaclass = (None if data['declared_metaclass'] is None
                                 else mypy.types.Instance.deserialize(data['declared_metaclass']))
        # NOTE: ti.metaclass_type and ti.mro will be set in the fixup phase.
        ti.tuple_type = (None if data['tuple_type'] is None
                         else mypy.types.TupleType.deserialize(data['tuple_type']))
        ti.typeddict_type = (None if data['typeddict_type'] is None
                            else mypy.types.TypedDictType.deserialize(data['typeddict_type']))
        set_flags(ti, data['flags'])
        return ti


def linearize_hierarchy(info: TypeInfo) -> List[TypeInfo]:
    # TODO describe
    if info.mro:
        return info.mro
    bases = info.direct_base_classes()
    lin_bases = []
    for base in bases:
        assert base is not None, "Cannot linearize bases for %s %s" % (info.fullname(), bases)
        lin_bases.append(linearize_hierarchy(base))
    lin_bases.append(bases)
    return [info] + merge(lin_bases)


def merge(seqs: List[List[TypeInfo]]) -> List[TypeInfo]:
    seqs = [s[:] for s in seqs]
    result = []  # type: List[TypeInfo]
    while True:
        seqs = [s for s in seqs if s]
        if not seqs:
            return result
        for seq in seqs:
            head = seq[0]
            if not [s for s in seqs if head in s[1:]]:
                break
        else:
            raise MroError()
        result.append(head)
        for s in seqs:
            if s[0] is head:
                del s[0]


class MroError(Exception):
    """Raised if a consistent mro cannot be determined for a class."""

deserialize_map['TypeInfo'] = TypeInfo.deserialize
