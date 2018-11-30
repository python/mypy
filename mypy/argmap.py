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
                # We don't exactly know which **kwargs are provided by the
                # caller. Assume that they will fill the remaining arguments.
                for j in range(ncallee):
                    # TODO: If there are also tuple varargs, we might be missing some potential
                    #       matches if the tuple was short enough to not match everything.
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


class ArgTypeExpander:
    """Utility class for mapping actual argument types to formal arguments.

    One of the main responsibilities is to expand caller tuple *args and TypedDict
    **kwargs, and to keep track of which tuple/TypedDict items have already been
    consumed.

    Example:

       def f(x: int, *args: str) -> None: ...
       f(*(1, 'x', 1.1))

    We'd call expand_actual_type three times:

      1. The first call would provide 'int' as the actual type of 'x' (from '1').
      2. The second call would provide 'str' as one of the actual types for '*args'.
      2. The third call would provide 'float' as one of the actual types for '*args'.

    A single instance can process all the arguments for a single call. Each call
    needs a separate instance since instances have per-call state.
    """

    def __init__(self) -> None:
        # Next tuple *args index to use.
        self.tuple_index = 0
        # Keyword arguments in TypedDict **kwargs used.
        self.kwargs_used = set()  # type: Set[str]

    def expand_actual_type(self,
                           actual_type: Type,
                           actual_kind: int,
                           formal_name: Optional[str],
                           formal_kind: int) -> Type:
        """Return the actual (caller) type(s) of a formal argument with the given kinds.

        If the actual argument is a tuple *args, return the next individual tuple item that
        maps to the formal arg.

        If the actual argument is a TypedDict **kwargs, return the next matching typed dict
        value type based on formal argument name and kind.

        This is supposed to be called for each formal, in order. Call multiple times per
        formal if multiple actuals map to a formal.
        """
        if actual_kind == nodes.ARG_STAR:
            if isinstance(actual_type, Instance):
                if actual_type.type.fullname() == 'builtins.list':
                    # List *arg.
                    return actual_type.args[0]
                elif actual_type.args:
                    # TODO: Try to map type arguments to Iterable
                    return actual_type.args[0]
                else:
                    return AnyType(TypeOfAny.from_error)
            elif isinstance(actual_type, TupleType):
                # Get the next tuple item of a tuple *arg.
                if self.tuple_index >= len(actual_type.items):
                    # Exhausted a tuple -- continue to the next *args.
                    self.tuple_index = 1
                else:
                    self.tuple_index += 1
                return actual_type.items[self.tuple_index - 1]
            else:
                return AnyType(TypeOfAny.from_error)
        elif actual_kind == nodes.ARG_STAR2:
            if isinstance(actual_type, TypedDictType):
                if formal_kind != nodes.ARG_STAR2 and formal_name in actual_type.items:
                    # Lookup type based on keyword argument name.
                    assert formal_name is not None
                else:
                    # Pick an arbitrary item if no specified keyword is expected.
                    formal_name = (set(actual_type.items.keys()) - self.kwargs_used).pop()
                self.kwargs_used.add(formal_name)
                return actual_type.items[formal_name]
            elif (isinstance(actual_type, Instance)
                  and (actual_type.type.fullname() == 'builtins.dict')):
                # Dict **arg.
                # TODO: Handle arbitrary Mapping
                return actual_type.args[1]
            else:
                return AnyType(TypeOfAny.from_error)
        else:
            # No translation for other kinds -- 1:1 mapping.
            return actual_type
