"""Classes for representing mypy types."""

import copy
from abc import abstractmethod
from collections import OrderedDict
from typing import (
    Any, TypeVar, Dict, List, Tuple, cast, Generic, Set, Optional, Union, Iterable, NamedTuple,
    Callable
)

import mypy.nodes
from mypy import experiments
from mypy.nodes import (
    INVARIANT, SymbolNode, ARG_POS, ARG_OPT, ARG_STAR, ARG_STAR2, ARG_NAMED, ARG_NAMED_OPT,
)
from mypy.sharedparse import argument_elide_name
from mypy.util import IdMapper

T = TypeVar('T')

JsonDict = Dict[str, Any]


def deserialize_type(data: Union[JsonDict, str]) -> 'Type':
    if isinstance(data, str):
        return Instance.deserialize(data)
    classname = data['.class']
    method = deserialize_map.get(classname)
    if method is not None:
        return method(data)
    raise NotImplementedError('unexpected .class {}'.format(classname))


class Type(mypy.nodes.Context):
    """Abstract base class for all types."""

    can_be_true = True
    can_be_false = True

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        raise RuntimeError('Not implemented')

    def __repr__(self) -> str:
        return self.accept(TypeStrVisitor())

    def serialize(self) -> Union[JsonDict, str]:
        raise NotImplementedError('Cannot serialize {} instance'.format(self.__class__.__name__))

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Type':
        raise NotImplementedError('Cannot deserialize {} instance'.format(cls.__name__))


class TypeVarId:
    # A type variable is uniquely identified by its raw id and meta level.

    # For plain variables (type parameters of generic classes and
    # functions) raw ids are allocated by semantic analysis, using
    # positive ids 1, 2, ... for generic class parameters and negative
    # ids -1, ... for generic function type arguments. This convention
    # is only used to keep type variable ids distinct when allocating
    # them; the type checker makes no distinction between class and
    # function type variables.

    # Metavariables are allocated unique ids starting from 1.
    raw_id = 0  # type: int

    # Level of the variable in type inference. Currently either 0 for
    # declared types, or 1 for type inference metavariables.
    meta_level = 0  # type: int

    # Class variable used for allocating fresh ids for metavariables.
    next_raw_id = 1  # type: int

    def __init__(self, raw_id: int, meta_level: int = 0) -> None:
        self.raw_id = raw_id
        self.meta_level = meta_level

    @staticmethod
    def new(meta_level: int) -> 'TypeVarId':
        raw_id = TypeVarId.next_raw_id
        TypeVarId.next_raw_id += 1
        return TypeVarId(raw_id, meta_level)

    def __repr__(self) -> str:
        return self.raw_id.__repr__()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TypeVarId):
            return (self.raw_id == other.raw_id and
                    self.meta_level == other.meta_level)
        else:
            return False

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __hash__(self) -> int:
        return hash((self.raw_id, self.meta_level))

    def is_meta_var(self) -> bool:
        return self.meta_level > 0


