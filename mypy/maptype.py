from typing import Dict, List, cast

from mypy.expandtype import expand_type
from mypy.nodes import TypeInfo
from mypy.types import Type, Instance, AnyType


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
        tvars = {}  # type: Dict[int, Type]
        for i in range(len(args)):
            tvars[i + 1] = args[i]
        return tvars


def map_instance_to_supertypes(instance: Instance,
                               supertype: TypeInfo) -> List[Instance]:
    # FIX: Currently we should only have one supertype per interface, so no
    #      need to return an array
    result = []  # type: List[Instance]
    for path in class_derivation_paths(instance.type, supertype):
        types = [instance]
        for sup in path:
            a = []  # type: List[Instance]
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
    result = []  # type: List[List[TypeInfo]]

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
    result = []  # type: List[Instance]

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
