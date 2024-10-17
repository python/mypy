from typing import Any, overload

default_action: str
once_registry: dict[Any, Any]

filters: list[tuple[Any, ...]]

@overload
def warn(message: str, category: type[Warning] | None = ..., stacklevel: int = ...) -> None: ...
@overload
def warn(message: Warning, category: Any = ..., stacklevel: int = ...) -> None: ...
@overload
def warn_explicit(
    message: str,
    category: type[Warning],
    filename: str,
    lineno: int,
    module: str | None = ...,
    registry: dict[str | tuple[str, type[Warning], int], int] | None = ...,
    module_globals: dict[str, Any] | None = ...,
) -> None: ...
@overload
def warn_explicit(
    message: Warning,
    category: Any,
    filename: str,
    lineno: int,
    module: str | None = ...,
    registry: dict[str | tuple[str, type[Warning], int], int] | None = ...,
    module_globals: dict[str, Any] | None = ...,
) -> None: ...
