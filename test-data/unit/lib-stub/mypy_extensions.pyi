from typing import Dict, Type, TypeVar, Optional, Any

T = TypeVar('T')


def TypedDict(typename: str, fields: Dict[str, Type[T]]) -> Type[dict]: pass

def Arg(name=None, typ: T = ...) -> T: pass

def DefaultArg(name=None, typ: T = ...) -> T: pass

def NamedArg(name=None, typ: T = ...) -> T: pass

def DefaultNamedArg(name=None, typ: T = ...) -> T: pass

def StarArg(typ: T = ...) -> T: pass

def KwArg(typ: T = ...) -> T: pass

class NoReturn: pass