class TypeVarDef(mypy.nodes.Context):
    """Definition of a single type variable."""

    name = ''
    id = None  # type: TypeVarId
    values = None  # type: List[Type]  # Value restriction, empty list if no restriction
    upper_bound = None  # type: Type
    variance = INVARIANT  # type: int

    def __init__(self, name: str, id: Union[TypeVarId, int], values: List[Type],
                 upper_bound: Type, variance: int = INVARIANT, line: int = -1,
                 column: int = -1) -> None:
        super().__init__(line, column)
        assert values is not None, "No restrictions must be represented by empty list"
        self.name = name
        if isinstance(id, int):
            id = TypeVarId(id)
        self.id = id
        self.values = values
        self.upper_bound = upper_bound
        self.variance = variance

    @staticmethod
    def new_unification_variable(old: 'TypeVarDef') -> 'TypeVarDef':
        new_id = TypeVarId.new(meta_level=1)
        return TypeVarDef(old.name, new_id, old.values,
                          old.upper_bound, old.variance, old.line, old.column)

    def __repr__(self) -> str:
        if self.values:
            return '{} in {}'.format(self.name, tuple(self.values))
        elif not is_named_instance(self.upper_bound, 'builtins.object'):
            return '{} <: {}'.format(self.name, self.upper_bound)
        else:
            return self.name

    def serialize(self) -> JsonDict:
        assert not self.id.is_meta_var()
        return {'.class': 'TypeVarDef',
                'name': self.name,
                'id': self.id.raw_id,
                'values': [v.serialize() for v in self.values],
                'upper_bound': self.upper_bound.serialize(),
                'variance': self.variance,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeVarDef':
        assert data['.class'] == 'TypeVarDef'
        return TypeVarDef(data['name'],
                          data['id'],
                          [deserialize_type(v) for v in data['values']],
                          deserialize_type(data['upper_bound']),
                          data['variance'],
                          )


class UnboundType(Type):
    """Instance type that has not been bound during semantic analysis."""

    name = ''
    args = None  # type: List[Type]
    # should this type be wrapped in an Optional?
    optional = False

    # special case for X[()]
    empty_tuple_index = False

    def __init__(self,
                 name: str,
                 args: Optional[List[Type]] = None,
                 line: int = -1,
                 column: int = -1,
                 optional: bool = False,
                 empty_tuple_index: bool = False) -> None:
        if not args:
            args = []
        self.name = name
        self.args = args
        self.optional = optional
        self.empty_tuple_index = empty_tuple_index
        super().__init__(line, column)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_unbound_type(self)

    def __hash__(self) -> int:
        return hash((self.name, self.optional, tuple(self.args)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnboundType):
            return NotImplemented
        return (self.name == other.name and self.optional == other.optional and
                self.args == other.args)

    def serialize(self) -> JsonDict:
        return {'.class': 'UnboundType',
                'name': self.name,
                'args': [a.serialize() for a in self.args],
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'UnboundType':
        assert data['.class'] == 'UnboundType'
        return UnboundType(data['name'],
                           [deserialize_type(a) for a in data['args']])


class CallableArgument(Type):
    """Represents a Arg(type, 'name') inside a Callable's type list.

    Note that this is a synthetic type for helping parse ASTs, not a real type.
    """
    typ = None          # type: Type
    name = None         # type: Optional[str]
    constructor = None  # type: Optional[str]

    def __init__(self, typ: Type, name: Optional[str], constructor: Optional[str],
                 line: int = -1, column: int = -1) -> None:
        super().__init__(line, column)
        self.typ = typ
        self.name = name
        self.constructor = constructor

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        assert isinstance(visitor, SyntheticTypeVisitor)
        return visitor.visit_callable_argument(self)

    def serialize(self) -> JsonDict:
        assert False, "Synthetic types don't serialize"


class TypeList(Type):
    """Information about argument types and names [...].

    This is only used for the arguments of a Callable type, i.e. for
    [arg, ...] in Callable[[arg, ...], ret]. This is not a real type
    but a syntactic AST construct.
    """

    items = None  # type: List[Type]

    def __init__(self, items: List[Type], line: int = -1, column: int = -1) -> None:
        super().__init__(line, column)
        self.items = items

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        assert isinstance(visitor, SyntheticTypeVisitor)
        return visitor.visit_type_list(self)

    def serialize(self) -> JsonDict:
        assert False, "Sythetic types don't serialize"


_dummy = object()  # type: Any


class TypeOfAny:
    """
    This class describes different types of Any. Each 'Any' can be of only one type at a time.

    TODO: this class should be made an Enum once we drop support for python 3.3.
    """
    MYPY = False
    if MYPY:
        from typing import NewType
        TypeOfAny = NewType('TypeOfAny', str)
    else:
        def TypeOfAny(x: str) -> str:
            return x

    # Was this Any type was inferred without a type annotation?
    unannotated = TypeOfAny('unannotated')
    # Does this Any come from an explicit type annotation?
    explicit = TypeOfAny('explicit')
    # Does this come from an unfollowed import? See --disallow-any=unimported option
    from_unimported_type = TypeOfAny('from_unimported_type')
    # Does this Any type come from omitted generics?
    from_omitted_generics = TypeOfAny('from_omitted_generics')
    # Does this Any come from an error?
    from_error = TypeOfAny('from_error')
    # Is this a type that can't be represented in mypy's type system? For instance, type of
    # call to NewType(...)). Even though these types aren't real Anys, we treat them as such.
    special_form = TypeOfAny('special_form')
    # Does this Any come from interaction with another Any?
    from_another_any = TypeOfAny('from_another_any')


class AnyType(Type):
    """The type 'Any'."""

    def __init__(self,
                 type_of_any: TypeOfAny.TypeOfAny,
                 source_any: Optional['AnyType'] = None,
                 line: int = -1,
                 column: int = -1) -> None:
        super().__init__(line, column)
        self.type_of_any = type_of_any
        # If this Any was created as a result of interacting with another 'Any', record the source
        # and use it in reports.
        self.source_any = source_any
        if source_any and source_any.source_any:
            self.source_any = source_any.source_any

        # Only Anys that come from another Any can have source_any.
        assert type_of_any != TypeOfAny.from_another_any or source_any is not None
        # We should not have chains of Anys.
        assert not self.source_any or self.source_any.type_of_any != TypeOfAny.from_another_any

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_any(self)

    def copy_modified(self,
                      type_of_any: TypeOfAny.TypeOfAny = _dummy,
                      original_any: Optional['AnyType'] = _dummy,
                      ) -> 'AnyType':
        if type_of_any is _dummy:
            type_of_any = self.type_of_any
        if original_any is _dummy:
            original_any = self.source_any
        return AnyType(type_of_any=type_of_any, source_any=original_any,
                       line=self.line, column=self.column)

    def __hash__(self) -> int:
        return hash(AnyType)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AnyType)

    def serialize(self) -> JsonDict:
        return {'.class': 'AnyType'}

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'AnyType':
        assert data['.class'] == 'AnyType'
        return AnyType(TypeOfAny.special_form)


class UninhabitedType(Type):
    """This type has no members.

    This type is the bottom type.
    With strict Optional checking, it is the only common subtype between all
    other types, which allows `meet` to be well defined.  Without strict
    Optional checking, NoneTyp fills this role.

    In general, for any type T:
        join(UninhabitedType, T) = T
        meet(UninhabitedType, T) = UninhabitedType
        is_subtype(UninhabitedType, T) = True
    """

    can_be_true = False
    can_be_false = False
    is_noreturn = False  # Does this come from a NoReturn?  Purely for error messages.

    def __init__(self, is_noreturn: bool = False, line: int = -1, column: int = -1) -> None:
        super().__init__(line, column)
        self.is_noreturn = is_noreturn

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_uninhabited_type(self)

    def __hash__(self) -> int:
        return hash(UninhabitedType)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, UninhabitedType)

    def serialize(self) -> JsonDict:
        return {'.class': 'UninhabitedType',
                'is_noreturn': self.is_noreturn}

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'UninhabitedType':
        assert data['.class'] == 'UninhabitedType'
        return UninhabitedType(is_noreturn=data['is_noreturn'])


class NoneTyp(Type):
    """The type of 'None'.

    This type can be written by users as 'None'.
    """

    can_be_true = False

    def __init__(self, line: int = -1, column: int = -1) -> None:
        super().__init__(line, column)

    def __hash__(self) -> int:
        return hash(NoneTyp)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NoneTyp)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_none_type(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'NoneTyp'}

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'NoneTyp':
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

    source = ''  # type: Optional[str]  # May be None; name that generated this value

    def __init__(self, source: Optional[str] = None, line: int = -1, column: int = -1) -> None:
        self.source = source
        super().__init__(line, column)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_deleted_type(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'DeletedType',
                'source': self.source}

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'DeletedType':
        assert data['.class'] == 'DeletedType'
        return DeletedType(data['source'])


# Fake TypeInfo to be used as a placeholder during Instance de-serialization.
NOT_READY = mypy.nodes.FakeInfo(mypy.nodes.SymbolTable(),
                                mypy.nodes.ClassDef('<NOT READY>', mypy.nodes.Block([])),
                                '<NOT READY>')


