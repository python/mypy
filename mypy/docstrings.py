from typing import List, Tuple, Dict
from mypy.types import Type, CallableType, AnyType
from mypy.nodes import Argument


def parse_docstring(docstring: str, line: int) -> Tuple[Dict[str, Type], Type]:
    """
    Parse a docstring and return type representations.  This function can
    be overridden by third-party tools which aim to add typing via docstrings.

    Returns a 2-tuple: dictionary of arg name to Type, and return Type.
    """
    return None, None


def make_callable(args: List[Argument], type_map: Dict[str, Type],
                  ret_type: Type) -> CallableType:
    if type_map is not None:
        arg_kinds = [arg.kind for arg in args]
        arg_names = [arg.variable.name() for arg in args]
        arg_types = [type_map.get(name) for name in arg_names]

        return CallableType([a if a is not None else AnyType() for a in arg_types],
                            arg_kinds,
                            arg_names,
                            ret_type, None,
                            is_ellipsis_args=False)
