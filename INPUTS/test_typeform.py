from typing import Any, Callable, cast, Never, NoReturn, Optional, reveal_type, Type, TypeVar, TypedDict
from typing_extensions import TypeForm, TypeGuard

dict_with_typx_keys: dict[TypeForm, int] = {
    int | str: 1,
    str | None: 2,
}
dict_with_typx_keys[int | str] += 1

#typx1: TypeForm[int | str] = 'int | str'  # OK
#typx2: TypeForm[int] = 'str'  # E: Incompatible types in assignment (expression has type "TypeForm[str]", variable has type "TypeForm[int]")

'''
from typing import Any

T = TypeVar('T')

def as_typeform(typx: TypeForm[T]) -> TypeForm[T]:
    return typx

def as_type(typx: TypeForm[T]) -> Type[T] | None:
    if isinstance(typx, type):
        return typx
    else:
        return None

def as_instance(typx: TypeForm[T]) -> T | None:
    if isinstance(typx, type):
        return typx()
    else:
        return None

reveal_type(as_typeform(int | str))  # actual=TypeForm[Never], expect=TypeForm[int | str]
reveal_type(as_type(int | str))
reveal_type(as_type(int))
reveal_type(as_instance(int | str))
reveal_type(as_instance(int))
'''
