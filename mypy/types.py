"""Classes for representing mypy types."""

from abc import abstractmethod
from typing import Any, TypeVar, Dict, List, Tuple, cast, Generic, Set, Sequence, Optional

import mypy.nodes
from mypy.nodes import INVARIANT, SymbolNode


T = TypeVar('T')

JsonDict = Dict[str, Any]


class Type(mypy.nodes.Context):
    """Abstract base class for all types."""

    line = 0

    def __init__(self, line: int = -1) -> None:
        self.line = line

    def get_line(self) -> int:
        return self.line

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        raise RuntimeError('Not implemented')

    def __repr__(self) -> str:
        return self.accept(TypeStrVisitor())

    def serialize(self) -> JsonDict:
        raise NotImplementedError('Cannot serialize {} instance'.format(self.__class__.__name__))

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Type':
        classname = data['.class']
        glo = globals()
        if classname in glo:
            cl = glo[classname]
            if 'deserialize' in cl.__dict__:
                return cl.deserialize(data)
        raise NotImplementedError('unexpected .class {}'.format(classname))


class TypeVarDef(mypy.nodes.Context):
    """Definition of a single type variable."""

    name = ''
    id = 0
    values = None  # type: Optional[List[Type]]
    upper_bound = None  # type: Type
    variance = INVARIANT  # type: int
    line = 0

    def __init__(self, name: str, id: int, values: Optional[List[Type]],
                 upper_bound: Type, variance: int = INVARIANT, line: int = -1) -> None:
        self.name = name
        self.id = id
        self.values = values
        self.upper_bound = upper_bound
        self.variance = variance
        self.line = line

    def get_line(self) -> int:
        return self.line

    def __repr__(self) -> str:
        if self.values:
            return '{} in {}'.format(self.name, tuple(self.values))
        elif not is_named_instance(self.upper_bound, 'builtins.object'):
            return '{} <: {}'.format(self.name, self.upper_bound)
        else:
            return self.name

    def serialize(self) -> JsonDict:
        return {'.class': 'TypeVarDef',
                'name': self.name,
                'id': self.id,
                'values': None if self.values is None else [v.serialize() for v in self.values],
                'upper_bound': self.upper_bound.serialize(),
                'variance': self.variance,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeVarDef':
        assert data['.class'] == 'TypeVarDef'
        return TypeVarDef(data['name'],
                          data['id'],
                          None if data['values'] is None
                          else [Type.deserialize(v) for v in data['values']],
                          Type.deserialize(data['upper_bound']),
                          data['variance'],
                          )


class UnboundType(Type):
    """Instance type that has not been bound during semantic analysis."""

    name = ''
    args = None  # type: List[Type]

    def __init__(self, name: str, args: List[Type] = None, line: int = -1) -> None:
        if not args:
            args = []
        self.name = name
        self.args = args
        super().__init__(line)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_unbound_type(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'UnboundType',
                'name': self.name,
                'args': [a.serialize() for a in self.args],
                }

    @classmethod
    def deserialize(self, data: JsonDict) -> 'UnboundType':
        assert data['.class'] == 'UnboundType'
        return UnboundType(data['name'],
                           [Type.deserialize(a) for a in data['args']])


class ErrorType(Type):
    """The error type is used as the result of failed type operations."""

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_error_type(self)


class TypeList(Type):
    """A list of types [...].

    This is only used for the arguments of a Callable type, i.e. for
    [arg, ...] in Callable[[arg, ...], ret]. This is not a real type
    but a syntactic AST construct.
    """

    items = None  # type: List[Type]

    def __init__(self, items: List[Type], line: int = -1) -> None:
        super().__init__(line)
        self.items = items

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_type_list(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'TypeList',
                'items': [t.serialize() for t in self.items],
                }

    @classmethod
    def deserialize(self, data: JsonDict) -> 'TypeList':
        assert data['.class'] == 'TypeList'
        return TypeList([Type.deserialize(t) for t in data['items']])


class AnyType(Type):
    """The type 'Any'."""

    def __init__(self, implicit=False, line: int = -1) -> None:
        super().__init__(line)
        self.implicit = implicit

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_any(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'AnyType'}

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'AnyType':
        assert data['.class'] == 'AnyType'
        return AnyType()


class Void(Type):
    """The return type 'None'.

    This can only be used as the return type in a callable type and as
    the result type of calling such callable.
    """

    source = ''   # May be None; function that generated this value

    def __init__(self, source: str = None, line: int = -1) -> None:
        self.source = source
        super().__init__(line)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_void(self)

    def with_source(self, source: str) -> 'Void':
        return Void(source, self.line)

    def serialize(self) -> JsonDict:
        return {'.class': 'Void'}

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Void':
        assert data['.class'] == 'Void'
        return Void()


class NoneTyp(Type):
    """The type of 'None'.

    This is only used internally during type inference.  Programs
    cannot declare a variable of this type, and the type checker
    refuses to infer this type for a variable. However, subexpressions
    often have this type. Note that this is not used as the result
    type when calling a function with a void type, even though
    semantically such a function returns a None value; the void type
    is used instead so that we can report an error if the caller tries
    to do anything with the return value.
    """

    def __init__(self, line: int = -1) -> None:
        super().__init__(line)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_none_type(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'NoneTyp'}

    @classmethod
    def deserialize(self, data: JsonDict) -> 'NoneTyp':
        assert data['.class'] == 'NoneTyp'
        return NoneTyp()


class ErasedType(Type):
    """Placeholder for an erased type.

    This is used during type inference. This has the special property that
    it is ignored during type inference.
    """

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_erased_type(self)


class DeletedType(Type):
    """Type of deleted variables.

    These can be used as lvalues but not rvalues.
    """

    source = ''   # May be None; name that generated this value

    def __init__(self, source: str = None, line: int = -1) -> None:
        self.source = source
        super().__init__(line)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_deleted_type(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'DeletedType',
                'source': self.source}

    @classmethod
    def deserialize(self, data: JsonDict) -> 'DeletedType':
        assert data['.class'] == 'DeletedType'
        return DeletedType(data['source'])


class Instance(Type):
    """An instance type of form C[T1, ..., Tn].

    The list of type variables may be empty.
    """

    type = None  # type: mypy.nodes.TypeInfo
    args = None  # type: List[Type]
    erased = False      # True if result of type variable substitution

    def __init__(self, typ: mypy.nodes.TypeInfo, args: List[Type],
                 line: int = -1, erased: bool = False) -> None:
        self.type = typ
        self.args = args
        self.erased = erased
        super().__init__(line)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_instance(self)

    type_ref = None  # type: str

    def serialize(self) -> JsonDict:
        data = {'.class': 'Instance',
                }  # type: JsonDict
        assert self.type is not None
        data['type_ref'] = self.type.alt_fullname or self.type.fullname()
        if self.args:
            data['args'] = [arg.serialize() for arg in self.args]
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Instance':
        assert data['.class'] == 'Instance'
        args = []  # type: List[Type]
        if 'args' in data:
            args_list = data['args']
            assert isinstance(args_list, list)
            args = [Type.deserialize(arg) for arg in args_list]
        inst = Instance(None, args)
        inst.type_ref = data['type_ref']  # Will be fixed up by fixup.py later.
        return inst


class TypeVarType(Type):
    """A type variable type.

    This refers to either a class type variable (id > 0) or a function
    type variable (id < 0).
    """

    name = ''  # Name of the type variable (for messages and debugging)
    id = 0     # 1, 2, ... for type-related, -1, ... for function-related
    values = None  # type: List[Type]  # Value restriction, empty list if no restriction
    upper_bound = None  # type: Type   # Upper bound for values
    # See comments in TypeVarDef for more about variance.
    variance = INVARIANT  # type: int

    def __init__(self, name: str, id: int, values: List[Type], upper_bound: Type,
                 variance: int = INVARIANT, line: int = -1) -> None:
        self.name = name
        self.id = id
        self.values = values
        self.upper_bound = upper_bound
        self.variance = variance
        super().__init__(line)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_type_var(self)

    def erase_to_union_or_bound(self) -> Type:
        if self.values:
            return UnionType.make_simplified_union(self.values)
        else:
            return self.upper_bound

    def serialize(self) -> JsonDict:
        return {'.class': 'TypeVarType',
                'name': self.name,
                'id': self.id,
                'values': [v.serialize() for v in self.values],
                'upper_bound': self.upper_bound.serialize(),
                'variance': self.variance,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeVarType':
        assert data['.class'] == 'TypeVarType'
        return TypeVarType(data['name'],
                           data['id'],
                           [Type.deserialize(v) for v in data['values']],
                           Type.deserialize(data['upper_bound']),
                           data['variance'])


class FunctionLike(Type):
    """Abstract base class for function types."""

    @abstractmethod
    def is_type_obj(self) -> bool: pass

    def is_concrete_type_obj(self) -> bool:
        return self.is_type_obj()

    @abstractmethod
    def type_object(self) -> mypy.nodes.TypeInfo: pass

    @abstractmethod
    def items(self) -> List['CallableType']: pass

    @abstractmethod
    def with_name(self, name: str) -> 'FunctionLike': pass

    # Corresponding instance type (e.g. builtins.type)
    fallback = None  # type: Instance

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'FunctionLike':
        return cast(FunctionLike, super().deserialize(data))


_dummy = object()  # type: Any


class CallableType(FunctionLike):
    """Type of a non-overloaded callable object (function)."""

    arg_types = None  # type: List[Type]  # Types of function arguments
    arg_kinds = None  # type: List[int]   # mypy.nodes.ARG_ constants
    arg_names = None  # type: List[str]   # None if not a keyword argument
    min_args = 0                    # Minimum number of arguments; derived from arg_kinds
    is_var_arg = False              # Is it a varargs function?  derived from arg_kinds
    ret_type = None  # type: Type   # Return value type
    name = ''                       # Name (may be None; for error messages)
    definition = None  # type: SymbolNode # For error messages.  May be None.
    # Type variables for a generic function
    variables = None  # type: List[TypeVarDef]

    # Is this Callable[..., t] (with literal '...')?
    is_ellipsis_args = False
    # Is this callable constructed for the benefit of a classmethod's 'cls' argument?
    is_classmethod_class = False
    # Was this type implicitly generated instead of explicitly specified by the user?
    implicit = False
    # Defined for signatures that require special handling (currently only value is 'dict'
    # for a signature similar to 'dict')
    special_sig = None  # type: Optional[str]

    def __init__(self,
                 arg_types: List[Type],
                 arg_kinds: List[int],
                 arg_names: List[str],
                 ret_type: Type,
                 fallback: Instance,
                 name: str = None,
                 definition: SymbolNode = None,
                 variables: List[TypeVarDef] = None,
                 line: int = -1,
                 is_ellipsis_args: bool = False,
                 implicit=False,
                 is_classmethod_class=False,
                 special_sig=None,
                 ) -> None:
        if variables is None:
            variables = []
        self.arg_types = arg_types
        self.arg_kinds = arg_kinds
        self.arg_names = arg_names
        self.min_args = arg_kinds.count(mypy.nodes.ARG_POS)
        self.is_var_arg = mypy.nodes.ARG_STAR in arg_kinds
        self.ret_type = ret_type
        self.fallback = fallback
        assert not name or '<bound method' not in name
        self.name = name
        self.definition = definition
        self.variables = variables
        self.is_ellipsis_args = is_ellipsis_args
        self.implicit = implicit
        self.special_sig = special_sig
        super().__init__(line)

    def copy_modified(self,
                      arg_types: List[Type] = _dummy,
                      arg_kinds: List[int] = _dummy,
                      arg_names: List[str] = _dummy,
                      ret_type: Type = _dummy,
                      fallback: Instance = _dummy,
                      name: str = _dummy,
                      definition: SymbolNode = _dummy,
                      variables: List[TypeVarDef] = _dummy,
                      line: int = _dummy,
                      is_ellipsis_args: bool = _dummy,
                      special_sig: Optional[str] = _dummy) -> 'CallableType':
        return CallableType(
            arg_types=arg_types if arg_types is not _dummy else self.arg_types,
            arg_kinds=arg_kinds if arg_kinds is not _dummy else self.arg_kinds,
            arg_names=arg_names if arg_names is not _dummy else self.arg_names,
            ret_type=ret_type if ret_type is not _dummy else self.ret_type,
            fallback=fallback if fallback is not _dummy else self.fallback,
            name=name if name is not _dummy else self.name,
            definition=definition if definition is not _dummy else self.definition,
            variables=variables if variables is not _dummy else self.variables,
            line=line if line is not _dummy else self.line,
            is_ellipsis_args=(
                is_ellipsis_args if is_ellipsis_args is not _dummy else self.is_ellipsis_args),
            implicit=self.implicit,
            is_classmethod_class=self.is_classmethod_class,
            special_sig=special_sig if special_sig is not _dummy else self.special_sig,
        )

    def is_type_obj(self) -> bool:
        return self.fallback.type is not None and self.fallback.type.fullname() == 'builtins.type'

    def is_concrete_type_obj(self) -> bool:
        return self.is_type_obj() and self.is_classmethod_class

    def type_object(self) -> mypy.nodes.TypeInfo:
        assert self.is_type_obj()
        ret = self.ret_type
        if isinstance(ret, TupleType):
            ret = ret.fallback
        return cast(Instance, ret).type

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_callable_type(self)

    def with_name(self, name: str) -> 'CallableType':
        """Return a copy of this type with the specified name."""
        ret = self.ret_type
        if isinstance(ret, Void):
            ret = ret.with_source(name)
        return self.copy_modified(ret_type=ret, name=name)

    def max_fixed_args(self) -> int:
        n = len(self.arg_types)
        if self.is_var_arg:
            n -= 1
        return n

    def items(self) -> List['CallableType']:
        return [self]

    def is_generic(self) -> bool:
        return bool(self.variables)

    def type_var_ids(self) -> List[int]:
        a = []  # type: List[int]
        for tv in self.variables:
            a.append(tv.id)
        return a

    def serialize(self) -> JsonDict:
        # TODO: As an optimization, leave out everything related to
        # generic functions for non-generic functions.
        return {'.class': 'CallableType',
                'arg_types': [(None if t is None else t.serialize())
                              for t in self.arg_types],
                'arg_kinds': self.arg_kinds,
                'arg_names': self.arg_names,
                'ret_type': self.ret_type.serialize(),
                'fallback': self.fallback.serialize(),
                'name': self.name,
                # We don't serialize the definition (only used for error messages).
                'variables': [v.serialize() for v in self.variables],
                'is_ellipsis_args': self.is_ellipsis_args,
                'implicit': self.implicit,
                'is_classmethod_class': self.is_classmethod_class,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'CallableType':
        assert data['.class'] == 'CallableType'
        # TODO: Set definition to the containing SymbolNode?
        return CallableType([(None if t is None else Type.deserialize(t))
                             for t in data['arg_types']],
                            data['arg_kinds'],
                            data['arg_names'],
                            Type.deserialize(data['ret_type']),
                            Instance.deserialize(data['fallback']),
                            name=data['name'],
                            variables=[TypeVarDef.deserialize(v) for v in data['variables']],
                            is_ellipsis_args=data['is_ellipsis_args'],
                            implicit=data['implicit'],
                            is_classmethod_class=data['is_classmethod_class'],
                            )


class Overloaded(FunctionLike):
    """Overloaded function type T1, ... Tn, where each Ti is CallableType.

    The variant to call is chosen based on static argument
    types. Overloaded function types can only be defined in stub
    files, and thus there is no explicit runtime dispatch
    implementation.
    """

    _items = None  # type: List[CallableType]  # Must not be empty

    def __init__(self, items: List[CallableType]) -> None:
        self._items = items
        self.fallback = items[0].fallback
        super().__init__(items[0].line)

    def items(self) -> List[CallableType]:
        return self._items

    def name(self) -> str:
        return self._items[0].name

    def is_type_obj(self) -> bool:
        # All the items must have the same type object status, so it's
        # sufficient to query only (any) one of them.
        return self._items[0].is_type_obj()

    def type_object(self) -> mypy.nodes.TypeInfo:
        # All the items must have the same type object, so it's sufficient to
        # query only (any) one of them.
        return self._items[0].type_object()

    def with_name(self, name: str) -> 'Overloaded':
        ni = []  # type: List[CallableType]
        for it in self._items:
            ni.append(it.with_name(name))
        return Overloaded(ni)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_overloaded(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'Overloaded',
                'items': [t.serialize() for t in self.items()],
                }

    @classmethod
    def deserialize(self, data: JsonDict) -> 'Overloaded':
        assert data['.class'] == 'Overloaded'
        return Overloaded([CallableType.deserialize(t) for t in data['items']])


class TupleType(Type):
    """The tuple type Tuple[T1, ..., Tn] (at least one type argument).

    Instance variables:
        items: tuple item types
        fallback: the underlying instance type that is used for non-tuple methods
            (this is currently always builtins.tuple, but it could be different for named
            tuples, for example)
        implicit: if True, derived from a tuple expression (t,....) instead of Tuple[t, ...]
    """

    items = None  # type: List[Type]
    fallback = None  # type: Instance
    implicit = False

    def __init__(self, items: List[Type], fallback: Instance, line: int = -1,
                 implicit: bool = False) -> None:
        self.items = items
        self.fallback = fallback
        self.implicit = implicit
        super().__init__(line)

    def length(self) -> int:
        return len(self.items)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_tuple_type(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'TupleType',
                'items': [t.serialize() for t in self.items],
                'fallback': self.fallback.serialize(),
                'implicit': self.implicit,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TupleType':
        assert data['.class'] == 'TupleType'
        return TupleType([Type.deserialize(t) for t in data['items']],
                         Instance.deserialize(data['fallback']),
                         implicit=data['implicit'])


class StarType(Type):
    """The star type *type_parameter.

    This is not a real type but a syntactic AST construct.
    """

    type = None  # type: Type

    def __init__(self, type: Type, line: int = -1) -> None:
        self.type = type
        super().__init__(line)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_star_type(self)


class UnionType(Type):
    """The union type Union[T1, ..., Tn] (at least one type argument)."""

    items = None  # type: List[Type]

    def __init__(self, items: List[Type], line: int = -1) -> None:
        self.items = items
        super().__init__(line)

    @staticmethod
    def make_union(items: List[Type], line: int = -1) -> Type:
        if len(items) > 1:
            return UnionType(items, line)
        elif len(items) == 1:
            return items[0]
        else:
            return Void()

    @staticmethod
    def make_simplified_union(items: List[Type], line: int = -1) -> Type:
        while any(isinstance(typ, UnionType) for typ in items):
            all_items = []  # type: List[Type]
            for typ in items:
                if isinstance(typ, UnionType):
                    all_items.extend(typ.items)
                else:
                    all_items.append(typ)
            items = all_items

        if any(isinstance(typ, AnyType) for typ in items):
            return AnyType()

        from mypy.subtypes import is_subtype
        removed = set()  # type: Set[int]
        for i in range(len(items)):
            if any(is_subtype(items[i], items[j]) for j in range(len(items))
                   if j not in removed and j != i):
                removed.add(i)

        simplified_set = [items[i] for i in range(len(items)) if i not in removed]
        return UnionType.make_union(simplified_set)

    def length(self) -> int:
        return len(self.items)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_union_type(self)

    def has_readable_member(self, name: str) -> bool:
        """For a tree of unions of instances, check whether all instances have a given member.

        TODO: Deal with attributes of TupleType etc.
        TODO: This should probably be refactored to go elsewhere.
        """
        return all((isinstance(x, UnionType) and x.has_readable_member(name)) or
                   (isinstance(x, Instance) and x.type.has_readable_member(name))
                   for x in self.items)

    def serialize(self) -> JsonDict:
        return {'.class': 'UnionType',
                'items': [t.serialize() for t in self.items],
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'UnionType':
        assert data['.class'] == 'UnionType'
        return UnionType([Type.deserialize(t) for t in data['items']])


class PartialType(Type):
    """Type such as List[?] where type arguments are unknown, or partial None type.

    These are used for inferring types in multiphase initialization such as this:

      x = []       # x gets a partial type List[?], as item type is unknown
      x.append(1)  # partial type gets replaced with normal type List[int]

    Or with None:

      x = None  # x gets a partial type None
      if c:
          x = 1  # Infer actual type int for x
    """

    # None for the 'None' partial type; otherwise a generic class
    type = None  # type: Optional[mypy.nodes.TypeInfo]
    var = None  # type: mypy.nodes.Var

    def __init__(self, type: Optional['mypy.nodes.TypeInfo'], var: 'mypy.nodes.Var') -> None:
        self.type = type
        self.var = var

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_partial_type(self)


class EllipsisType(Type):
    """The type ... (ellipsis).

    This is not a real type but a syntactic AST construct, used in Callable[..., T], for example.

    A semantically analyzed type will never have ellipsis types.
    """

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_ellipsis_type(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'EllipsisType'}

    @classmethod
    def deserialize(self, data: JsonDict) -> 'EllipsisType':
        assert data['.class'] == 'EllipsisType'
        return EllipsisType()


#
# Visitor-related classes
#


class TypeVisitor(Generic[T]):
    """Visitor class for types (Type subclasses).

    The parameter T is the return type of the visit methods.
    """

    def _notimplemented_helper(self) -> NotImplementedError:
        return NotImplementedError("Method visit_type_list not implemented in "
                                   + "'{}'\n".format(type(self).__name__)
                                   + "This is a known bug, track development in "
                                   + "'https://github.com/JukkaL/mypy/issues/730'")

    @abstractmethod
    def visit_unbound_type(self, t: UnboundType) -> T:
        pass

    def visit_type_list(self, t: TypeList) -> T:
        raise self._notimplemented_helper()

    def visit_error_type(self, t: ErrorType) -> T:
        raise self._notimplemented_helper()

    @abstractmethod
    def visit_any(self, t: AnyType) -> T:
        pass

    @abstractmethod
    def visit_void(self, t: Void) -> T:
        pass

    @abstractmethod
    def visit_none_type(self, t: NoneTyp) -> T:
        pass

    def visit_erased_type(self, t: ErasedType) -> T:
        raise self._notimplemented_helper()

    @abstractmethod
    def visit_deleted_type(self, t: DeletedType) -> T:
        pass

    @abstractmethod
    def visit_type_var(self, t: TypeVarType) -> T:
        pass

    @abstractmethod
    def visit_instance(self, t: Instance) -> T:
        pass

    @abstractmethod
    def visit_callable_type(self, t: CallableType) -> T:
        pass

    def visit_overloaded(self, t: Overloaded) -> T:
        raise self._notimplemented_helper()

    @abstractmethod
    def visit_tuple_type(self, t: TupleType) -> T:
        pass

    def visit_star_type(self, t: StarType) -> T:
        raise self._notimplemented_helper()

    @abstractmethod
    def visit_union_type(self, t: UnionType) -> T:
        pass

    @abstractmethod
    def visit_partial_type(self, t: PartialType) -> T:
        pass

    def visit_ellipsis_type(self, t: EllipsisType) -> T:
        raise self._notimplemented_helper()


class TypeTranslator(TypeVisitor[Type]):
    """Identity type transformation.

    Subclass this and override some methods to implement a non-trivial
    transformation.
    """

    def visit_unbound_type(self, t: UnboundType) -> Type:
        return t

    def visit_type_list(self, t: TypeList) -> Type:
        return t

    def visit_error_type(self, t: ErrorType) -> Type:
        return t

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_void(self, t: Void) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_erased_type(self, t: ErasedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_instance(self, t: Instance) -> Type:
        return Instance(t.type, self.translate_types(t.args), t.line)

    def visit_type_var(self, t: TypeVarType) -> Type:
        return t

    def visit_partial_type(self, t: PartialType) -> Type:
        return t

    def visit_callable_type(self, t: CallableType) -> Type:
        return t.copy_modified(arg_types=self.translate_types(t.arg_types),
                               ret_type=t.ret_type.accept(self),
                               variables=self.translate_variables(t.variables))

    def visit_tuple_type(self, t: TupleType) -> Type:
        return TupleType(self.translate_types(t.items),
                         cast(Any, t.fallback.accept(self)),
                         t.line)

    def visit_star_type(self, t: StarType) -> Type:
        return StarType(t.type.accept(self), t.line)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.translate_types(t.items), t.line)

    def visit_ellipsis_type(self, t: EllipsisType) -> Type:
        return t

    def translate_types(self, types: List[Type]) -> List[Type]:
        return [t.accept(self) for t in types]

    def translate_variables(self,
                            variables: List[TypeVarDef]) -> List[TypeVarDef]:
        return variables

    def visit_overloaded(self, t: Overloaded) -> Type:
        items = []  # type: List[CallableType]
        for item in t.items():
            new = item.accept(self)
            if isinstance(new, CallableType):
                items.append(new)
            else:
                raise RuntimeError('CallableType expectected, but got {}'.format(type(new)))
        return Overloaded(items=items)


class TypeStrVisitor(TypeVisitor[str]):
    """Visitor for pretty-printing types into strings.

    This is mostly for debugging/testing.

    Do not preserve original formatting.

    Notes:
     - Represent unbound types as Foo? or Foo?[...].
     - Represent the NoneTyp type as None.
    """

    def visit_unbound_type(self, t):
        s = t.name + '?'
        if t.args != []:
            s += '[{}]'.format(self.list_str(t.args))
        return s

    def visit_type_list(self, t):
        return '<TypeList {}>'.format(self.list_str(t.items))

    def visit_error_type(self, t):
        return '<ERROR>'

    def visit_any(self, t):
        return 'Any'

    def visit_void(self, t):
        return 'void'

    def visit_none_type(self, t):
        # Include quotes to make this distinct from the None value.
        return "'None'"

    def visit_erased_type(self, t):
        return "<Erased>"

    def visit_deleted_type(self, t):
        if t.source is None:
            return "<Deleted>"
        else:
            return "<Deleted '{}'>".format(t.source)

    def visit_instance(self, t):
        s = t.type.fullname() if t.type is not None else '<?>'
        if t.erased:
            s += '*'
        if t.args != []:
            s += '[{}]'.format(self.list_str(t.args))
        return s

    def visit_type_var(self, t):
        if t.name is None:
            # Anonymous type variable type (only numeric id).
            return '`{}'.format(t.id)
        else:
            # Named type variable type.
            return '{}`{}'.format(t.name, t.id)

    def visit_callable_type(self, t):
        s = ''
        bare_asterisk = False
        for i in range(len(t.arg_types)):
            if s != '':
                s += ', '
            if t.arg_kinds[i] == mypy.nodes.ARG_NAMED and not bare_asterisk:
                s += '*, '
                bare_asterisk = True
            if t.arg_kinds[i] == mypy.nodes.ARG_STAR:
                s += '*'
            if t.arg_kinds[i] == mypy.nodes.ARG_STAR2:
                s += '**'
            if t.arg_names[i]:
                s += t.arg_names[i] + ': '
            s += str(t.arg_types[i])
            if t.arg_kinds[i] == mypy.nodes.ARG_OPT:
                s += ' ='

        s = '({})'.format(s)

        if not isinstance(t.ret_type, Void):
            s += ' -> {}'.format(t.ret_type)

        if t.variables:
            s = '{} {}'.format(t.variables, s)

        return 'def {}'.format(s)

    def visit_overloaded(self, t):
        a = []
        for i in t.items():
            a.append(i.accept(self))
        return 'Overload({})'.format(', '.join(a))

    def visit_tuple_type(self, t):
        s = self.list_str(t.items)
        if t.fallback and t.fallback.type:
            fallback_name = t.fallback.type.fullname()
            if fallback_name != 'builtins.tuple':
                return 'Tuple[{}, fallback={}]'.format(s, t.fallback.accept(self))
        return 'Tuple[{}]'.format(s)

    def visit_star_type(self, t):
        s = t.type.accept(self)
        return '*{}'.format(s)

    def visit_union_type(self, t):
        s = self.list_str(t.items)
        return 'Union[{}]'.format(s)

    def visit_partial_type(self, t: PartialType) -> str:
        if t.type is None:
            return '<partial None>'
        else:
            return '<partial {}[{}]>'.format(t.type.name(),
                                             ', '.join(['?'] * len(t.type.type_vars)))

    def visit_ellipsis_type(self, t):
        return '...'

    def list_str(self, a):
        """Convert items of an array to strings (pretty-print types)
        and join the results with commas.
        """
        res = []
        for t in a:
            if isinstance(t, Type):
                res.append(t.accept(self))
            else:
                res.append(str(t))
        return ', '.join(res)


# These constants define the method used by TypeQuery to combine multiple
# query results, e.g. for tuple types. The strategy is not used for empty
# result lists; in that case the default value takes precedence.
ANY_TYPE_STRATEGY = 0   # Return True if any of the results are True.
ALL_TYPES_STRATEGY = 1  # Return True if all of the results are True.


class TypeQuery(TypeVisitor[bool]):
    """Visitor for performing simple boolean queries of types.

    This class allows defining the default value for leafs to simplify the
    implementation of many queries.
    """

    default = False  # Default result
    strategy = 0     # Strategy for combining multiple values (ANY_TYPE_STRATEGY or ALL_TYPES_...).

    def __init__(self, default: bool, strategy: int) -> None:
        """Construct a query visitor.

        Use the given default result and strategy for combining
        multiple results. The strategy must be either
        ANY_TYPE_STRATEGY or ALL_TYPES_STRATEGY.
        """
        self.default = default
        self.strategy = strategy

    def visit_unbound_type(self, t: UnboundType) -> bool:
        return self.default

    def visit_type_list(self, t: TypeList) -> bool:
        return self.default

    def visit_error_type(self, t: ErrorType) -> bool:
        return self.default

    def visit_any(self, t: AnyType) -> bool:
        return self.default

    def visit_void(self, t: Void) -> bool:
        return self.default

    def visit_none_type(self, t: NoneTyp) -> bool:
        return self.default

    def visit_erased_type(self, t: ErasedType) -> bool:
        return self.default

    def visit_deleted_type(self, t: DeletedType) -> bool:
        return self.default

    def visit_type_var(self, t: TypeVarType) -> bool:
        return self.default

    def visit_partial_type(self, t: PartialType) -> bool:
        return self.default

    def visit_instance(self, t: Instance) -> bool:
        return self.query_types(t.args)

    def visit_callable_type(self, t: CallableType) -> bool:
        # FIX generics
        return self.query_types(t.arg_types + [t.ret_type])

    def visit_tuple_type(self, t: TupleType) -> bool:
        return self.query_types(t.items)

    def visit_star_type(self, t: StarType) -> bool:
        return t.type.accept(self)

    def visit_union_type(self, t: UnionType) -> bool:
        return self.query_types(t.items)

    def visit_overloaded(self, t: Overloaded) -> bool:
        return self.query_types(t.items())

    def query_types(self, types: Sequence[Type]) -> bool:
        """Perform a query for a list of types.

        Use the strategy constant to combine the results.
        """
        if not types:
            # Use default result for empty list.
            return self.default
        if self.strategy == ANY_TYPE_STRATEGY:
            # Return True if at least one component is true.
            res = False
            for t in types:
                res = res or t.accept(self)
                if res:
                    break
            return res
        else:
            # Return True if all components are true.
            res = True
            for t in types:
                res = res and t.accept(self)
                if not res:
                    break
            return res


def strip_type(typ: Type) -> Type:
    """Make a copy of type without 'debugging info' (function name)."""

    if isinstance(typ, CallableType):
        return typ.copy_modified(name=None)
    elif isinstance(typ, Overloaded):
        return Overloaded([cast(CallableType, strip_type(item))
                           for item in typ.items()])
    else:
        return typ


def replace_leading_arg_type(t: CallableType, self_type: Type) -> CallableType:
    """Return a copy of a callable type with a different self argument type.

    Assume that the callable is the signature of a method.
    """
    return t.copy_modified(arg_types=[self_type] + t.arg_types[1:])


def is_named_instance(t: Type, fullname: str) -> bool:
    return (isinstance(t, Instance) and
            t.type is not None and
            t.type.fullname() == fullname)