class Instance(Type):
    """An instance type of form C[T1, ..., Tn].

    The list of type variables may be empty.
    """

    type = None  # type: mypy.nodes.TypeInfo
    args = None  # type: List[Type]
    erased = False  # True if result of type variable substitution
    invalid = False  # True if recovered after incorrect number of type arguments error
    from_generic_builtin = False  # True if created from a generic builtin (e.g. list() or set())

    def __init__(self, typ: mypy.nodes.TypeInfo, args: List[Type],
                 line: int = -1, column: int = -1, erased: bool = False) -> None:
        assert(typ is NOT_READY or typ.fullname() not in ["builtins.Any", "typing.Any"])
        self.type = typ
        self.args = args
        self.erased = erased
        super().__init__(line, column)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_instance(self)

    type_ref = None  # type: str

    def __hash__(self) -> int:
        return hash((self.type, tuple(self.args)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Instance):
            return NotImplemented
        return self.type == other.type and self.args == other.args

    def serialize(self) -> Union[JsonDict, str]:
        assert self.type is not None
        type_ref = self.type.fullname()
        if not self.args:
            return type_ref
        data = {'.class': 'Instance',
                }  # type: JsonDict
        data['type_ref'] = type_ref
        data['args'] = [arg.serialize() for arg in self.args]
        return data

    @classmethod
    def deserialize(cls, data: Union[JsonDict, str]) -> 'Instance':
        if isinstance(data, str):
            inst = Instance(NOT_READY, [])
            inst.type_ref = data
            return inst
        assert data['.class'] == 'Instance'
        args = []  # type: List[Type]
        if 'args' in data:
            args_list = data['args']
            assert isinstance(args_list, list)
            args = [deserialize_type(arg) for arg in args_list]
        inst = Instance(NOT_READY, args)
        inst.type_ref = data['type_ref']  # Will be fixed up by fixup.py later.
        return inst

    def copy_modified(self, *, args: List[Type]) -> 'Instance':
        return Instance(self.type, args, self.line, self.column, self.erased)


class TypeVarType(Type):
    """A type variable type.

    This refers to either a class type variable (id > 0) or a function
    type variable (id < 0).
    """

    name = ''  # Name of the type variable (for messages and debugging)
    id = None  # type: TypeVarId
    values = None  # type: List[Type]  # Value restriction, empty list if no restriction
    upper_bound = None  # type: Type   # Upper bound for values
    # See comments in TypeVarDef for more about variance.
    variance = INVARIANT  # type: int

    def __init__(self, binder: TypeVarDef, line: int = -1, column: int = -1) -> None:
        self.name = binder.name
        self.id = binder.id
        self.values = binder.values
        self.upper_bound = binder.upper_bound
        self.variance = binder.variance
        super().__init__(line, column)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_type_var(self)

    def erase_to_union_or_bound(self) -> Type:
        if self.values:
            return UnionType.make_simplified_union(self.values)
        else:
            return self.upper_bound

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypeVarType):
            return NotImplemented
        return self.id == other.id

    def serialize(self) -> JsonDict:
        assert not self.id.is_meta_var()
        return {'.class': 'TypeVarType',
                'name': self.name,
                'id': self.id.raw_id,
                'values': [v.serialize() for v in self.values],
                'upper_bound': self.upper_bound.serialize(),
                'variance': self.variance,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeVarType':
        assert data['.class'] == 'TypeVarType'
        tvdef = TypeVarDef(data['name'],
                           data['id'],
                           [deserialize_type(v) for v in data['values']],
                           deserialize_type(data['upper_bound']),
                           data['variance'])
        return TypeVarType(tvdef)


class FunctionLike(Type):
    """Abstract base class for function types."""

    can_be_false = False

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

    @abstractmethod
    def get_name(self) -> Optional[str]: pass

    # Corresponding instance type (e.g. builtins.type)
    fallback = None  # type: Instance


FormalArgument = NamedTuple('FormalArgument', [
    ('name', Optional[str]),
    ('pos', Optional[int]),
    ('typ', Type),
    ('required', bool)])


class CallableType(FunctionLike):
    """Type of a non-overloaded callable object (function)."""

    arg_types = None  # type: List[Type]  # Types of function arguments
    arg_kinds = None  # type: List[int]   # ARG_ constants
    arg_names = None  # type: List[Optional[str]]   # None if not a keyword argument
    min_args = 0                    # Minimum number of arguments; derived from arg_kinds
    is_var_arg = False              # Is it a varargs function?  derived from arg_kinds
    is_kw_arg = False
    ret_type = None  # type: Type   # Return value type
    name = ''   # type: Optional[str]  # Name (may be None; for error messages and plugins)
    definition = None  # type: Optional[SymbolNode] # For error messages.  May be None.
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
    # Was this callable generated by analyzing Type[...] instantiation?
    from_type_type = False  # type: bool

    bound_args = None  # type: List[Optional[Type]]

    def __init__(self,
                 arg_types: List[Type],
                 arg_kinds: List[int],
                 arg_names: List[Optional[str]],
                 ret_type: Type,
                 fallback: Instance,
                 name: Optional[str] = None,
                 definition: Optional[SymbolNode] = None,
                 variables: Optional[List[TypeVarDef]] = None,
                 line: int = -1,
                 column: int = -1,
                 is_ellipsis_args: bool = False,
                 implicit: bool = False,
                 is_classmethod_class: bool = False,
                 special_sig: Optional[str] = None,
                 from_type_type: bool = False,
                 bound_args: Optional[List[Optional[Type]]] = None,
                 ) -> None:
        if variables is None:
            variables = []
        assert len(arg_types) == len(arg_kinds)
        assert not any(tp is None for tp in arg_types), "No annotation must be Any, not None"
        self.arg_types = arg_types
        self.arg_kinds = arg_kinds
        self.arg_names = arg_names
        self.min_args = arg_kinds.count(ARG_POS)
        self.is_var_arg = ARG_STAR in arg_kinds
        self.is_kw_arg = ARG_STAR2 in arg_kinds
        self.ret_type = ret_type
        self.fallback = fallback
        assert not name or '<bound method' not in name
        self.name = name
        self.definition = definition
        self.variables = variables
        self.is_ellipsis_args = is_ellipsis_args
        self.implicit = implicit
        self.is_classmethod_class = is_classmethod_class
        self.special_sig = special_sig
        self.from_type_type = from_type_type
        self.bound_args = bound_args or []
        super().__init__(line, column)

    def copy_modified(self,
                      arg_types: List[Type] = _dummy,
                      arg_kinds: List[int] = _dummy,
                      arg_names: List[Optional[str]] = _dummy,
                      ret_type: Type = _dummy,
                      fallback: Instance = _dummy,
                      name: Optional[str] = _dummy,
                      definition: SymbolNode = _dummy,
                      variables: List[TypeVarDef] = _dummy,
                      line: int = _dummy,
                      column: int = _dummy,
                      is_ellipsis_args: bool = _dummy,
                      special_sig: Optional[str] = _dummy,
                      from_type_type: bool = _dummy,
                      bound_args: List[Optional[Type]] = _dummy) -> 'CallableType':
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
            column=column if column is not _dummy else self.column,
            is_ellipsis_args=(
                is_ellipsis_args if is_ellipsis_args is not _dummy else self.is_ellipsis_args),
            implicit=self.implicit,
            is_classmethod_class=self.is_classmethod_class,
            special_sig=special_sig if special_sig is not _dummy else self.special_sig,
            from_type_type=from_type_type if from_type_type is not _dummy else self.from_type_type,
            bound_args=bound_args if bound_args is not _dummy else self.bound_args,
        )

    def is_type_obj(self) -> bool:
        return self.fallback.type.is_metaclass()

    def is_concrete_type_obj(self) -> bool:
        return self.is_type_obj() and self.is_classmethod_class

    def type_object(self) -> mypy.nodes.TypeInfo:
        assert self.is_type_obj()
        ret = self.ret_type
        if isinstance(ret, TupleType):
            ret = ret.fallback
        if isinstance(ret, TypeVarType):
            ret = ret.upper_bound
        assert isinstance(ret, Instance)
        return ret.type

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_callable_type(self)

    def with_name(self, name: str) -> 'CallableType':
        """Return a copy of this type with the specified name."""
        return self.copy_modified(ret_type=self.ret_type, name=name)

    def get_name(self) -> Optional[str]:
        return self.name

    def max_fixed_args(self) -> int:
        n = len(self.arg_types)
        if self.is_var_arg:
            n -= 1
        return n

    def corresponding_argument(self, model: FormalArgument) -> Optional[FormalArgument]:
        """Return the argument in this function that corresponds to `model`"""

        by_name = self.argument_by_name(model.name)
        by_pos = self.argument_by_position(model.pos)
        if by_name is None and by_pos is None:
            return None
        if by_name is not None and by_pos is not None:
            if by_name == by_pos:
                return by_name
            # If we're dealing with an optional pos-only and an optional
            # name-only arg, merge them.  This is the case for all functions
            # taking both *args and **args, or a pair of functions like so:

            # def right(a: int = ...) -> None: ...
            # def left(__a: int = ..., *, a: int = ...) -> None: ...
            from mypy.subtypes import is_equivalent
            if (not (by_name.required or by_pos.required)
                    and by_pos.name is None
                    and by_name.pos is None
                    and is_equivalent(by_name.typ, by_pos.typ)):
                return FormalArgument(by_name.name, by_pos.pos, by_name.typ, False)
        return by_name if by_name is not None else by_pos

    def argument_by_name(self, name: Optional[str]) -> Optional[FormalArgument]:
        if name is None:
            return None
        seen_star = False
        star2_type = None  # type: Optional[Type]
        for i, (arg_name, kind, typ) in enumerate(
                zip(self.arg_names, self.arg_kinds, self.arg_types)):
            # No more positional arguments after these.
            if kind in (ARG_STAR, ARG_STAR2, ARG_NAMED, ARG_NAMED_OPT):
                seen_star = True
            if kind == ARG_STAR:
                continue
            if kind == ARG_STAR2:
                star2_type = typ
                continue
            if arg_name == name:
                position = None if seen_star else i
                return FormalArgument(name, position, typ, kind in (ARG_POS, ARG_NAMED))
        if star2_type is not None:
            return FormalArgument(name, None, star2_type, False)
        return None

    def argument_by_position(self, position: Optional[int]) -> Optional[FormalArgument]:
        if position is None:
            return None
        if self.is_var_arg:
            for kind, typ in zip(self.arg_kinds, self.arg_types):
                if kind == ARG_STAR:
                    star_type = typ
                    break
        if position >= len(self.arg_names):
            if self.is_var_arg:
                return FormalArgument(None, position, star_type, False)
            else:
                return None
        name, kind, typ = (
            self.arg_names[position],
            self.arg_kinds[position],
            self.arg_types[position],
        )
        if kind in (ARG_POS, ARG_OPT):
            return FormalArgument(name, position, typ, kind == ARG_POS)
        else:
            if self.is_var_arg:
                return FormalArgument(None, position, star_type, False)
            else:
                return None

    def items(self) -> List['CallableType']:
        return [self]

    def is_generic(self) -> bool:
        return bool(self.variables)

    def type_var_ids(self) -> List[TypeVarId]:
        a = []  # type: List[TypeVarId]
        for tv in self.variables:
            a.append(tv.id)
        return a

    def __hash__(self) -> int:
        return hash((self.ret_type, self.is_type_obj(),
                     self.is_ellipsis_args, self.name,
                    tuple(self.arg_types), tuple(self.arg_names), tuple(self.arg_kinds)))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CallableType):
            return (self.ret_type == other.ret_type and
                    self.arg_types == other.arg_types and
                    self.arg_names == other.arg_names and
                    self.arg_kinds == other.arg_kinds and
                    self.name == other.name and
                    self.is_type_obj() == other.is_type_obj() and
                    self.is_ellipsis_args == other.is_ellipsis_args)
        else:
            return NotImplemented

    def serialize(self) -> JsonDict:
        # TODO: As an optimization, leave out everything related to
        # generic functions for non-generic functions.
        return {'.class': 'CallableType',
                'arg_types': [t.serialize() for t in self.arg_types],
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
                'bound_args': [(None if t is None else t.serialize())
                               for t in self.bound_args],
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'CallableType':
        assert data['.class'] == 'CallableType'
        # TODO: Set definition to the containing SymbolNode?
        return CallableType([deserialize_type(t) for t in data['arg_types']],
                            data['arg_kinds'],
                            data['arg_names'],
                            deserialize_type(data['ret_type']),
                            Instance.deserialize(data['fallback']),
                            name=data['name'],
                            variables=[TypeVarDef.deserialize(v) for v in data['variables']],
                            is_ellipsis_args=data['is_ellipsis_args'],
                            implicit=data['implicit'],
                            is_classmethod_class=data['is_classmethod_class'],
                            bound_args=[(None if t is None else deserialize_type(t))
                                        for t in data['bound_args']],
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
        super().__init__(items[0].line, items[0].column)

    def items(self) -> List[CallableType]:
        return self._items

    def name(self) -> Optional[str]:
        return self.get_name()

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

    def get_name(self) -> Optional[str]:
        return self._items[0].name

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_overloaded(self)

    def __hash__(self) -> int:
        return hash(tuple(self.items()))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Overloaded):
            return NotImplemented
        return self.items() == other.items()

    def serialize(self) -> JsonDict:
        return {'.class': 'Overloaded',
                'items': [t.serialize() for t in self.items()],
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Overloaded':
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
                 column: int = -1, implicit: bool = False) -> None:
        self.items = items
        self.fallback = fallback
        self.implicit = implicit
        self.can_be_true = len(self.items) > 0
        self.can_be_false = len(self.items) == 0
        super().__init__(line, column)

    def length(self) -> int:
        return len(self.items)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_tuple_type(self)

    def __hash__(self) -> int:
        return hash((tuple(self.items), self.fallback))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TupleType):
            return NotImplemented
        return self.items == other.items and self.fallback == other.fallback

    def serialize(self) -> JsonDict:
        return {'.class': 'TupleType',
                'items': [t.serialize() for t in self.items],
                'fallback': self.fallback.serialize(),
                'implicit': self.implicit,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TupleType':
        assert data['.class'] == 'TupleType'
        return TupleType([deserialize_type(t) for t in data['items']],
                         Instance.deserialize(data['fallback']),
                         implicit=data['implicit'])

    def copy_modified(self, *, fallback: Optional[Instance] = None,
                      items: Optional[List[Type]] = None) -> 'TupleType':
        if fallback is None:
            fallback = self.fallback
        if items is None:
            items = self.items
        return TupleType(items, fallback, self.line, self.column)

    def slice(self, begin: Optional[int], stride: Optional[int],
              end: Optional[int]) -> 'TupleType':
        return TupleType(self.items[begin:end:stride], self.fallback,
                         self.line, self.column, self.implicit)


class TypedDictType(Type):
    """The type of a TypedDict instance. TypedDict(K1=VT1, ..., Kn=VTn)

    A TypedDictType can be either named or anonymous.
    If it is anonymous then its fallback will be an Instance of Mapping[str, V].
    If it is named then its fallback will be an Instance of the named type (ex: "Point")
    whose TypeInfo has a typeddict_type that is anonymous.
    """

    items = None  # type: OrderedDict[str, Type]  # item_name -> item_type
    required_keys = None  # type: Set[str]
    fallback = None  # type: Instance

    def __init__(self, items: 'OrderedDict[str, Type]', required_keys: Set[str],
                 fallback: Instance, line: int = -1, column: int = -1) -> None:
        self.items = items
        self.required_keys = required_keys
        self.fallback = fallback
        self.can_be_true = len(self.items) > 0
        self.can_be_false = len(self.items) == 0
        super().__init__(line, column)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_typeddict_type(self)

    def __hash__(self) -> int:
        return hash((frozenset(self.items.items()), self.fallback,
                     frozenset(self.required_keys)))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TypedDictType):
            if frozenset(self.items.keys()) != frozenset(other.items.keys()):
                return False
            for (_, left_item_type, right_item_type) in self.zip(other):
                if not left_item_type == right_item_type:
                    return False
            return self.fallback == other.fallback and self.required_keys == other.required_keys
        else:
            return NotImplemented

    def serialize(self) -> JsonDict:
        return {'.class': 'TypedDictType',
                'items': [[n, t.serialize()] for (n, t) in self.items.items()],
                'required_keys': sorted(self.required_keys),
                'fallback': self.fallback.serialize(),
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypedDictType':
        assert data['.class'] == 'TypedDictType'
        return TypedDictType(OrderedDict([(n, deserialize_type(t))
                                          for (n, t) in data['items']]),
                             set(data['required_keys']),
                             Instance.deserialize(data['fallback']))

    def is_anonymous(self) -> bool:
        return self.fallback.type.fullname() == 'typing.Mapping'

    def as_anonymous(self) -> 'TypedDictType':
        if self.is_anonymous():
            return self
        assert self.fallback.type.typeddict_type is not None
        return self.fallback.type.typeddict_type.as_anonymous()

    def copy_modified(self, *, fallback: Optional[Instance] = None,
                      item_types: Optional[List[Type]] = None,
                      required_keys: Optional[Set[str]] = None) -> 'TypedDictType':
        if fallback is None:
            fallback = self.fallback
        if item_types is None:
            items = self.items
        else:
            items = OrderedDict(zip(self.items, item_types))
        if required_keys is None:
            required_keys = self.required_keys
        return TypedDictType(items, required_keys, fallback, self.line, self.column)

    def create_anonymous_fallback(self, *, value_type: Type) -> Instance:
        anonymous = self.as_anonymous()
        return anonymous.fallback.copy_modified(args=[  # i.e. Mapping
            anonymous.fallback.args[0],                 # i.e. str
            value_type
        ])

    def names_are_wider_than(self, other: 'TypedDictType') -> bool:
        return len(other.items.keys() - self.items.keys()) == 0

    def zip(self, right: 'TypedDictType') -> Iterable[Tuple[str, Type, Type]]:
        left = self
        for (item_name, left_item_type) in left.items.items():
            right_item_type = right.items.get(item_name)
            if right_item_type is not None:
                yield (item_name, left_item_type, right_item_type)

    def zipall(self, right: 'TypedDictType') \
            -> Iterable[Tuple[str, Optional[Type], Optional[Type]]]:
        left = self
        for (item_name, left_item_type) in left.items.items():
            right_item_type = right.items.get(item_name)
            yield (item_name, left_item_type, right_item_type)
        for (item_name, right_item_type) in right.items.items():
            if item_name in left.items:
                continue
            yield (item_name, None, right_item_type)


class StarType(Type):
    """The star type *type_parameter.

    This is not a real type but a syntactic AST construct.
    """

    type = None  # type: Type

    def __init__(self, type: Type, line: int = -1, column: int = -1) -> None:
        self.type = type
        super().__init__(line, column)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        assert isinstance(visitor, SyntheticTypeVisitor)
        return visitor.visit_star_type(self)

    def serialize(self) -> JsonDict:
        assert False, "Sythetic types don't serialize"


class UnionType(Type):
    """The union type Union[T1, ..., Tn] (at least one type argument)."""

    items = None  # type: List[Type]

    def __init__(self, items: List[Type], line: int = -1, column: int = -1) -> None:
        self.items = flatten_nested_unions(items)
        self.can_be_true = any(item.can_be_true for item in items)
        self.can_be_false = any(item.can_be_false for item in items)
        super().__init__(line, column)

    def __hash__(self) -> int:
        return hash(frozenset(self.items))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnionType):
            return NotImplemented
        return frozenset(self.items) == frozenset(other.items)

    @staticmethod
    def make_union(items: List[Type], line: int = -1, column: int = -1) -> Type:
        if len(items) > 1:
            return UnionType(items, line, column)
        elif len(items) == 1:
            return items[0]
        else:
            return UninhabitedType()

    @staticmethod
    def make_simplified_union(items: List[Type], line: int = -1, column: int = -1) -> Type:
        """Build union type with redundant union items removed.

        If only a single item remains, this may return a non-union type.

        Examples:

        * [int, str] -> Union[int, str]
        * [int, object] -> object
        * [int, int] -> int
        * [int, Any] -> Union[int, Any] (Any types are not simplified away!)
        * [Any, Any] -> Any

        Note: This must NOT be used during semantic analysis, since TypeInfos may not
              be fully initialized.
        """
        # TODO: Make this a function living somewhere outside mypy.types. Most other non-trivial
        #       type operations are not static methods, so this is inconsistent.
        while any(isinstance(typ, UnionType) for typ in items):
            all_items = []  # type: List[Type]
            for typ in items:
                if isinstance(typ, UnionType):
                    all_items.extend(typ.items)
                else:
                    all_items.append(typ)
            items = all_items

        from mypy.subtypes import is_proper_subtype

        removed = set()  # type: Set[int]
        for i, ti in enumerate(items):
            if i in removed: continue
            # Keep track of the truishness info for deleted subtypes which can be relevant
            cbt = cbf = False
            for j, tj in enumerate(items):
                if (i != j and is_proper_subtype(tj, ti)):
                    # We found a redundant item in the union.
                    removed.add(j)
                    cbt = cbt or tj.can_be_true
                    cbf = cbf or tj.can_be_false
            # if deleted subtypes had more general truthiness, use that
            if not ti.can_be_true and cbt:
                items[i] = true_or_false(ti)
            elif not ti.can_be_false and cbf:
                items[i] = true_or_false(ti)

        simplified_set = [items[i] for i in range(len(items)) if i not in removed]
        return UnionType.make_union(simplified_set, line, column)

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
                   for x in self.relevant_items())

    def relevant_items(self) -> List[Type]:
        """Removes NoneTypes from Unions when strict Optional checking is off."""
        if experiments.STRICT_OPTIONAL:
            return self.items
        else:
            return [i for i in self.items if not isinstance(i, NoneTyp)]

    def serialize(self) -> JsonDict:
        return {'.class': 'UnionType',
                'items': [t.serialize() for t in self.items],
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'UnionType':
        assert data['.class'] == 'UnionType'
        return UnionType([deserialize_type(t) for t in data['items']])


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
    inner_types = None  # type: List[Type]

    def __init__(self,
                 type: 'Optional[mypy.nodes.TypeInfo]',
                 var: 'mypy.nodes.Var',
                 inner_types: List[Type]) -> None:
        self.type = type
        self.var = var
        self.inner_types = inner_types

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_partial_type(self)


class EllipsisType(Type):
    """The type ... (ellipsis).

    This is not a real type but a syntactic AST construct, used in Callable[..., T], for example.

    A semantically analyzed type will never have ellipsis types.
    """

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        assert isinstance(visitor, SyntheticTypeVisitor)
        return visitor.visit_ellipsis_type(self)

    def serialize(self) -> JsonDict:
        assert False, "Synthetic types don't serialize"


class TypeType(Type):
    """For types like Type[User].

    This annotates variables that are class objects, constrained by
    the type argument.  See PEP 484 for more details.

    We may encounter expressions whose values are specific classes;
    those are represented as callables (possibly overloaded)
    corresponding to the class's constructor's signature and returning
    an instance of that class.  The difference with Type[C] is that
    those callables always represent the exact class given as the
    return type; Type[C] represents any class that's a subclass of C,
    and C may also be a type variable or a union (or Any).

    Many questions around subtype relationships between Type[C1] and
    def(...) -> C2 are answered by looking at the subtype
    relationships between C1 and C2, since Type[] is considered
    covariant.

    There's an unsolved problem with constructor signatures (also
    unsolved in PEP 484): calling a variable whose type is Type[C]
    assumes the constructor signature for C, even though a subclass of
    C might completely change the constructor signature.  For now we
    just assume that users of Type[C] are careful not to do that (in
    the future we might detect when they are violating that
    assumption).
    """

    # This can't be everything, but it can be a class reference,
    # a generic class instance, a union, Any, a type variable...
    item = None  # type: Type

    def __init__(self, item: Union[Instance, AnyType, TypeVarType, TupleType, NoneTyp,
                                   CallableType], *, line: int = -1, column: int = -1) -> None:
        """To ensure Type[Union[A, B]] is always represented as Union[Type[A], Type[B]], item of
        type UnionType must be handled through make_normalized static method.
        """
        super().__init__(line, column)
        self.item = item

    @staticmethod
    def make_normalized(item: Type, *, line: int = -1, column: int = -1) -> Type:
        if isinstance(item, UnionType):
            return UnionType.make_union(
                [TypeType.make_normalized(union_item) for union_item in item.items],
                line=line, column=column
            )
        return TypeType(item, line=line, column=column)  # type: ignore

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_type_type(self)

    def __hash__(self) -> int:
        return hash(self.item)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypeType):
            return NotImplemented
        return self.item == other.item

    def serialize(self) -> JsonDict:
        return {'.class': 'TypeType', 'item': self.item.serialize()}

    @classmethod
    def deserialize(cls, data: JsonDict) -> Type:
        assert data['.class'] == 'TypeType'
        return TypeType.make_normalized(deserialize_type(data['item']))


