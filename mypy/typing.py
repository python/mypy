"""The "mypy.typing" module defines experimental extensions to the standard
"typing" module that is supported by the mypy typechecker.
"""

from typing import cast, Dict, Type, TypeVar


_T = TypeVar('_T')


def TypedDict(typename: str, fields: Dict[str, Type[_T]]) -> Type[dict]:
    """TypedDict creates a dictionary type that expects all of its
    instances to have a certain common set of keys, with each key
    associated with a value of a consistent type. This expectation
    is not checked at runtime but is only enforced by typecheckers.
    """
    def new_dict(*args, **kwargs):
        return dict(*args, **kwargs)

    new_dict.__name__ = typename  # type: ignore  # https://github.com/python/mypy/issues/708
    new_dict.__supertype__ = dict  # type: ignore  # https://github.com/python/mypy/issues/708
    return cast(Type[dict], new_dict)
