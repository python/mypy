from typing import cast, List, Dict

from mypy.types import (
    Type, AnyType, UnboundType, TypeVisitor, ErrorType, Void, NoneTyp,
    Instance, TypeVar, Callable, TupleType, Overloaded, ErasedType, TypeList
)
from mypy import sametypes
from mypy.nodes import TypeInfo
from mypy.expandtype import expand_type


def is_subtype(left: Type, right: Type) -> bool:
    """Is 'left' subtype of 'right'?

    Also consider Any to be a subtype of any type, and vice versa. This
    recursively applies to components of composite types (List[int] is subtype
    of List[Any], for example).
    """
    if (isinstance(right, AnyType) or isinstance(right, UnboundType)
            or isinstance(right, ErasedType)):
        return True
    else:
        return left.accept(SubtypeVisitor(right))


def is_equivalent(a: Type, b: Type) -> bool:
    return is_subtype(a, b) and is_subtype(b, a)


class SubtypeVisitor(TypeVisitor[bool]):
    def __init__(self, right: Type) -> None:
        self.right = right
    
    # visit_x(left) means: is left (which is an instance of X) a subtype of
    # right?
    
    def visit_unbound_type(self, left: UnboundType) -> bool:
        return True
    
    def visit_error_type(self, left: ErrorType) -> bool:
        return False
    
    def visit_type_list(self, t: TypeList) -> bool:
        assert False, 'Not supported'
    
    def visit_any(self, left: AnyType) -> bool:
        return True
    
    def visit_void(self, left: Void) -> bool:
        return isinstance(self.right, Void)
    
    def visit_none_type(self, left: NoneTyp) -> bool:
        return not isinstance(self.right, Void)
    
    def visit_erased_type(self, left: ErasedType) -> bool:
        return True
    
    def visit_instance(self, left: Instance) -> bool:
        right = self.right
        if isinstance(right, Instance):
            if left.type.ducktype and is_subtype(left.type.ducktype,
                                                 self.right):
                return True
            rname = right.type.fullname()
            if not left.type.has_base(rname) and rname != 'builtins.object':
                return False
            
            # Map left type to corresponding right instances.
            t = map_instance_to_supertype(left, right.type)
            result = True
            for i in range(len(right.args)):
                if not is_equivalent(t.args[i], right.args[i]):
                    result = False
                    break
            return result
        else:
            return False
    
    def visit_type_var(self, left: TypeVar) -> bool:
        right = self.right
        if isinstance(right, TypeVar):
            return (left.name == right.name and
                    left.is_wrapper_var == right.is_wrapper_var)
        else:
            return is_named_instance(self.right, 'builtins.object')
    
    def visit_callable(self, left: Callable) -> bool:
        right = self.right
        if isinstance(right, Callable):
            return is_callable_subtype(left, right)
        elif isinstance(right, Overloaded):
            return all(is_subtype(left, item) for item in right.items())
        elif is_named_instance(right, 'builtins.object'):
            return True
        elif (is_named_instance(right, 'builtins.type') and
                  left.is_type_obj()):
            return True
        else:
            return False
    
    def visit_tuple_type(self, left: TupleType) -> bool:
        right = self.right
        if isinstance(right, Instance) and (
                is_named_instance(right, 'builtins.object') or
                is_named_instance(right, 'builtins.tuple')):
            return True
        elif isinstance(right, TupleType):
            if len(left.items) != len(right.items):
                return False
            for i in range(len(left.items)):
                if not is_subtype(left.items[i], right.items[i]):
                    return False
            return True
        else:
            return False
    
    def visit_overloaded(self, left: Overloaded) -> bool:
        right = self.right
        if is_named_instance(right, 'builtins.object'):
            return True
        elif isinstance(right, Callable) or is_named_instance(
                                                 right, 'builtins.type'):
            for item in left.items():
                if is_subtype(item, right):
                    return True
            return False
        elif isinstance(right, Overloaded):
            # TODO: this may be too restrictive
            if len(left.items()) != len(right.items()):
                return False
            for i in range(len(left.items())):
                if not is_subtype(left.items()[i], right.items()[i]):
                    return False
            return True
        elif isinstance(right, UnboundType):
            return True
        else:
            return False