class ForwardRef(Type):
    """Class to wrap forward references to other types.

    This is used when a forward reference to an (unanalyzed) synthetic type is found,
    for example:

        x: A
        A = TypedDict('A', {'x': int})

    To avoid false positives and crashes in such situations, we first wrap the first
    occurrence of 'A' in ForwardRef. Then, the wrapped UnboundType is updated in the third
    pass of semantic analysis and ultimately fixed in the patches after the third pass.
    So that ForwardRefs are temporary and will be completely replaced with the linked types
    or Any (to avoid cyclic references) before the type checking stage.
    """
    _unbound = None  # type: UnboundType  # The original wrapped type
    _resolved = None  # type: Optional[Type]  # The resolved forward reference (initially None)

    def __init__(self, unbound: UnboundType) -> None:
        self._unbound = unbound
        self._resolved = None

    @property
    def unbound(self) -> UnboundType:
        # This is read-only to make it clear that resolution happens through resolve().
        return self._unbound

    @property
    def resolved(self) -> Optional[Type]:
        # Similar to above.
        return self._resolved

    def resolve(self, resolved: Type) -> None:
        """Resolve an unbound forward reference to point to a type."""
        assert self._resolved is None
        self._resolved = resolved

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_forwardref_type(self)

    def serialize(self) -> str:
        name = self.unbound.name
        # We should never get here since all forward references should be resolved
        # and removed during semantic analysis.
        assert False, "Internal error: Unresolved forward reference to {}".format(name)


