from nodes import TypeInfo
from mtypes import Instance, Typ, TypeVar
from transutil import self_expr


int[] get_tvar_access_path(TypeInfo typ, int tvindex):
    """Return a description of how to get to type variable value defined in a
    specific type from type variable slot values embedded in an instance. The
    indexing is 1-based.
    
     - If tvar slot x maps directly to tvar subtvindex in the type, return [x].
     - If argument y of x maps to tvar subtvindex, return [x, y]. For argument z
       of argument y of x return [x, y, z], etc.
     - If there is no relation, return nil.
    
    For example, assume these definitions:
    
      class A<S, U> ...
      class B<T> is A<X, Y<T>> ...
    
    Now we can query the access path to T (1) of B:
    
      GetTvarAccessPath(<B>, 1) == [2, 1]  (slot 2, lookup type argument 1).
      """
    if typ.base is None:
        return None
    
    # Check argument range.
    if tvindex < 1 or tvindex > len(typ.type_vars):
        raise RuntimeError('{} does not have tvar #{}'.format(typ.name, tvindex))
    
    # Figure out the superclass instance type.
    Instance base
    if typ.bases[0] is None:
        # Non-generic superclass.
        base = Instance(typ.base, [])
    else:
        # The cast will succeed if we get here.
        base = ((Instance)typ.bases[0])
    
    # Go through all the supertype tvars to find a match.
    int[] mapping = None
    for i in range(len(base.args)):
        mapping = find_tvar_mapping(base.args[i], tvindex)
        if mapping is not None:
            if base.typ.base is not None:
                return get_tvar_access_path(base.typ, i + 1) + mapping
            else:
                return [i + 1] + mapping
    
    # The type variable was introduced in this type.
    return [tvar_slot_index(typ, tvindex)]


int[] find_tvar_mapping(Typ t, int index):
    """Recursively search for a type variable instance (with given index) within
    the type t, which represents a supertype definition. Return the path to the
    first found instance.
    
     - If t is a bare type variable with correct index, return [] as the path.
     - If type variable is within instance arguments, return the indexing
       operations required to get it.
     - If no result could be found, return nil.
    
    Examples:
      FindTvarMapping(T`1, 1) == []
      FindTvarMapping(A<X, Y, T`1>, 1) == [2]
      FindTvarMapping(A<B<X, T`2>, T`1>, 2) == [0, 1]
      FindTvarMapping(A<T`2>, T`1) == nil               (no T`1 within t)
      FindTvarMapping(A<T`1, T`1>, T`1) == [0]          (first match)
      """
    if isinstance(t, Instance) and ((Instance)t).args != []:
        inst = (Instance)t
        for argi in range(len(inst.args)):
            mapping = find_tvar_mapping(inst.args[argi], index)
            if mapping is not None:
                return get_tvar_access_path(inst.typ, argi + 1) + mapping
        return None
    elif isinstance(t, TypeVar) and ((TypeVar)t).id == index:
        return []
    else:
        return None


int tvar_slot_index(TypeInfo typ, int tvindex):
    """If the specified type variable was introduced as a new variable in type,
    return the slot index (1 = first type varible slot) of the type variable.
    """
    base_slots = num_slots(typ.base)
    
    for i in range(1, tvindex):
        if get_tvar_access_path(typ, i)[0] > base_slots:
            base_slots += 1
    
    return base_slots + 1  


int num_slots(TypeInfo typ):
    """Return the number of type variable slots used by a type. If type == nil,
    the result is 0.
    """
    if typ is None:
        return 0
    slots = num_slots(typ.base)
    ntv = len(typ.type_vars)
    for i in range(ntv):
        n = get_tvar_access_path(typ, i + 1)[0]
        slots = max(slots, n)
    return slots
