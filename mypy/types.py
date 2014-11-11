"""Classes for representing mypy types."""

from abc import abstractmethod
from typing import Undefined, Any, typevar, List, Tuple, cast, Generic, Set

import mypy.nodes


T = typevar('T')


class Type(mypy.nodes.Context):
    """Abstract base class for all types."""

    line = 0
    repr = Undefined(Any)

    def __init__(self, line: int = -1, repr=None) -> None:
        self.line = line
        self.repr = repr

    def get_line(self) -> int:
        return self.line

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        raise RuntimeError('Not implemented')

    def __repr__(self) -> str:
        return self.accept(TypeStrVisitor())


class TypeVarDef(mypy.nodes.Context):
    """Definition of a single type variable."""

    name = ''
    id = 0
    values = Undefined(List[Type])
    upper_bound = Undefined(Type)
    line = 0
    repr = Undefined(Any)

    def __init__(self, name: str, id: int, values: List[Type], upper_bound: Type, line: int = -1,
                 repr: Any = None) -> None:
        self.name = name
        self.id = id
        self.values = values
        self.upper_bound = upper_bound
        self.line = line
        self.repr = repr

    def get_line(self) -> int:
        return self.line

    def __repr__(self) -> str:
        if self.values:
            return '{} in {}'.format(self.name, tuple(self.values))
        else:
            return self.name


class UnboundType(Type):
    """Instance type that has not been bound during semantic analysis."""

    name = ''
    args = Undefined(List[Type])

    def __init__(self, name: str, args: List[Type] = None, line: int = -1,
                 repr: Any = None) -> None:
        if not args:
            args = []
        self.name = name
        self.args = args
        super().__init__(line, repr)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_unbound_type(self)


class ErrorType(Type):
    """The error type is used as the result of failed type operations."""

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_error_type(self)


class TypeList(Type):
    """A list of types [...].

    This is only used for the arguments of a Function type, i.e. for
    [arg, ...] in Function[[arg, ...], ret].
    """

    items = Undefined(List[Type])

    def __init__(self, items: List[Type], line: int = -1,
                 repr: Any = None) -> None:
        super().__init__(line, repr)
        self.items = items

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_type_list(self)


class AnyType(Type):
    """The type 'Any'."""

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_any(self)


class Void(Type):
    """The return type 'None'.

    This can only be used as the return type in a callable type and as
    the result type of calling such callable.
    """

    source = ''   # May be None; function that generated this value

    def __init__(self, source: str = None, line: int = -1,
                 repr: Any = None) -> None:
        self.source = source
        super().__init__(line, repr)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_void(self)

    def with_source(self, source: str) -> 'Void':
        return Void(source, self.line, self.repr)


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

    def __init__(self, line: int = -1, repr=None) -> None:
        super().__init__(line, repr)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_none_type(self)


class ErasedType(Type):
    """Placeholder for an erased type.

    This is used during type inference. This has the special property that
    it is ignored during type inference.
    """

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_erased_type(self)


class Instance(Type):
    """An instance type of form C[T1, ..., Tn].

    The list of type variables may be empty.
    """

    type = Undefined(mypy.nodes.TypeInfo)
    args = Undefined(List[Type])
    erased = False      # True if result of type variable substitution

    def __init__(self, typ: mypy.nodes.TypeInfo, args: List[Type],
                 line: int = -1, repr: Any = None,
                 erased: Any = False) -> None:
        self.type = typ
        self.args = args
        self.erased = erased
        super().__init__(line, repr)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_instance(self)


class TypeVar(Type):
    """A type variable type.

    This refers to either a class type variable (id > 0) or a function
    type variable (id < 0).
    """

    name = ''  # Name of the type variable (for messages and debugging)
    id = 0     # 1, 2, ... for type-related, -1, ... for function-related
    values = Undefined(List[Type])  # Value restriction, empty list if no restriction
    upper_bound = Undefined(Type)   # Upper bound for values (currently always 'object')

    def __init__(self, name: str, id: int, values: List[Type], upper_bound: Type,
                 line: int = -1, repr: Any = None) -> None:
        self.name = name
        self.id = id
        self.values = values
        self.upper_bound = upper_bound
        super().__init__(line, repr)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_type_var(self)


