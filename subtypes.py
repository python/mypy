from mtypes import (
    Typ, Any, UnboundType, TypeVisitor, ErrorType, Void, NoneTyp, Instance,
    TypeVar, Callable, TupleType, Overloaded
)
from nodes import TypeInfo
from expandtype import expand_type


bool is_subtype(Typ left, Typ right):
    """Is 'left' subtype of 'right'?"""
    if isinstance(right, Any) or isinstance(right, UnboundType):
        return True
    else:
        return left.accept(SubtypeVisitor(right))


bool is_equivalent(Typ a, Typ b):
    return is_subtype(a, b) and is_subtype(b, a)


class SubtypeVisitor(TypeVisitor<bool>):
    void __init__(self, Typ right):
        self.right = right
    
    # visit_x(left) means: is left (which is an instance of X) a subtype of
    # right?
    
    bool visit_unbound_type(self, UnboundType left):
        return True
    
    bool visit_error_type(self, ErrorType left):
        return False
    
    bool visit_any(self, Any left):
        return True
    
    bool visit_void(self, Void left):
        return isinstance(self.right, Void)
    
    bool visit_none_type(self, NoneTyp left):
        return not isinstance(self.right, Void)
    
    bool visit_instance(self, Instance left):
        if isinstance(self.right, Instance):
            right = (Instance)self.right
            rname = right.typ.full_name()
            if not left.typ.has_base(rname) and rname != 'builtins.object':
                return False
            
            # Map left type to corresponding right instances.
            t = map_instance_to_supertype(left, right.typ)
            result = True
            for i in range(len(right.args)):
                if not is_equivalent(t.args[i], right.args[i]):
                    result = False
                    break
            return result
        else:
            return False
    
    bool visit_type_var(self, TypeVar left):
        if isinstance(self.right, TypeVar):
            tvar = (TypeVar)self.right
            return (left.name == tvar.name and
                    left.is_wrapper_var == tvar.is_wrapper_var)
        else:
            return is_named_instance(self.right, 'builtins.object')
    
    bool visit_callable(self, Callable left):
        if isinstance(self.right, Callable):
            return is_callable_subtype(left, (Callable)self.right)
        elif is_named_instance(self.right, 'builtins.object'):
            return True
        elif (is_named_instance(self.right, 'builtins.type') and
                  left.is_type_obj()):
            return True
        else:
            return False
    
    bool visit_tuple_type(self, TupleType left):
        if isinstance(self.right, Instance) and (
                is_named_instance(self.right, 'builtins.object') or
                is_named_instance(self.right, 'builtins.tuple')):
            return True
        elif isinstance(self.right, TupleType):
            tright = (TupleType)self.right
            if len(left.items) != len(tright.items):
                return False
            for i in range(len(left.items)):
                if not is_subtype(left.items[i], tright.items[i]):
                    return False
            return True
        else:
            return False
    
    bool visit_overloaded(self, Overloaded left):
        if is_named_instance(self.right, 'builtins.object'):
            return True
        elif isinstance(self.right, Callable) or is_named_instance(
                                                 self.right, 'builtins.type'):
            for item in left.items():
                if is_subtype(item, self.right):
                    return True
            return False
        elif isinstance(self.right, Overloaded):
            # TODO: this may be too restrictive
            oright = (Overloaded)self.right
            if len(left.items()) != len(oright.items()):
                return False
            for i in range(len(left.items())):
                if not is_subtype(left.items()[i], oright.items()[i]):
                    return False
            return True
        elif isinstance(self.right, UnboundType):
            return True
        else:
            return False


bool is_callable_subtype(Callable left, Callable right):
    # Subtyping is not currently supported for generic functions.
    if left.variables.items or right.variables.items:
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
        if not is_equivalent(right.arg_types[i], left.arg_types[i]):
            return False
    
    if right.is_var_arg and not left.is_var_arg:
        return False
    
    if (left.is_var_arg and not right.is_var_arg and
            len(left.arg_types) <= len(right.arg_types)):
        return False
    
    return True


