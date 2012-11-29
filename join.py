import checker
from mtypes import (
    Typ, Any, NoneTyp, Void, TypeVisitor, Instance, UnboundType, ErrorType,
    TypeVar, Callable, TupleType
)
from subtypes import is_subtype, is_equivalent, map_instance_to_supertype


Typ join_types(Typ s, Typ t, checker.BasicTypes basic):
    if isinstance(s, Any):
        return s
    
    if isinstance(s, NoneTyp) and not isinstance(t, Void):
        return t
    
    return t.accept(TypeJoinVisitor(s, basic))


class TypeJoinVisitor(TypeVisitor<Typ>):
    void __init__(self, Typ s, checker.BasicTypes basic):
        self.s = s
        self.basic = basic
        self.object = basic.object
    
    Typ visit_unbound_type(self, UnboundType t):
        if isinstance(self.s, Void) or isinstance(self.s, ErrorType):
            return ErrorType()
        else:
            return Any()
    
    Typ visit_error_type(self, ErrorType t):
        return t
    
    Typ visit_any(self, Any t):
        return t
    
    Typ visit_void(self, Void t):
        if isinstance(self.s, Void):
            return t
        else:
            return ErrorType()
    
    Typ visit_none_type(self, NoneTyp t):
        if not isinstance(self.s, Void):
            return self.s
        else:
            return self.default(self.s)
    
    Typ visit_type_var(self, TypeVar t):
        if isinstance(self.s, TypeVar) and ((TypeVar)self.s).id == t.id:
            return self.s
        else:
            return self.default(self.s)
    
    Typ visit_instance(self, Instance t):
        if isinstance(self.s, Instance):
            return join_instances(t, (Instance)self.s, True, self.basic)
        elif t.typ == self.basic.std_type.typ and is_subtype(self.s, t):
            return t
        else:
            return self.default(self.s)
    
    Typ visit_callable(self, Callable t):
        if isinstance(self.s, Callable) and is_similar_callables(
                                                    t, (Callable)self.s):
            return combine_similar_callables(t, (Callable)self.s, self.basic)
        elif t.is_type_obj() and is_subtype(self.s, self.basic.std_type):
            return self.basic.std_type
        elif (isinstance(self.s, Instance) and
                  ((Instance)self.s).typ == self.basic.std_type.typ and
                  t.is_type_obj()):
            return self.basic.std_type
        else:
            return self.default(self.s)
    
    Typ visit_tuple_type(self, TupleType t):
        if isinstance(self.s, TupleType) and (((TupleType)self.s).length() ==
                                              t.length()):
            Typ[] items = []
            for i in range(t.length()):
                items.append(self.join(t.items[i],
                                       ((TupleType)self.s).items[i]))
            return TupleType(items)
        else:
            return self.default(self.s)
    
    Typ join(self, Typ s, Typ t):
        return join_types(s, t, self.basic)
    
    Typ default(self, Typ typ):
        if isinstance(typ, UnboundType):
            return Any()
        elif isinstance(typ, Void) or isinstance(typ, ErrorType):
            return ErrorType()
        else:
            return self.object


Typ join_instances(Instance t, Instance s, bool allow_interfaces,
                   checker.BasicTypes basic):
    """Calculate the join of two instance types. If allow_interfaces is
    True, also consider interface-type results for non-interface
    types.
    
    Return ErrorType if the result is ambiguous.
    """
    if t.typ == s.typ:
        # Simplest case: join two types with the same base type (but
        # potentially different arguments).
        if is_subtype(t, s):
            # Compatible; combine type arguments.
            Typ[] args = []
            for i in range(len(t.args)):
                args.append(join_types(t.args[i], s.args[i], basic))
            return Instance(t.typ, args)
        else:
            # Incompatible; return trivial result object.
            return basic.object
    elif t.typ.is_interface != s.typ.is_interface:
        return join_instances_as_interface(t, s, basic)
    elif t.typ.base is not None and is_subtype(t, s):
        return join_instances_via_supertype(t, s, allow_interfaces, basic)
    elif s.typ.base is not None:
        return join_instances_via_supertype(s, t, allow_interfaces, basic)
    elif allow_interfaces and not t.typ.is_interface:
        return join_instances_as_interface(t, s, basic)
    else:
        return basic.object


Typ join_instances_via_supertype(Instance t, Instance s,
                                 bool allow_interfaces,
                                 checker.BasicTypes basic):
    res = s
    mapped = map_instance_to_supertype(t, t.typ.base)
    join = join_instances(mapped, res, False, basic)
    # If the join failed, fail. This is a defensive measure (this might
    # never happen).
    if isinstance(join, ErrorType):
        return join
    # Now the result must be an Instance, so the cast below cannot fail.
    res = (Instance)join
    
    if (res.typ == basic.object.typ and not t.typ.is_interface and
            allow_interfaces):
        return join_instances_as_interface(t, s, basic)
    else:
        return res


Typ join_instances_as_interface(Instance t, Instance s,
                                checker.BasicTypes basic):
    """Compute join of two instances with a preference to an interface
    type result.  Return Object if no common interface type is found
    and ErrorType if the result type is ambiguous.
    
    Interface type result is expected in the following cases:
     * exactly one of t or s is an interface type
     * neither t nor s is an interface type, and neither is subtype of the
       other
    """
    t_ifaces = implemented_interfaces(t)
    s_ifaces = implemented_interfaces(s)
    
    Instance[] res = []
    
    for ti in t_ifaces:
        for si in s_ifaces:
            # Join of two interface types is always an Instance type (either
            # another interface type or Object), so the cast below is safe.
            j = (Instance)join_types(ti, si, basic)
            if j.typ != basic.object.typ:
                res.append(j)
    
    if len(res) == 1:
        # Unambiguous, non-trivial result.
        return res[0]
    elif len(res) == 0:
        # Return the trivial result (Object).
        return basic.object
    else:
        # Two or more potential candidate results.
        
        # Calculate the join of the results. If it is Object, the result is
        # ambigous (ErrorType).
        j = res[0]
        for i in range(1, len(res)):
            # As above, the join of two interface types is always an Instance
            # type. The cast below is thus safe.
            j = (Instance)join_types(j, res[i], basic)
        if j.typ != basic.object.typ:
            return j
        else:
            return ErrorType()


Typ[] implemented_interfaces(Instance t):
    """If t is a class instance, return all the directly implemented interface
    types by t and its supertypes, including mapped type arguments.
    """
    if t.typ.is_interface:
        return [t]
    else:
        Typ[] res = []
        
        for iface in t.typ.interfaces:
            res.append(map_instance_to_supertype(t, iface))
        
        if t.typ.base is not None:
            tt = map_instance_to_supertype(t, t.typ.base)
            res.extend(implemented_interfaces(tt))
        
        return res


bool is_similar_callables(Callable t, Callable s):
    """Return True if t and s are equivalent and have identical numbers of
    arguments, default arguments and varargs.
    """
    return (len(t.arg_types) == len(s.arg_types) and t.min_args == s.min_args
            and t.is_var_arg == s.is_var_arg and is_equivalent(t, s))


Callable combine_similar_callables(Callable t, Callable s,
                                   checker.BasicTypes basic):
    Typ[] arg_types = []
    for i in range(len(t.arg_types)):
        arg_types.append(join_types(t.arg_types[i], s.arg_types[i], basic))
    # TODO kinds and argument names
    return Callable(arg_types,
                    t.arg_kinds,
                    t.arg_names,
                    join_types(t.ret_type, s.ret_type, basic),
                    t.is_type_obj() and s.is_type_obj(),
                    None,
                    t.variables)
    return s
