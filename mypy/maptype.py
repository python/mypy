from typing import Dict, List

from mypy.expandtype import expand_type
from mypy.typeinfo import TypeInfo
from mypy.types import Type, TypeVarId, Instance, AnyType


def map_instance_to_supertype(instance: Instance,
                              superclass: TypeInfo) -> Instance:
    """Produce a supertype of `instance` that is an Instance
    of `superclass`, mapping type arguments up the chain of bases.

    `superclass` is required to be a superclass of `instance.type`.
    """
    if instance.type == superclass:
        # Fast path: `instance` already belongs to `superclass`.
        return instance

    if not superclass.type_vars:
        # Fast path: `superclass` has no type variables to map to.
        return Instance(superclass, [])

    return map_instance_to_supertypes(instance, superclass)[0]


def map_instance_to_supertypes(instance: Instance,
                               supertype: TypeInfo) -> List[Instance]:
    # FIX: Currently we should only have one supertype per interface, so no
    #      need to return an array
    result = []  # type: List[Instance]
    typ = instance.type
    assert typ is not None, 'Instance.type is not fixed after deserialization'
    for path in class_derivation_paths(typ, supertype):
        types = [instance]
        for sup in path:
            a = []  # type: List[Instance]
            for t in types:
                a.extend(map_instance_to_direct_supertypes(t, sup))
            types = a
        result.extend(types)
    if result:
        return result
    else:
        # Nothing. Presumably due to an error. Construct a dummy using Any.
        return [Instance(supertype, [AnyType()] * len(supertype.type_vars))]


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
    result = []  # type: List[List[TypeInfo]]

    for base in typ.bases:
        btype = base.type
        assert btype is not None, 'Instance.type is not fixed after deserialization'
        if btype == supertype:
            result.append([btype])
        else:
            # Try constructing a longer path via the base class.
            for path in class_derivation_paths(btype, supertype):
                result.append([btype] + path)

    return result


def map_instance_to_direct_supertypes(instance: Instance,
                                      supertype: TypeInfo) -> List[Instance]:
    # FIX: There should only be one supertypes, always.
    typ = instance.type
    assert typ is not None, 'Instance.type is not fixed after deserialization'
    result = []  # type: List[Instance]

    for b in typ.bases:
        if b.type == supertype:
            env = instance_to_type_environment(instance)
            t = expand_type(b, env)
            assert isinstance(t, Instance)
            result.append(t)

    if result:
        return result
    else:
        # Relationship with the supertype not specified explicitly. Use dynamic
        # type arguments implicitly.
        return [Instance(supertype, [AnyType()] * len(supertype.type_vars))]


def instance_to_type_environment(instance: Instance) -> Dict[TypeVarId, Type]:
    """Given an Instance, produce the resulting type environment for type
    variables bound by the Instance's class definition.

    An Instance is a type application of a class (a TypeInfo) to its
    required number of type arguments.  So this environment consists
    of the class's type variables mapped to the Instance's actual
    arguments.  The type variables are mapped by their `id`.

    """
    typ = instance.type
    assert typ is not None, 'Instance.type is not fixed after deserialization'
    return {binder.id: arg for binder, arg in zip(typ.defn.type_vars, instance.args)}