#
# Visitor-related classes
#


class TypeVisitor(Generic[T]):
    """Visitor class for types (Type subclasses).

    The parameter T is the return type of the visit methods.
    """

    def _notimplemented_helper(self, name: str) -> NotImplementedError:
        return NotImplementedError("Method {}.visit_{}() not implemented\n"
                                   .format(type(self).__name__, name)
                                   + "This is a known bug, track development in "
                                   + "'https://github.com/JukkaL/mypy/issues/730'")

    @abstractmethod
    def visit_unbound_type(self, t: UnboundType) -> T:
        pass

    @abstractmethod
    def visit_any(self, t: AnyType) -> T:
        pass

    @abstractmethod
    def visit_none_type(self, t: NoneTyp) -> T:
        pass

    @abstractmethod
    def visit_uninhabited_type(self, t: UninhabitedType) -> T:
        pass

    def visit_erased_type(self, t: ErasedType) -> T:
        raise self._notimplemented_helper('erased_type')

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
        raise self._notimplemented_helper('overloaded')

    @abstractmethod
    def visit_tuple_type(self, t: TupleType) -> T:
        pass

    @abstractmethod
    def visit_typeddict_type(self, t: TypedDictType) -> T:
        pass

    @abstractmethod
    def visit_union_type(self, t: UnionType) -> T:
        pass

    @abstractmethod
    def visit_partial_type(self, t: PartialType) -> T:
        pass

    @abstractmethod
    def visit_type_type(self, t: TypeType) -> T:
        pass

    def visit_forwardref_type(self, t: ForwardRef) -> T:
        raise RuntimeError('Internal error: unresolved forward reference')


