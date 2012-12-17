from types import Typ
from nodes import TypeInfo
from semanal import self_type
from checker import map_instance_to_supertype


# Return types that represent values of type variable slots of a type in terms
# of type variables of the type.
#
# For example, assume these definitions:
#
#   class C<T, S> extends D<E<S>> ...
#   class D<S> extends Object ...
#
# Now slot mappings for C is [E<S>, T] (S and T refer to type variables of C).
list<Typ> compile_slot_mapping(TypeInfo typ):
    list<Typ> exprs = []
    
    for slot in range(num_slots(typ)):
        # Figure out the superclass which defines the slot; also figure out
        # the tvar index that maps to the slot.
        origin, tv = find_slot_origin(typ, slot)
        
        # Map self type to the superclass -> extract tvar with target index
        # (only contains subclass tvars?? PROBABLY NOT).
        self_type = self_type(typ)
        self_type = map_instance_to_supertype(self_type, origin)
        tvar = self_type.args[tv - 1]
        
        # tvar is the representation of the slot in terms of type arguments.
        exprs.append(tvar)
    
    return exprs


# Determine the class and the index of type variable in this class which is
# mapped directly to the given type variable slot.
#
# Examples:
#   - In "class C<T> ...", the type var 1 (T) in C is mapped to slot 0.
#   - In "class D<S, U> is C<U> ...", the type var 1 (S) in D is mapped to
#     slot 1; the type var 1 (T) in C is mapped to slot 0.
tuple<TypeInfo, int> find_slot_origin(TypeInfo info, int slot):
    base = info.base
    super_slots = num_slots(base)
    if slot < super_slots:
        # A superclass introduced the slot.
        return find_slot_origin(base, slot)
    else:
        # This class introduced the slot. Figure out which type variable maps
        # to the slot.
        for tv in range(1, len(info.type_vars) + 1):
            if get_tvar_access_path(info, tv)[0] - 1 == slot:
                return (info, tv)
        
        raise RuntimeError('Could not map slot')
