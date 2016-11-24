from typing import Dict, Type, TypeVar

T = TypeVar('T')


def TypedDict(typename: str, fields: Dict[str, Type[T]]) -> Type[dict]: pass