class FunctionLike(Type):
    """Abstract base class for function types."""

    @abstractmethod
    def is_type_obj(self) -> bool: pass

    @abstractmethod
    def type_object(self) -> mypy.nodes.TypeInfo: pass

    @abstractmethod
    def items(self) -> List['Callable']: pass

    @abstractmethod
    def with_name(self, name: str) -> 'FunctionLike': pass

    # Corresponding instance type (e.g. builtins.type)
    fallback = Undefined(Instance)


class Callable(FunctionLike):
    """Type of a non-overloaded callable object (function)."""

    arg_types = Undefined(List[Type])  # Types of function arguments
    arg_kinds = Undefined(List[int])   # mypy.nodes.ARG_ constants
    arg_names = Undefined(List[str])   # None if not a keyword argument
    min_args = 0                    # Minimum number of arguments
    is_var_arg = False              # Is it a varargs function?
    ret_type = Undefined(Type)      # Return value type
    name = ''                       # Name (may be None; for error messages)
    # Type variables for a generic function
    variables = Undefined(List[TypeVarDef])

    # Implicit bound values of type variables. These can be either for
    # class type variables or for generic function type variables.
    # For example, the method 'append' of List[int] has implicit value
    # 'int' for the list type variable; the explicit method type is
    # just 'def append(int) -> None', without any type variable. Implicit
    # values are needed for runtime type checking, but they do not
    # affect static type checking.
    #
    # All class type arguments must be stored first, ordered by id,
    # and function type arguments must be stored next, again ordered by id
    # (absolute value this time).
    #
    # Stored as tuples (id, type).
    bound_vars = Undefined(List[Tuple[int, Type]])

    _is_type_obj = False  # Does this represent a type object?

    def __init__(self, arg_types: List[Type],
                 arg_kinds: List[int],
                 arg_names: List[str],
                 ret_type: Type,
                 fallback: Instance,
                 name: str = None, variables: List[TypeVarDef] = None,
                 bound_vars: List[Tuple[int, Type]] = None,
                 line: int = -1, repr: Any = None) -> None:
        if variables is None:
            variables = []
        if not bound_vars:
            bound_vars = []
        self.arg_types = arg_types
        self.arg_kinds = arg_kinds
        self.arg_names = arg_names
        self.min_args = arg_kinds.count(mypy.nodes.ARG_POS)
        self.is_var_arg = mypy.nodes.ARG_STAR in arg_kinds
        self.ret_type = ret_type
        self.fallback = fallback
        assert not name or '<bound method' not in name
        self.name = name
        self.variables = variables
        self.bound_vars = bound_vars
        super().__init__(line, repr)

    def is_type_obj(self) -> bool:
        return self.fallback.type.fullname() == 'builtins.type'

    def type_object(self) -> mypy.nodes.TypeInfo:
        assert self.is_type_obj()
        return cast(Instance, self.ret_type).type

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_callable(self)

    def with_name(self, name: str) -> 'Callable':
        """Return a copy of this type with the specified name."""
        ret = self.ret_type
        if isinstance(ret, Void):
            ret = ret.with_source(name)
        return Callable(self.arg_types,
                        self.arg_kinds,
                        self.arg_names,
                        ret,
                        self.fallback,
                        name,
                        self.variables,
                        self.bound_vars,
                        self.line, self.repr)

    def max_fixed_args(self) -> int:
        n = len(self.arg_types)
        if self.is_var_arg:
            n -= 1
        return n

    def items(self) -> List['Callable']:
        return [self]

    def is_generic(self) -> bool:
        return bool(self.variables)

    def type_var_ids(self) -> List[int]:
        a = List[int]()
        for tv in self.variables:
            a.append(tv.id)
        return a