Instance map_instance_to_supertype(Instance instance, TypeInfo supertype):
    """Map an Instance type, including the type arguments, to compatible
    Instance of a specific supertype.
    
    Assume that supertype is a supertype of instance.type.
    """
    if instance.typ == supertype:
        return instance
    
    # Strip type variables away if the supertype has none.
    if supertype.type_vars == []:
        return Instance(supertype, [])
    
    if supertype.is_interface:
        return map_instance_to_interface_supertypes(instance, supertype)[0]
    
    while True:
        instance = map_instance_to_direct_supertype(instance,
                                                    instance.typ.base)
        if instance.typ == supertype: break
    
    return instance


Instance map_instance_to_direct_supertype(Instance instance,
                                          TypeInfo supertype):
    typ = instance.typ
    
    for b in typ.bases:
        # The cast below cannot fail since we require that semantic analysis
        # was successful, so bases cannot contain unbound types.
        if b and ((Instance)b).typ == supertype:
            map = type_var_map(typ, instance.args)
            return (Instance)expand_type(b, map)
    
    # Relationship with the supertype not specified explicitly. Use dynamic
    # type arguments implicitly.
    return Instance(typ.base, <Typ> [Any()] * len(typ.base.type_vars))


dict<int, Typ> type_var_map(TypeInfo typ, Typ[] args):
    if not args:
        return None
    else:
        tvars = <int, Typ> {}
        for i in range(len(args)):
            tvars[i + 1] = args[i]
        return tvars


Instance[] map_instance_to_interface_supertypes(Instance instance,
                                                    TypeInfo supertype):
    # FIX: Currently we should only have one supertype per interface, so no
    #      need to return an array
    result = <Instance> []
    for path in interface_implementation_paths(instance.typ, supertype):
        types = [instance]
        for sup in path:
            a = <Instance> []
            for t in types:
                a.extend(map_instance_to_direct_supertypes(t, sup))
            types = a
        result.extend(types)
    return result


list<TypeInfo[]> interface_implementation_paths(TypeInfo typ,
                                                    TypeInfo supertype):
    """Return an array of non-empty paths of direct supertypes from
    type to supertype.  Return [] if no such path could be found.
    
      InterfaceImplementationPaths(A, B) == [[B]] if A inherits B
      InterfaceImplementationPaths(A, C) == [[B, C]] if A inherits B and
                                                        B inherits C
    """
    # FIX: Currently we might only ever have a single path, so this could be
    #      simplified
    list<TypeInfo[]> result = []
    
    if typ.base == supertype or supertype in typ.interfaces:
        # Direct supertype.
        result.append([supertype])
    
    # Try constructing a path via superclass.
    if typ.base:
        for path in interface_implementation_paths(typ.base, supertype):
            result.append([typ.base] + path)
    
    # Try constructing a path via each superinterface.
    if typ.interfaces:
        for iface in typ.interfaces:
            for path_ in interface_implementation_paths(iface, supertype):
                result.append([iface] + path_)
    
    return result


Instance[] map_instance_to_direct_supertypes(Instance instance,
                                                 TypeInfo supertype):
    # FIX: There should only be one supertypes, always.
    typ = instance.typ
    Instance[] result = []
    
    for b in typ.bases:
        # The cast below cannot fail since we require that semantic analysis
        # was successful, so bases cannot contain unbound types.
        if b and ((Instance)b).typ == supertype:
            map = type_var_map(typ, instance.args)
            result.append((Instance)expand_type(b, map))
    
    if result:
        return result
    else:
        # Relationship with the supertype not specified explicitly. Use dynamic
        # type arguments implicitly.
        return [Instance(supertype, <Typ> [Any()] * len(supertype.type_vars))]


bool is_named_instance(Typ t, str full_name):
    return isinstance(t,
                      Instance) and ((Instance)t).typ.full_name() == full_name
