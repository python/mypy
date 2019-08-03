"""Dump the runtime structure of a module as JSON.

This is used for testing stubs.
"""
import importlib
import inspect
import json
import sys
import types
from types import FunctionType
from typing import Optional, Dict, Any, Set, Callable
from typing_extensions import Final


DumpNode = Dict[str, Any]


def dump_module(id: str) -> None:
    m = importlib.import_module(id)
    data = module_to_json(m)
    print(json.dumps(data, ensure_ascii=True, indent=4, sort_keys=True))


def module_to_json(m: object) -> Dict[str, DumpNode]:
    result = {}  # type: Dict[str, DumpNode]
    for name, value in m.__dict__.items():
        # Filter out some useless attributes.

        if name in ('__file__',
                    '__doc__',
                    '__name__',
                    '__builtins__',
                    '__package__'):
            continue

        if name == '__all__':
            result[name] = {'type': 'list', 'values': sorted(value)}
        else:
            result[name] = dump_value(value)

        try:
            line = inspect.getsourcelines(getattr(m, name))[1]  # type: Optional[int]
        except (TypeError, OSError):
            line = None

        result[name]['line'] = line

    return result


def dump_value(value: object, depth: int = 0) -> DumpNode:
    if depth > 10:
        # TODO: Callers don't handle this case.
        return 'max_recursion_depth_exceeded'  # type: ignore
    if isinstance(value, type):
        return dump_class(value, depth + 1)
    if isinstance(value, FunctionType):
        return dump_function(value)
    if callable(value):
        return {'type': 'callable'}  # TODO more information
    if isinstance(value, types.ModuleType):
        return {'type': 'module'}  # TODO module name
    if inspect.isdatadescriptor(value):
        return {'type': 'datadescriptor'}

    if inspect.ismemberdescriptor(value):
        return {'type': 'memberdescriptor'}
    return dump_simple(value)


def dump_simple(value: object) -> DumpNode:
    if type(value) in (int, bool, float, str, bytes, list, set, dict, tuple):
        return {'type': type(value).__name__}
    if value is None:
        return {'type': 'None'}
    if value is inspect.Parameter.empty:
        return {'type': None}  # 'None' and None: Ruh-Roh
    return {'type': 'unknown'}


def dump_class(value: type, depth: int) -> DumpNode:
    return {
        'type': 'class',
        'attributes': dump_attrs(value, depth),
    }


special_methods = [
    '__init__',
    '__str__',
    '__int__',
    '__float__',
    '__bool__',
    '__contains__',
    '__iter__',
]  # type: Final


# Change to return a dict
def dump_attrs(d: type, depth: int) -> DumpNode:
    result = {}
    seen = set()  # type: Set[str]
    try:
        mro = d.mro()
    except TypeError:
        mro = [d]
    for base in mro:
        v = vars(base)
        for name, value in v.items():
            if name not in seen:
                result[name] = dump_value(value, depth + 1)
                seen.add(name)
    for m in special_methods:
        if hasattr(d, m) and m not in seen:
            result[m] = dump_value(getattr(d, m), depth + 1)
    return result


kind_map = {
    inspect.Parameter.POSITIONAL_ONLY: 'POS_ONLY',
    inspect.Parameter.POSITIONAL_OR_KEYWORD: 'POS_OR_KW',
    inspect.Parameter.VAR_POSITIONAL: 'VAR_POS',
    inspect.Parameter.KEYWORD_ONLY: 'KW_ONLY',
    inspect.Parameter.VAR_KEYWORD: 'VAR_KW',
}  # type: Final


def param_kind(p: inspect.Parameter) -> str:
    s = kind_map[p.kind]
    if p.default != inspect.Parameter.empty:
        assert s in ('POS_ONLY', 'POS_OR_KW', 'KW_ONLY')
        s += '_OPT'
    return s


def dump_function(value: FunctionType) -> DumpNode:
    try:
        sig = inspect.signature(value)
    except ValueError:
        # The signature call sometimes fails for some reason.
        return {'type': 'invalid_signature'}
    params = list(sig.parameters.items())
    return {
        'type': 'function',
        'args': [(name, param_kind(p), dump_simple(p.default))
                 for name, p in params],
    }


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        sys.exit('usage: dumpmodule.py module-name')
    dump_module(sys.argv[1])
