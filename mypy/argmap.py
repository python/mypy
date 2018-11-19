"""Utilities for mapping between actual and formal arguments (and their types)."""

from typing import List, Optional, Sequence, Callable, Set

from mypy.types import Type, Instance, TupleType, AnyType, TypeOfAny, TypedDictType
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
            argt = caller_arg_type(i)
            if isinstance(argt, TypedDictType):
                for name, value in argt.items.items():
                    if name in callee_names:
                        map[callee_names.index(name)].append(i)
                    elif nodes.ARG_STAR2 in callee_kinds:
                        map[callee_kinds.index(nodes.ARG_STAR2)].append(i)
            else:
                # We don't exactly which **kwargs are provided by the
                # caller. Assume that they will fill the remaining arguments.
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


class ArgTypeMapper:
    """Utility class for mapping actual argument types to formal argument types.

    The main job is to expand tuple *args and typed dict **kwargs in caller, and to
    keep track of which tuple/typed dict items have already been consumed.
    """

    def __init__(self) -> None:
        # Next tuple *args index to use.
        self.tuple_index = 0
        # Keyword arguments in TypedDict **kwargs used.
        self.kwargs_used = set()  # type: Set[str]

    def get_actual_type(self, arg_type: Type, kind: int, arg_name: Optional[str]) -> List[Type]:
        """Return the type(s) of an actual argument with the given kind.

        If the argument is a *args, return the individual argument item. The
        tuple_counter argument tracks the next unused tuple item.

        If the argument is a **kwargs, return the item type based on argument name,
        or all item types otherwise.
        """
        if kind == nodes.ARG_STAR:
            if isinstance(arg_type, Instance):
                if arg_type.type.fullname() == 'builtins.list':
                    # List *arg.
                    return [arg_type.args[0]]
                elif arg_type.args:
                    # TODO try to map type arguments to Iterable
                    return [arg_type.args[0]]
                else:
                    return [AnyType(TypeOfAny.from_error)]
            elif isinstance(arg_type, TupleType):
                # Get the next tuple item of a tuple *arg.
                self.tuple_index += 1
                return [arg_type.items[self.tuple_index - 1]]
            else:
                return [AnyType(TypeOfAny.from_error)]
        elif kind == nodes.ARG_STAR2:
            if isinstance(arg_type, TypedDictType):
                if arg_name in arg_type.items:
                    # Lookup type based on keyword argument name.
                    assert arg_name is not None
                    self.kwargs_used.add(arg_name)
                    return [arg_type.items[arg_name]]
                else:
                    # Callee takes **kwargs. Give all remaining keyword args.
                    return [value for key, value in arg_type.items.items()
                            if key not in self.kwargs_used]
            elif isinstance(arg_type, Instance) and (arg_type.type.fullname() == 'builtins.dict'):
                # Dict **arg. TODO more general (Mapping)
                return [arg_type.args[1]]
            else:
                return [AnyType(TypeOfAny.from_error)]
        else:
            # No translation for other kinds.
            return [arg_type]
