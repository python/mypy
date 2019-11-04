from typing import Union, Tuple, Any, Callable


# copy pasted from typeshed
def narrow_cast(T: Union[type, Tuple[Union[type, Tuple[Any, ...]], ...]]) \
        -> Callable[..., Callable[..., bool]]:
    def narrow_cast_inner(f: Callable[..., bool]) -> Callable[..., bool]:
        return f  # binds first argument of f to T

    return narrow_cast_inner
