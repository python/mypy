from collections import deque
from collections.abc import Iterable
from typing import List, Dict, Iterator, Optional, Tuple, Mapping
import weakref
import types

from mypy.nodes import SymbolNode, Var, Decorator, OverloadedFuncDef, FuncDef


method_descriptor_type = type(object.__dir__)
method_wrapper_type = type(object().__ne__)
wrapper_descriptor_type = type(object.__ne__)

FUNCTION_TYPES = (types.BuiltinFunctionType,
                  types.FunctionType,
                  types.MethodType,
                  method_descriptor_type,
                  wrapper_descriptor_type,
                  method_wrapper_type)

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

# Instances of these types can't have references to other objects
ATOMIC_TYPE_BLACKLIST = {
    bool,
    int,
    float,
    str,
    type(None),
    object,
}

COLLECTION_TYPE_BLACKLIST = {
    list,
    set,
    dict,
    tuple,
}

TYPE_BLACKLIST = {
    weakref.ReferenceType,
}


def isproperty(o: object, attr: str) -> bool:
    return isinstance(getattr(type(o), attr, None), property)


def get_edge_candidates(o: object) -> Iterator[Tuple[object, object]]:
    if type(o) not in COLLECTION_TYPE_BLACKLIST:
        for attr in dir(o):
            if attr not in ATTR_BLACKLIST and hasattr(o, attr) and not isproperty(o, attr):
                e = getattr(o, attr)
                if not type(e) in ATOMIC_TYPE_BLACKLIST:
                    yield attr, e
    if isinstance(o, Mapping):
        for k, v in o.items():
            yield k, v
    elif isinstance(o, Iterable) and not isinstance(o, str):
        for i, e in enumerate(o):
            yield i, e


def get_edges(o: object) -> Iterator[Tuple[object, object]]:
    for s, e in get_edge_candidates(o):
        #if isinstance(e, (types.BuiltinFunctionType,
        #                  method_descriptor_type,
        #                  wrapper_descriptor_type)):
        #    print(s, e)
        #else:
        #    print(s, type(e))
        if (isinstance(e, FUNCTION_TYPES)):
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


DUMP_MISMATCH_NODES = False


def check_consistency(o: object) -> None:
    seen, parents = get_reachable_graph(o)
    reachable = list(seen.values())
    syms = [x for x in reachable if isinstance(x, SymbolNode)]

    m = {}  # type: Dict[str, SymbolNode]
    for sym in syms:
        fn = sym.fullname()
        if fn is None:
            continue
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
        if DUMP_MISMATCH_NODES and fn in m:
            print('---')
            print(id(sym1), sym1)
            print('---')
            print(id(sym2), sym2)

        if fn in m:
            print('\nDuplicate %r nodes with fullname %r found:' % (type(sym).__name__, fn))
            print('[1] %d: %s' % (id(sym1), path_to_str(path1)))
            print('[2] %d: %s' % (id(sym2), path_to_str(path2)))
        assert sym.fullname() not in m


def path_to_str(path: List[Tuple[object, object]]) -> str:
    result = '<root>'
    for attr, obj in path:
        t = type(obj).__name__
        if t in ('dict', 'tuple', 'SymbolTable', 'list'):
            result += '[%s]' % repr(attr)
        else:
            if t == 'Var':
                result += '.%s(%s:%s)' % (attr, t, obj.name())
            elif t in ('BuildManager', 'FineGrainedBuildManager'):
                # Omit class name for some classes that aren't part of a class
                # hierarchy since there isn't much ambiguity.
                result += '.%s' % attr
            else:
                result += '.%s(%s)' % (attr, t)
    return result