def is_callable_subtype(left: Callable, right: Callable) -> bool:
    # TODO support named arguments, **args etc.
    
    # Subtyping is not currently supported for generic functions.
    if left.variables or right.variables:
        return False
    
    # Non-type cannot be a subtype of type.
    if right.is_type_obj() and not left.is_type_obj():
        return False
    
    # Check return types.
    if not is_subtype(left.ret_type, right.ret_type):
        return False
    
    if len(left.arg_types) < len(right.arg_types):
        return False
    if left.min_args > right.min_args:
        return False
    for i in range(len(right.arg_types)):
        if not is_subtype(right.arg_types[i], left.arg_types[i]):
            return False
    
    if right.is_var_arg and not left.is_var_arg:
        return False
    
    if (left.is_var_arg and not right.is_var_arg and
            len(left.arg_types) <= len(right.arg_types)):
        return False
    
    return True


def map_instance_to_supertype(instance: Instance,
                              supertype: TypeInfo) -> Instance:
    """Map an Instance type, including the type arguments, to compatible
    Instance of a specific supertype.
    
    Assume that supertype is a supertype of instance.type.
    """
    if instance.type == supertype:
        return instance
    
    # Strip type variables away if the supertype has none.
    if not supertype.type_vars:
        return Instance(supertype, [])
    
    return map_instance_to_supertypes(instance, supertype)[0]


def map_instance_to_direct_supertype(instance: Instance,
                                     supertype: TypeInfo) -> Instance:
    typ = instance.type
    
    for base in typ.bases:
        if base.type == supertype:
            map = type_var_map(typ, instance.args)
            return cast(Instance, expand_type(base, map))
    
    # Relationship with the supertype not specified explicitly. Use AnyType
    # type arguments implicitly.
    # TODO Should this be an error instead?
    return Instance(supertype, [AnyType()] * len(supertype.type_vars))


def type_var_map(typ: TypeInfo, args: List[Type]) -> Dict[int, Type]:
    if not args:
        return None
    else:
        tvars = {} # type: Dict[int, Type]
        for i in range(len(args)):
            tvars[i + 1] = args[i]
        return tvars


def map_instance_to_supertypes(instance: Instance,
                               supertype: TypeInfo) -> List[Instance]:
    # FIX: Currently we should only have one supertype per interface, so no
    #      need to return an array
    result = [] # type: List[Instance]
    for path in class_derivation_paths(instance.type, supertype):
        types = [instance]
        for sup in path:
            a = [] # type: List[Instance]
            for t in types:
                a.extend(map_instance_to_direct_supertypes(t, sup))
            types = a
        result.extend(types)
    return result


def class_derivation_paths(typ: TypeInfo,
                           supertype: TypeInfo) -> List[List[TypeInfo]]:
    """Return an array of non-empty paths of direct base classes from
    type to supertype.  Return [] if no such path could be found.
    
      InterfaceImplementationPaths(A, B) == [[B]] if A inherits B
      InterfaceImplementationPaths(A, C) == [[B, C]] if A inherits B and
                                                        B inherits C
    """
    # FIX: Currently we might only ever have a single path, so this could be
    #      simplified
    result = [] # type: List[List[TypeInfo]]

    for base in typ.bases:
        if base.type == supertype:
            result.append([base.type])
        else:
            # Try constructing a longer path via the base class.
            for path in class_derivation_paths(base.type, supertype):
                result.append([base.type] + path)

    return result


def map_instance_to_direct_supertypes(instance: Instance,
                                      supertype: TypeInfo) -> List[Instance]:
    # FIX: There should only be one supertypes, always.
    typ = instance.type
    result = [] # type: List[Instance]
    
    for b in typ.bases:
        if b.type == supertype:
            map = type_var_map(typ, instance.args)
            result.append(cast(Instance, expand_type(b, map)))
    
    if result:
        return result
    else:
        # Relationship with the supertype not specified explicitly. Use dynamic
        # type arguments implicitly.
        return [Instance(supertype, [AnyType()] * len(supertype.type_vars))]


def is_named_instance(t: Type, fullname: str) -> bool:
    return (isinstance(t, Instance) and
            cast(Instance, t).type.fullname() == fullname)


def is_proper_subtype(t, s):
    """Check if t is a proper subtype of s?

    For proper subtypes, there's no need to rely on compatibility due to
    Any types. Any instance type t is also a proper subtype of t.
    """
    # FIX support generic types, tuple types etc.
    return (isinstance(t, Instance) and isinstance(s, Instance)
            and t.args == [] and s.args == [] and is_subtype(t, s))


def is_more_precise(t: Type, s: Type) -> bool:
    """Check if t is a more precise type than s.

    A t is a proper subtype of s, t is also more precise than s. Also, if
    s is Any, t is more precise than s for any t. Finally, if t is the same
    type as s, t is more precise than s.
    """
    # TODO Should List[int] be more precise than List[Any]?
    if isinstance(s, AnyType):
        return True
    if isinstance(s, Instance):
        return is_proper_subtype(t, s)
    return sametypes.is_same_type(t, s)
