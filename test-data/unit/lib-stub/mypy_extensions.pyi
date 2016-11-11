from typing import Dict, Type, TypeVar, Optional, Any

T = TypeVar('T')


def TypedDict(typename: str, fields: Dict[str, Type[T]]) -> Type[dict]: ...

class Arg(object):
    def __init__(name: Optional[str]=...,
                 typ: Type[T]=...,
                 keyword_only: Optional[bool]=...) -> None:
        ...

class DefaultArg(object):
    def __init__(name: Optional[str]=...,
                 typ: Type[T]=...,
                 keyword_only: Optional[bool]=...) -> None:
        ...

class StarArg(object):
    def __init__(typ: Type[T]=...) -> None: ...

class KwArg(object):
    def __init__(typ: Type[T]=...) -> None: ...
