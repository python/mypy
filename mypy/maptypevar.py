from mypy.types import RuntimeTypeVar, OBJECT_VAR, Instance, Type, TypeVar
from mypy.nodes import TypeInfo, Node, MemberExpr, IndexExpr, IntExpr
from mypy.transutil import self_expr, tvar_slot_name


RuntimeTypeVar get_tvar_access_expression(TypeInfo typ, int tvindex, any alt,
                                          any is_java):
    """Return a type expression that maps from runtime type variable slots
    to the type variable in the given class with the given index.
    
    For example, assume class A<T, S>: ... and class B<U>(A<X, Y<U>>): ...:
    
      get_tvar_access_expression(<B>, 1) ==
        RuntimeTypeVar(<self.__tv2.args[0]>)  (with <...> represented as nodes)
    """
    # First get the description of how to get from supertype type variables to
    # a subtype type variable.
    mapping = get_tvar_access_path(typ, tvindex)
    
    # The type checker should have noticed if there is no mapping. Be defensive
    # and make sure there is one.
    if mapping is None:
        raise RuntimeError('Could not find a typevar mapping')
    
    # Build the expression for getting at the subtype type variable
    # progressively.
    
    # First read the value of a supertype runtime type variable slot.
    Node s = self_expr()
    if alt == OBJECT_VAR:
        o = '__o'
        if is_java:
            o = '__o_{}'.format(typ.name)
        s = MemberExpr(s, o)
    Node expr = MemberExpr(s, tvar_slot_name(mapping[0] - 1, alt))
    
    # Then, optionally look into arguments based on the description.
    for i in mapping[1:]:
        expr = MemberExpr(expr, 'args')
        expr = IndexExpr(expr, IntExpr(i - 1))
    
    # Than add a final wrapper so that we have a valid type.
    return RuntimeTypeVar(expr)


int[] get_tvar_access_path(TypeInfo typ, int tvindex):
    """Determine how to calculate the value of a type variable of a type.
    
    The description is based on operations on type variable slot values
    embedded in an instance. The type variable and slot indexing is 1-based.
    
     - If tvar slot x maps directly to tvar tvindex in the type, return [x].
     - If argument y of slot x maps to tvar tvindex, return [x, y]. For
       argument z of argument y of x return [x, y, z], etc.
     - If there is no relation, return None.
    
    For example, assume these definitions:
    
      class A<S, U>: ...
      class B<T>(A<X, Y<T>>): ...
    
    Now we can query the access path to type variable 1 (T) of B:
    
      get_tvar_access_path(<B>, 1) == [2, 1] (slot 2, lookup type argument 1).
    """
    if not typ.bases:
        return None
    
    # Check argument range.
    if tvindex < 1 or tvindex > len(typ.type_vars):
        raise RuntimeError('{} does not have tvar #{}'.format(typ.name,
                                                              tvindex))
    
    # Figure out the superclass instance type.
    base = typ.bases[0]
    
    # Go through all the supertype tvars to find a match.
    int[] mapping = None
    for i in range(len(base.args)):
        mapping = find_tvar_mapping(base.args[i], tvindex)
        if mapping is not None:
            if base.type.bases[0]:
                return get_tvar_access_path(base.type, i + 1) + mapping
            else:
                return [i + 1] + mapping
    
    # The type variable was introduced in this type.
    return [tvar_slot_index(typ, tvindex)]


int[] find_tvar_mapping(Type t, int index):
    """Recursively search for a type variable instance (with given index)
    within the type t, which represents a supertype definition. Return the
    path to the first found instance.
    
     - If t is a bare type variable with correct index, return [] as the path.
     - If type variable is within instance arguments, return the indexing
       operations required to get it.
     - If no result could be found, return None.
    
    Examples:
      find_tvar_mapping(T`1, 1) == []
      find_tvar_mapping(A<X, Y, T`1>, 1) == [2]
      find_tvar_mapping(A<B<X, T`2>, T`1>, 2) == [0, 1]
      find_tvar_mapping(A<T`2>, T`1) == None               (no T`1 within t)
      find_tvar_mapping(A<T`1, T`1>, T`1) == [0]           (first match)
    """
    if isinstance(t, Instance) and ((Instance)t).args != []:
        inst = (Instance)t
        for argi in range(len(inst.args)):
            mapping = find_tvar_mapping(inst.args[argi], index)
            if mapping is not None:
                return get_tvar_access_path(inst.type, argi + 1) + mapping
        return None
    elif isinstance(t, TypeVar) and ((TypeVar)t).id == index:
        return []
    else:
        return None


int tvar_slot_index(TypeInfo typ, int tvindex):
    """If the specified type variable was introduced as a new variable in type,
    return the slot index (1 = first type varible slot) of the type variable.
    """
    base_slots = num_slots(typ.bases[0].type)
    
    for i in range(1, tvindex):
        if get_tvar_access_path(typ, i)[0] > base_slots:
            base_slots += 1
    
    return base_slots + 1  


int num_slots(TypeInfo typ):
    """Return the number of type variable slots used by a type.

    If type is None, the result is 0.
    """
    if not typ:
        return 0
    slots = num_slots(typ.bases[0].type)
    ntv = len(typ.type_vars)
    for i in range(ntv):
        n = get_tvar_access_path(typ, i + 1)[0]
        slots = max(slots, n)
    return slots
