"""Utilities for mapping between actual and formal arguments (and their types)."""

from typing import List, Optional, Sequence, Callable

from mypy.types import Type, Instance, TupleType, AnyType, TypeOfAny
from mypy import nodes


def map_actuals_to_formals(caller_kinds: List[int],
                           caller_names: Optional[Sequence[Optional[str]]],
                           callee_kinds: List[int],
                           callee_names: Sequence[Optional[str]],
                           caller_arg_type: Callable[[int],
                                                     Type]) -> List[List[int]]:
    """Calculate mapping between actual (caller) args and formals.

    The result contains a list of caller argument indexes mapping to each
    callee argument index, indexed by callee index.

    The caller_arg_type argument should evaluate to the type of the actual
    argument type with the given index.
    """
    ncallee = len(callee_kinds)
    map = [[] for i in range(ncallee)]  # type: List[List[int]]
    j = 0
    for i, kind in enumerate(caller_kinds):
        if kind == nodes.ARG_POS:
            if j < ncallee:
                if callee_kinds[j] in [nodes.ARG_POS, nodes.ARG_OPT,
                                       nodes.ARG_NAMED, nodes.ARG_NAMED_OPT]:
                    map[j].append(i)
                    j += 1
                elif callee_kinds[j] == nodes.ARG_STAR:
                    map[j].append(i)
        elif kind == nodes.ARG_STAR:
            # We need to know the actual type to map varargs.
            argt = caller_arg_type(i)
            if isinstance(argt, TupleType):
                # A tuple actual maps to a fixed number of formals.
                for _ in range(len(argt.items)):
                    if j < ncallee:
                        if callee_kinds[j] != nodes.ARG_STAR2:
                            map[j].append(i)
                        else:
                            break
                        if callee_kinds[j] != nodes.ARG_STAR:
                            j += 1
            else:
                # Assume that it is an iterable (if it isn't, there will be
                # an error later).
                while j < ncallee:
                    if callee_kinds[j] in (nodes.ARG_NAMED, nodes.ARG_NAMED_OPT, nodes.ARG_STAR2):
                        break
                    else:
                        map[j].append(i)
                    if callee_kinds[j] == nodes.ARG_STAR:
                        break
                    j += 1
        elif kind in (nodes.ARG_NAMED, nodes.ARG_NAMED_OPT):
            assert caller_names is not None, "Internal error: named kinds without names given"
            name = caller_names[i]
            if name in callee_names:
                map[callee_names.index(name)].append(i)
            elif nodes.ARG_STAR2 in callee_kinds:
                map[callee_kinds.index(nodes.ARG_STAR2)].append(i)
        else:
            assert kind == nodes.ARG_STAR2
            for j in range(ncallee):
                # TODO tuple varargs complicate this
                no_certain_match = (
                    not map[j] or caller_kinds[map[j][0]] == nodes.ARG_STAR)
                if ((callee_names[j] and no_certain_match)
                        or callee_kinds[j] == nodes.ARG_STAR2):
                    map[j].append(i)
    return map


def map_formals_to_actuals(caller_kinds: List[int],
                           caller_names: Optional[Sequence[Optional[str]]],
                           callee_kinds: List[int],
                           callee_names: List[Optional[str]],
                           caller_arg_type: Callable[[int],
                                                     Type]) -> List[List[int]]:
    """Calculate the reverse mapping of map_actuals_to_formals."""
    formal_to_actual = map_actuals_to_formals(caller_kinds,
                                              caller_names,
                                              callee_kinds,
                                              callee_names,
                                              caller_arg_type)
    # Now reverse the mapping.
    actual_to_formal = [[] for _ in caller_kinds]  # type: List[List[int]]
    for formal, actuals in enumerate(formal_to_actual):
        for actual in actuals:
            actual_to_formal[actual].append(formal)
    return actual_to_formal


def get_actual_type(arg_type: Type, kind: int,
                    tuple_counter: List[int]) -> Type:
    """Return the type of an actual argument with the given kind.

    If the argument is a *arg, return the individual argument item.
    """

    if kind == nodes.ARG_STAR:
        if isinstance(arg_type, Instance):
            if arg_type.type.fullname() == 'builtins.list':
                # List *arg.
                return arg_type.args[0]
            elif arg_type.args:
                # TODO try to map type arguments to Iterable
                return arg_type.args[0]
            else:
                return AnyType(TypeOfAny.from_error)
        elif isinstance(arg_type, TupleType):
            # Get the next tuple item of a tuple *arg.
            tuple_counter[0] += 1
            return arg_type.items[tuple_counter[0] - 1]
        else:
            return AnyType(TypeOfAny.from_error)
    elif kind == nodes.ARG_STAR2:
        if isinstance(arg_type, Instance) and (arg_type.type.fullname() == 'builtins.dict'):
            # Dict **arg. TODO more general (Mapping)
            return arg_type.args[1]
        else:
            return AnyType(TypeOfAny.from_error)
    else:
        # No translation for other kinds.
        return arg_type