class SyntheticTypeVisitor(TypeVisitor[T]):
    """A TypeVisitor that also knows how to visit synthetic AST constructs.

       Not just real types."""

    @abstractmethod
    def visit_star_type(self, t: StarType) -> T:
        pass

    @abstractmethod
    def visit_type_list(self, t: TypeList) -> T:
        pass

    @abstractmethod
    def visit_callable_argument(self, t: CallableArgument) -> T:
        pass

    @abstractmethod
    def visit_ellipsis_type(self, t: EllipsisType) -> T:
        pass


class TypeTranslator(TypeVisitor[Type]):
    """Identity type transformation.

    Subclass this and override some methods to implement a non-trivial
    transformation.
    """

    def visit_unbound_type(self, t: UnboundType) -> Type:
        return t

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_erased_type(self, t: ErasedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_instance(self, t: Instance) -> Type:
        return Instance(t.type, self.translate_types(t.args), t.line, t.column)

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
                         # TODO: This appears to be unsafe.
                         cast(Any, t.fallback.accept(self)),
                         t.line, t.column)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        items = OrderedDict([
            (item_name, item_type.accept(self))
            for (item_name, item_type) in t.items.items()
        ])
        return TypedDictType(items,
                             t.required_keys,
                             # TODO: This appears to be unsafe.
                             cast(Any, t.fallback.accept(self)),
                             t.line, t.column)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.translate_types(t.items), t.line, t.column)

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

    def visit_type_type(self, t: TypeType) -> Type:
        return TypeType.make_normalized(t.item.accept(self), line=t.line, column=t.column)

    def visit_forwardref_type(self, t: ForwardRef) -> Type:
        return t