class Overloaded(FunctionLike):
    """Overloaded function type T1, ... Tn, where each Ti is Callable.

    The variant to call is chosen based on runtime argument types; the first
    matching signature is the target.
    """

    _items = Undefined(List[Callable])  # Must not be empty

    def __init__(self, items: List[Callable]) -> None:
        self._items = items
        self.fallback = items[0].fallback
        super().__init__(items[0].line, None)

    def items(self) -> List[Callable]:
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
        ni = List[Callable]()
        for it in self._items:
            ni.append(it.with_name(name))
        return Overloaded(ni)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_overloaded(self)


class TupleType(Type):
    """The tuple type Tuple[T1, ..., Tn] (at least one type argument).

    Instance variables:
      items -- tuple item types
      fallback -- the underlying instance type that is used for non-tuple methods
        (this is currently always builtins.tuple, but it could be different for named
        tuples, for example)
    """

    items = Undefined(List[Type])
    fallback = Undefined(Instance)

    def __init__(self, items: List[Type], fallback: Instance, line: int = -1,
                 repr: Any = None) -> None:
        self.items = items
        self.fallback = fallback
        super().__init__(line, repr)

    def length(self) -> int:
        return len(self.items)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_tuple_type(self)


class UnionType(Type):
    """The union type Union[T1, ..., Tn] (at least one type argument)."""

    items = Undefined(List[Type])

    def __init__(self, items: List[Type], line: int = -1,
                 repr: Any = None) -> None:
        self.items = items
        super().__init__(line, repr)

    @staticmethod
    def make_union(items: List[Type], line: int = -1, repr: Any = None) -> Type:
        if len(items) > 1:
            return UnionType(items, line, repr)
        elif len(items) == 1:
            return items[0]
        else:
            return Void()

    @staticmethod
    def make_simplified_union(items: List[Type], line: int = -1, repr: Any = None) -> Type:
        while any(isinstance(typ, UnionType) for typ in items):
            all_items = []  # type: List[Type]
            for typ in items:
                if isinstance(typ, UnionType):
                    all_items.extend(typ.items)
                else:
                    all_items.append(typ)
            items = all_items

        from mypy.subtypes import is_subtype
        removed = Set[int]()
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

    def has_readable_member(self, name):
        """For a tree of unions of instances, check whether all
        instances have a given member.

        This should probably be refactored to go elsewhere."""
        return all(isinstance(x, UnionType) and x.has_readable_member(name) or
                   isinstance(x, Instance) and
                   x.type.has_readable_member(name)
                   for x in self.items)


class RuntimeTypeVar(Type):
    """Reference to a runtime variable with the value of a type variable.

    The reference can must be a expression node, but only some node
    types are properly supported (NameExpr, MemberExpr and IndexExpr
    mainly).
    """

    node = Undefined(mypy.nodes.Node)

    def __init__(self, node: mypy.nodes.Node) -> None:
        self.node = node
        super().__init__(-1, None)

    def accept(self, visitor: 'TypeVisitor[T]') -> T:
        return visitor.visit_runtime_type_var(self)


#
# Visitor-related classes
#


