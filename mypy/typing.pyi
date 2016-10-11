from typing import Dict, Type, TypeVar

_T = TypeVar('_T')


def TypedDict(typename: str, fields: Dict[str, Type[_T]]) -> Type[dict]: ...
