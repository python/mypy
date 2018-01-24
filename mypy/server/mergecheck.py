from collections import deque
from collections.abc import Iterable
from typing import List, Dict, Iterator, Optional, Tuple, Mapping
import weakref
import types

method_descriptor_type = type(object.__dir__)
method_wrapper_type = type(object().__ne__)
wrapper_descriptor_type = type(object.__ne__)
ATTR_BLACKLIST = {
    '__doc__',
    '__name__',
    '__class__',
    '__dict__',

    # mypy specific attr blacklists
    'indirection_detector',
    'all_types',
    'type_maps',
    'semantic_analyzer', # semantic analyzer has stale caches
    'semantic_analyzer_pass3', # semantic analyzer has stale caches
}
TYPE_BLACKLIST = {
    int,
    float,
    str,
    weakref.ReferenceType,
}


def get_edge_candidates(o: object) -> Iterator[Tuple[object, object]]:
    for attr in dir(o):
        if attr not in ATTR_BLACKLIST and hasattr(o, attr):
            yield attr, getattr(o, attr)
    if isinstance(o, Iterable) and not isinstance(o, str):
        for i, e in enumerate(o):
            yield i, e
    if isinstance(o, Mapping):
        for k, v in o.items():
            yield k, v


def get_edges(o: object) -> Iterator[Tuple[object, object]]:
    for s, e in get_edge_candidates(o):
        if (
                isinstance(e, types.BuiltinFunctionType) or
                isinstance(e, types.FunctionType) or
                isinstance(e, types.MethodType) or
                isinstance(e, method_descriptor_type) or
                isinstance(e, wrapper_descriptor_type) or
                isinstance(e, method_wrapper_type)):
            # We don't want to collect methods, but do want to collect values
            # in closures and self pointers to other objects

            if hasattr(e, '__closure__'):
                yield (s, '__closure__'), getattr(e, '__closure__')
            if hasattr(e, '__self__'):
                se = getattr(e, '__self__')
                if se is not o and se is not type(o):
                    yield (s, '__self__'), se
        else:
            if not type(e) in TYPE_BLACKLIST:
                yield s, e


def get_reachable_graph(root: object) -> Tuple[Dict[int, object],
                                               Dict[int, Tuple[int, object]]]:
    parents = {}
    seen = {id(root): root}
    worklist = [root]
    while worklist:
        o = worklist.pop()
        for s, e in get_edges(o):
            if id(e) in seen: continue
            parents[id(e)] = (id(o), s)
            seen[id(e)] = e
            worklist.append(e)

    return seen, parents


def find_all_reachable(root: object) -> List[object]:
    return list(get_reachable_graph(root)[0].values())


def aggregate_by_type(objs: List[object]) -> Dict[type, List[object]]:
    m = {}  # type: Dict[type, List[object]]
    for o in objs:
        m.setdefault(type(o), []).append(o)
    return m


def get_path(o: object,
             seen: Dict[int, object],
             parents: Dict[int, Tuple[int, object]]) -> List[Tuple[object, object]]:
    path = []
    while id(o) in parents:
        pid, attr = parents[id(o)]
        o = seen[pid]
        path.append((attr, o))
    path.reverse()
    return path


#####################################################

from mypy.nodes import SymbolNode, Var, Decorator, OverloadedFuncDef, FuncDef

PRINT_MISMATCH = False
def check_consistency(o: object) -> None:
    seen, parents = get_reachable_graph(o)
    reachable = list(seen.values())
    syms = [x for x in reachable if isinstance(x, SymbolNode)]

    m = {}  # type: Dict[str, SymbolNode]
    for sym in syms:
        fn = sym.fullname()
        # Skip stuff that should be expected to have duplicate names
        if isinstance(sym, Var): continue
        if isinstance(sym, Decorator): continue
        if isinstance(sym, FuncDef) and sym.is_overload: continue

        if fn not in m:
            m[sym.fullname()] = sym
            continue

        # We have trouble and need to decide what to do about it.
        sym1, sym2 = sym, m[fn]

        # If the type changed, then it shouldn't have been merged
        if type(sym1) is not type(sym2): continue

        # XXX: It is wrong even if the dicts match but it is extra
        # wrong if they don't, so I have been looking for those cases.
        # if m[fn].__dict__ is sym.__dict__: continue

        path1 = get_path(sym1, seen, parents)
        path2 = get_path(sym2, seen, parents)
        if PRINT_MISMATCH:
            print(sym1, sym2, path1, path2)
        assert sym.fullname() not in m