class TypeStrVisitor(SyntheticTypeVisitor[str]):
    """Visitor for pretty-printing types into strings.

    This is mostly for debugging/testing.

    Do not preserve original formatting.

    Notes:
     - Represent unbound types as Foo? or Foo?[...].
     - Represent the NoneTyp type as None.
    """

    def __init__(self, id_mapper: Optional[IdMapper] = None) -> None:
        self.id_mapper = id_mapper

    def visit_unbound_type(self, t: UnboundType)-> str:
        s = t.name + '?'
        if t.args != []:
            s += '[{}]'.format(self.list_str(t.args))
        return s

    def visit_type_list(self, t: TypeList) -> str:
        return '<TypeList {}>'.format(self.list_str(t.items))

    def visit_callable_argument(self, t: CallableArgument) -> str:
        typ = t.typ.accept(self)
        if t.name is None:
            return "{}({})".format(t.constructor, typ)
        else:
            return "{}({}, {})".format(t.constructor, typ, t.name)

    def visit_any(self, t: AnyType) -> str:
        return 'Any'

    def visit_none_type(self, t: NoneTyp) -> str:
        # Fully qualify to make this distinct from the None value.
        return "builtins.None"

    def visit_uninhabited_type(self, t: UninhabitedType) -> str:
        return "<nothing>"

    def visit_erased_type(self, t: ErasedType) -> str:
        return "<Erased>"

    def visit_deleted_type(self, t: DeletedType) -> str:
        if t.source is None:
            return "<Deleted>"
        else:
            return "<Deleted '{}'>".format(t.source)

    def visit_instance(self, t: Instance) -> str:
        if t.type is not None:
            s = t.type.fullname() or t.type.name() or '<???>'
        else:
            s = '<?>'
        if t.erased:
            s += '*'
        if t.args != []:
            s += '[{}]'.format(self.list_str(t.args))
        if self.id_mapper:
            s += '<{}>'.format(self.id_mapper.id(t.type))
        return s

    def visit_type_var(self, t: TypeVarType) -> str:
        if t.name is None:
            # Anonymous type variable type (only numeric id).
            return '`{}'.format(t.id)
        else:
            # Named type variable type.
            return '{}`{}'.format(t.name, t.id)

    def visit_callable_type(self, t: CallableType) -> str:
        s = ''
        bare_asterisk = False
        for i in range(len(t.arg_types)):
            if s != '':
                s += ', '
            if t.arg_kinds[i] in (ARG_NAMED, ARG_NAMED_OPT) and not bare_asterisk:
                s += '*, '
                bare_asterisk = True
            if t.arg_kinds[i] == ARG_STAR:
                s += '*'
            if t.arg_kinds[i] == ARG_STAR2:
                s += '**'
            name = t.arg_names[i]
            if name:
                s += name + ': '
            s += t.arg_types[i].accept(self)
            if t.arg_kinds[i] in (ARG_OPT, ARG_NAMED_OPT):
                s += ' ='

        s = '({})'.format(s)

        if not isinstance(t.ret_type, NoneTyp):
            s += ' -> {}'.format(t.ret_type.accept(self))

        if t.variables:
            s = '{} {}'.format(t.variables, s)

        return 'def {}'.format(s)

    def visit_overloaded(self, t: Overloaded) -> str:
        a = []
        for i in t.items():
            a.append(i.accept(self))
        return 'Overload({})'.format(', '.join(a))

    def visit_tuple_type(self, t: TupleType) -> str:
        s = self.list_str(t.items)
        if t.fallback and t.fallback.type:
            fallback_name = t.fallback.type.fullname()
            if fallback_name != 'builtins.tuple':
                return 'Tuple[{}, fallback={}]'.format(s, t.fallback.accept(self))
        return 'Tuple[{}]'.format(s)

    def visit_typeddict_type(self, t: TypedDictType) -> str:
        def item_str(name: str, typ: str) -> str:
            if name in t.required_keys:
                return '{!r}: {}'.format(name, typ)
            else:
                return '{!r}?: {}'.format(name, typ)

        s = '{' + ', '.join(item_str(name, typ.accept(self))
                            for name, typ in t.items.items()) + '}'
        prefix = ''
        suffix = ''
        if t.fallback and t.fallback.type:
            if t.fallback.type.fullname() != 'typing.Mapping':
                prefix = repr(t.fallback.type.fullname()) + ', '
            else:
                suffix = ', fallback={}'.format(t.fallback.accept(self))
        return 'TypedDict({}{}{})'.format(prefix, s, suffix)

    def visit_star_type(self, t: StarType) -> str:
        s = t.type.accept(self)
        return '*{}'.format(s)

    def visit_union_type(self, t: UnionType) -> str:
        s = self.list_str(t.items)
        return 'Union[{}]'.format(s)

    def visit_partial_type(self, t: PartialType) -> str:
        if t.type is None:
            return '<partial None>'
        else:
            return '<partial {}[{}]>'.format(t.type.name(),
                                             ', '.join(['?'] * len(t.type.type_vars)))

    def visit_ellipsis_type(self, t: EllipsisType) -> str:
        return '...'

    def visit_type_type(self, t: TypeType) -> str:
        return 'Type[{}]'.format(t.item.accept(self))

    def visit_forwardref_type(self, t: ForwardRef) -> str:
        if t.resolved:
            return '~{}'.format(t.resolved.accept(self))
        else:
            return '~{}'.format(t.unbound.accept(self))

    def list_str(self, a: List[Type]) -> str:
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


class TypeQuery(SyntheticTypeVisitor[T]):
    """Visitor for performing queries of types.

    strategy is used to combine results for a series of types

    Common use cases involve a boolean query using `any` or `all`
    """

    def __init__(self, strategy: Callable[[Iterable[T]], T]) -> None:
        self.strategy = strategy

    def visit_unbound_type(self, t: UnboundType) -> T:
        return self.query_types(t.args)

    def visit_type_list(self, t: TypeList) -> T:
        return self.query_types(t.items)

    def visit_callable_argument(self, t: CallableArgument) -> T:
        return t.typ.accept(self)

    def visit_any(self, t: AnyType) -> T:
        return self.strategy([])

    def visit_uninhabited_type(self, t: UninhabitedType) -> T:
        return self.strategy([])

    def visit_none_type(self, t: NoneTyp) -> T:
        return self.strategy([])

    def visit_erased_type(self, t: ErasedType) -> T:
        return self.strategy([])

    def visit_deleted_type(self, t: DeletedType) -> T:
        return self.strategy([])

    def visit_type_var(self, t: TypeVarType) -> T:
        return self.strategy([])

    def visit_partial_type(self, t: PartialType) -> T:
        return self.query_types(t.inner_types)

    def visit_instance(self, t: Instance) -> T:
        return self.query_types(t.args)

    def visit_callable_type(self, t: CallableType) -> T:
        # FIX generics
        return self.query_types(t.arg_types + [t.ret_type])

    def visit_tuple_type(self, t: TupleType) -> T:
        return self.query_types(t.items)

    def visit_typeddict_type(self, t: TypedDictType) -> T:
        return self.query_types(t.items.values())

    def visit_star_type(self, t: StarType) -> T:
        return t.type.accept(self)

    def visit_union_type(self, t: UnionType) -> T:
        return self.query_types(t.items)

    def visit_overloaded(self, t: Overloaded) -> T:
        return self.query_types(t.items())

    def visit_type_type(self, t: TypeType) -> T:
        return t.item.accept(self)

    def visit_forwardref_type(self, t: ForwardRef) -> T:
        if t.resolved:
            return t.resolved.accept(self)
        else:
            return t.unbound.accept(self)

    def visit_ellipsis_type(self, t: EllipsisType) -> T:
        return self.strategy([])

    def query_types(self, types: Iterable[Type]) -> T:
        """Perform a query for a list of types.

        Use the strategy to combine the results.
        """
        return self.strategy(t.accept(self) for t in types)


