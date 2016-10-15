from typing import Dict, Optional, Callable, Union
from mypy.types import Type

hooks = {}  # type: Dict[str, Callable]

docstring_parser_type = Callable[[str, int], Optional[Dict[str, Union[str, Type]]]]


def set_docstring_parser(func: docstring_parser_type) -> None:
    """Enable the docstring parsing hook.

    The callable must take a docstring for a function along with its line number
    (typically passed to mypy.parsetype.parse_str_as_type), and should return
    a mapping of argument name to type. The function's return type, if
    specified, is stored in the mapping with the special key 'return'.

    The keys of the mapping must be a subset of the arguments of the function
    to which the docstring belongs (other than the special 'return'
    key); an error will be raised if the mapping contains stray arguments.

    The values of the mapping must be either mypy.types.Type or a valid
    PEP484-compatible string which can be converted to a Type.
    """
    hooks['docstring_parser'] = func


def get_docstring_parser() -> Optional[docstring_parser_type]:
    return hooks.get('docstring_parser')