class TypeVisitor(Generic[T]):
    """Visitor class for types (Type subclasses).

    The parameter T is the return type of the visit methods.
    """

    def visit_unbound_type(self, t: UnboundType) -> T:
        pass

    def visit_type_list(self, t: TypeList) -> T:
        pass

    def visit_error_type(self, t: ErrorType) -> T:
        pass

    def visit_any(self, t: AnyType) -> T:
        pass

    def visit_void(self, t: Void) -> T:
        pass

    def visit_none_type(self, t: NoneTyp) -> T:
        pass

    def visit_erased_type(self, t: ErasedType) -> T:
        pass

    def visit_type_var(self, t: TypeVar) -> T:
        pass

    def visit_instance(self, t: Instance) -> T:
        pass

    def visit_callable(self, t: Callable) -> T:
        pass

    def visit_overloaded(self, t: Overloaded) -> T:
        pass

    def visit_tuple_type(self, t: TupleType) -> T:
        pass

    def visit_union_type(self, t: UnionType) -> T:
        assert(0)               # XXX catch visitors that don't have Union cases yet

    def visit_runtime_type_var(self, t: RuntimeTypeVar) -> T:
        pass


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

    def visit_instance(self, t: Instance) -> Type:
        return Instance(t.type, self.translate_types(t.args), t.line, t.repr)

    def visit_type_var(self, t: TypeVar) -> Type:
        return t

    def visit_callable(self, t: Callable) -> Type:
        return Callable(self.translate_types(t.arg_types),
                        t.arg_kinds,
                        t.arg_names,
                        t.ret_type.accept(self),
                        t.fallback,
                        t.name,
                        self.translate_variables(t.variables),
                        self.translate_bound_vars(t.bound_vars),
                        t.line, t.repr)

    def visit_tuple_type(self, t: TupleType) -> Type:
        return TupleType(self.translate_types(t.items),
                         Any(t.fallback.accept(self)),
                         t.line, t.repr)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.translate_types(t.items), t.line, t.repr)

    def translate_types(self, types: List[Type]) -> List[Type]:
        return [t.accept(self) for t in types]

    def translate_bound_vars(
            self, types: List[Tuple[int, Type]]) -> List[Tuple[int, Type]]:
        return [(id, t.accept(self)) for id, t in types]

    def translate_variables(self,
                            variables: List[TypeVarDef]) -> List[TypeVarDef]:
        return variables


class TypeStrVisitor(TypeVisitor[str]):
    """Visitor for pretty-printing types into strings.

    Do not preserve original formatting.

    Notes:
     - Include implicit bound type variables of callables.
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

    def visit_instance(self, t):
        s = t.type.fullname()
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

    def visit_callable(self, t):
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

        if t.bound_vars != []:
            # Include implicit bound type variables.
            a = []
            for i, bt in t.bound_vars:
                a.append('{}:{}'.format(i, bt))
            s = '[{}] {}'.format(', '.join(a), s)

        return 'def {}'.format(s)

    def visit_overloaded(self, t):
        a = []
        for i in t.items():
            a.append(i.accept(self))
        return 'Overload({})'.format(', '.join(a))

    def visit_tuple_type(self, t):
        s = self.list_str(t.items)
        return 'Tuple[{}]'.format(s)

    def visit_union_type(self, t):
        s = self.list_str(t.items)
        return 'Union[{}]'.format(s)

    def visit_runtime_type_var(self, t):
        return '<RuntimeTypeVar>'

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
    strategy = 0     # Strategy for combining multiple values

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

    def visit_type_var(self, t: TypeVar) -> bool:
        return self.default

    def visit_instance(self, t: Instance) -> bool:
        return self.query_types(t.args)

    def visit_callable(self, t: Callable) -> bool:
        # FIX generics
        return self.query_types(t.arg_types + [t.ret_type])

    def visit_tuple_type(self, t: TupleType) -> bool:
        return self.query_types(t.items)

    def visit_union_type(self, t: UnionType) -> bool:
        return self.query_types(t.items)

    def visit_runtime_type_var(self, t: RuntimeTypeVar) -> bool:
        return self.default

    def query_types(self, types: List[Type]) -> bool:
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

    if isinstance(typ, Callable):
        return Callable(typ.arg_types,
                        typ.arg_kinds,
                        typ.arg_names,
                        typ.ret_type,
                        typ.fallback,
                        None,
                        typ.variables)
    elif isinstance(typ, Overloaded):
        return Overloaded([cast(Callable, strip_type(item))
                           for item in typ.items()])
    else:
        return typ


def replace_leading_arg_type(t: Callable, self_type: Type) -> Callable:
    """Return a copy of a callable type with a different self argument type.

    Assume that the callable is the signature of a method.
    """
    return Callable([self_type] + t.arg_types[1:],
                    t.arg_kinds,
                    t.arg_names,
                    t.ret_type,
                    t.fallback,
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)


def is_named_instance(t: Type, fullname: str) -> bool:
    return (isinstance(t, Instance) and
            cast(Instance, t).type.fullname() == fullname)