def strip_type(typ: Type) -> Type:
    """Make a copy of type without 'debugging info' (function name)."""

    if isinstance(typ, CallableType):
        return typ.copy_modified(name=None)
    elif isinstance(typ, Overloaded):
        return Overloaded([cast(CallableType, strip_type(item))
                           for item in typ.items()])
    else:
        return typ


def is_named_instance(t: Type, fullname: str) -> bool:
    return (isinstance(t, Instance) and
            t.type is not None and
            t.type.fullname() == fullname)


def copy_type(t: Type) -> Type:
    """
    Build a copy of the type; used to mutate the copy with truthiness information
    """
    return copy.copy(t)


def true_only(t: Type) -> Type:
    """
    Restricted version of t with only True-ish values
    """
    if not t.can_be_true:
        # All values of t are False-ish, so there are no true values in it
        return UninhabitedType(line=t.line, column=t.column)
    elif not t.can_be_false:
        # All values of t are already True-ish, so true_only is idempotent in this case
        return t
    elif isinstance(t, UnionType):
        # The true version of a union type is the union of the true versions of its components
        new_items = [true_only(item) for item in t.items]
        return UnionType.make_simplified_union(new_items, line=t.line, column=t.column)
    else:
        new_t = copy_type(t)
        new_t.can_be_false = False
        return new_t


def false_only(t: Type) -> Type:
    """
    Restricted version of t with only False-ish values
    """
    if not t.can_be_false:
        # All values of t are True-ish, so there are no false values in it
        return UninhabitedType(line=t.line)
    elif not t.can_be_true:
        # All values of t are already False-ish, so false_only is idempotent in this case
        return t
    elif isinstance(t, UnionType):
        # The false version of a union type is the union of the false versions of its components
        new_items = [false_only(item) for item in t.items]
        return UnionType.make_simplified_union(new_items, line=t.line, column=t.column)
    else:
        new_t = copy_type(t)
        new_t.can_be_true = False
        return new_t


def true_or_false(t: Type) -> Type:
    """
    Unrestricted version of t with both True-ish and False-ish values
    """
    if isinstance(t, UnionType):
        new_items = [true_or_false(item) for item in t.items]
        return UnionType.make_simplified_union(new_items, line=t.line, column=t.column)

    new_t = copy_type(t)
    new_t.can_be_true = type(new_t).can_be_true
    new_t.can_be_false = type(new_t).can_be_false
    return new_t


def function_type(func: mypy.nodes.FuncBase, fallback: Instance) -> FunctionLike:
    if func.type:
        assert isinstance(func.type, FunctionLike)
        return func.type
    else:
        # Implicit type signature with dynamic types.
        # Overloaded functions always have a signature, so func must be an ordinary function.
        assert isinstance(func, mypy.nodes.FuncItem), str(func)
        return callable_type(func, fallback)


def callable_type(fdef: mypy.nodes.FuncItem, fallback: Instance,
                  ret_type: Optional[Type] = None) -> CallableType:
    name = fdef.name()
    if name:
        name = '"{}"'.format(name)

    return CallableType(
        [AnyType(TypeOfAny.unannotated)] * len(fdef.arg_names),
        fdef.arg_kinds,
        [None if argument_elide_name(n) else n for n in fdef.arg_names],
        ret_type or AnyType(TypeOfAny.unannotated),
        fallback,
        name,
        implicit=True,
    )


def get_typ_args(tp: Type) -> List[Type]:
    """Get all type arguments from a parameterizable Type."""
    if not isinstance(tp, (Instance, UnionType, TupleType, CallableType)):
        return []
    typ_args = (tp.args if isinstance(tp, Instance) else
                tp.items if not isinstance(tp, CallableType) else
                tp.arg_types + [tp.ret_type])
    return typ_args


def set_typ_args(tp: Type, new_args: List[Type], line: int = -1, column: int = -1) -> Type:
    """Return a copy of a parameterizable Type with arguments set to new_args."""
    if isinstance(tp, Instance):
        return Instance(tp.type, new_args, line, column)
    if isinstance(tp, TupleType):
        return tp.copy_modified(items=new_args)
    if isinstance(tp, UnionType):
        return UnionType(new_args, line, column)
    if isinstance(tp, CallableType):
        return tp.copy_modified(arg_types=new_args[:-1], ret_type=new_args[-1],
                                line=line, column=column)
    return tp


def get_type_vars(typ: Type) -> List[TypeVarType]:
    """Get all type variables that are present in an already analyzed type,
    without duplicates, in order of textual appearance.
    Similar to TypeAnalyser.get_type_var_names.
    """
    all_vars = []  # type: List[TypeVarType]
    for t in get_typ_args(typ):
        if isinstance(t, TypeVarType):
            all_vars.append(t)
        else:
            all_vars.extend(get_type_vars(t))
    # Remove duplicates while preserving order
    included = set()  # type: Set[TypeVarId]
    tvars = []
    for var in all_vars:
        if var.id not in included:
            tvars.append(var)
            included.add(var.id)
    return tvars


def flatten_nested_unions(types: Iterable[Type]) -> List[Type]:
    """Flatten nested unions in a type list."""
    flat_items = []  # type: List[Type]
    for tp in types:
        if isinstance(tp, UnionType):
            flat_items.extend(flatten_nested_unions(tp.items))
        else:
            flat_items.append(tp)
    return flat_items


def union_items(typ: Type) -> List[Type]:
    """Return the flattened items of a union type.

    For non-union types, return a list containing just the argument.
    """
    if isinstance(typ, UnionType):
        items = []
        for item in typ.items:
            items.extend(union_items(item))
        return items
    else:
        return [typ]


names = globals().copy()
names.pop('NOT_READY', None)
deserialize_map = {
    key: obj.deserialize  # type: ignore
    for key, obj in names.items()
    if isinstance(obj, type) and issubclass(obj, Type) and obj is not Type
}
