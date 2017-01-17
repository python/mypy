from typing import Dict, Type, TypeVar, AsyncGenerator as AsyncGenerator

T = TypeVar('T')


def TypedDict(typename: str, fields: Dict[str, Type[T]]) -> Type[dict]: pass

class NoReturn: pass
