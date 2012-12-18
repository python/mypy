from mtypes import Typ
from nodes import TypeInfo
from semanal import self_type
from subtypes import map_instance_to_supertype
from maptypevar import num_slots, get_tvar_access_path


Typ[] compile_slot_mapping(TypeInfo typ):
    """Return types that represent values of type variable slots of a type.

    The returned types are in terms of type variables of the type.
    
    For example, assume these definitions:
    
    . class C<T, S>(D<E<S>>): ...
    . class D<S>(object): ...
    
    Now slot mappings for C is [E<S>, T] (S and T refer to type variables of
    C).
    """
    Typ[] exprs = []
    
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


tuple<TypeInfo, int> find_slot_origin(TypeInfo info, int slot):
    """Determine class and type variable index that directly maps to the slot.

    The result defines which class in inheritance hierarchy of info introduced
    the slot. All subclasses inherit this slot. The result TypeInfo always
    refers to one of the base classes of info (or info itself).

    Examples:
      - In 'class C<T>: ...', the slot 0 in C is mapped to type var 1 (T) in C.
      - In 'class D<S, U>(C<U>): ...', the slot 0 in D is mapped to type var
        1 (T) in C; the slot 1 of D is mapped to type variable 1 of D.
    """
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
