from __future__ import annotations

from mypy.expandtype import expand_type, expand_type_by_instance
from mypy.nodes import TypeInfo
from mypy.types import AnyType, Instance, TupleType, Type, TypeOfAny, has_type_vars


def map_type_to_instance(typ: Type, target: Instance) -> Instance | None:
    """Attempt to map `typ` to an Instance of the same class as `target`

    Examples:
        (list[int], Iterable[T]) -> Iterable[int]
        (list[list[int]], Iterable[list[T]]) -> Iterable[list[int]]
        (dict[str, int], Mapping[K, int]) -> Mapping[str, int]
        (list[int], Mapping[K, V]) -> None

    Args:
        typ: The type to map from.
        target: The target instance type to map to.

    Returns:
        None: if the mapping is not possible.
        Instance: the mapped instance type if the mapping is possible.
    """
    from mypy.subtypes import is_subtype
    from mypy.typeops import get_all_type_vars

    # 1. get type vars of target
    tvars = get_all_type_vars(target)

    # fast path: if no type vars,
    if not tvars:
        return target if is_subtype(typ, target) else None

    from mypy.constraints import SUBTYPE_OF, SUPERTYPE_OF, Constraint, infer_constraints
    from mypy.solve import solve_constraints

    # 2. determine constraints
    constraints: list[Constraint] = infer_constraints(target, typ, SUPERTYPE_OF)
    for tvar in tvars:
        constraints.append(Constraint(tvar, SUBTYPE_OF, tvar.upper_bound))

    # 3. solve constraints
    solution, _ = solve_constraints(tvars, constraints)

    if None in solution:
        return None

    # 4. build resulting Instance by substituting typevars with solution
    env = {tvar.id: sol for tvar, sol in zip(tvars, solution)}
    target = expand_type(target, env)
    return target if is_subtype(typ, target) else None


def map_instance_to_supertype(instance: Instance, superclass: TypeInfo) -> Instance:
    """Produce a supertype of `instance` that is an Instance
    of `superclass`, mapping type arguments up the chain of bases.

    If `superclass` is not a nominal superclass of `instance.type`,
    then all type arguments are mapped to 'Any'.
    """
    if instance.type == superclass:
        # Fast path: `instance` already belongs to `superclass`.
        return instance

    if superclass.fullname == "builtins.tuple" and instance.type.tuple_type:
        if has_type_vars(instance.type.tuple_type):
            # We special case mapping generic tuple types to tuple base, because for
            # such tuples fallback can't be calculated before applying type arguments.
            alias = instance.type.special_alias
            assert alias is not None
            if not alias._is_recursive:
                # Unfortunately we can't support this for generic recursive tuples.
                # If we skip this special casing we will fall back to tuple[Any, ...].
                tuple_type = expand_type_by_instance(instance.type.tuple_type, instance)
                if isinstance(tuple_type, TupleType):
                    # Make the import here to avoid cyclic imports.
                    import mypy.typeops

                    return mypy.typeops.tuple_fallback(tuple_type)
                elif isinstance(tuple_type, Instance):
                    # This can happen after normalizing variadic tuples.
                    return tuple_type

    if not superclass.type_vars:
        # Fast path: `superclass` has no type variables to map to.
        return Instance(superclass, [])

    return map_instance_to_supertypes(instance, superclass)[0]


def map_instance_to_supertypes(instance: Instance, supertype: TypeInfo) -> list[Instance]:
    # FIX: Currently we should only have one supertype per interface, so no
    #      need to return an array
    result: list[Instance] = []
    for path in class_derivation_paths(instance.type, supertype):
        types = [instance]
        for sup in path:
            a: list[Instance] = []
            for t in types:
                a.extend(map_instance_to_direct_supertypes(t, sup))
            types = a
        result.extend(types)
    if result:
        return result
    else:
        # Nothing. Presumably due to an error. Construct a dummy using Any.
        any_type = AnyType(TypeOfAny.from_error)
        return [Instance(supertype, [any_type] * len(supertype.type_vars))]


def class_derivation_paths(typ: TypeInfo, supertype: TypeInfo) -> list[list[TypeInfo]]:
    """Return an array of non-empty paths of direct base classes from
    type to supertype.  Return [] if no such path could be found.

      InterfaceImplementationPaths(A, B) == [[B]] if A inherits B
      InterfaceImplementationPaths(A, C) == [[B, C]] if A inherits B and
                                                        B inherits C
    """
    # FIX: Currently we might only ever have a single path, so this could be
    #      simplified
    result: list[list[TypeInfo]] = []

    for base in typ.bases:
        btype = base.type
        if btype == supertype:
            result.append([btype])
        else:
            # Try constructing a longer path via the base class.
            for path in class_derivation_paths(btype, supertype):
                result.append([btype] + path)

    return result


def map_instance_to_direct_supertypes(instance: Instance, supertype: TypeInfo) -> list[Instance]:
    # FIX: There should only be one supertypes, always.
    typ = instance.type
    result: list[Instance] = []

    for b in typ.bases:
        if b.type == supertype:
            t = expand_type_by_instance(b, instance)
            assert isinstance(t, Instance)
            result.append(t)

    if result:
        return result
    else:
        # Relationship with the supertype not specified explicitly. Use dynamic
        # type arguments implicitly.
        any_type = AnyType(TypeOfAny.unannotated)
        return [Instance(supertype, [any_type] * len(supertype.type_vars))]
