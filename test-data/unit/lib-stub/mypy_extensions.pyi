from typing import Dict, Type, TypeVar, Callable

T = TypeVar('T')


def TypedDict(typename: str, fields: Dict[str, Type[T]]) -> Type[dict]: pass

class NoReturn: pass

def decorated_type(t: Type) -> Callable[[T], T]: pass