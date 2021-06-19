from typing import Optional

def version() -> str: ...
def bootstrap(
    *,
    root: Optional[str] = ...,
    upgrade: bool = ...,
    user: bool = ...,
    altinstall: bool = ...,
    default_pip: bool = ...,
    verbosity: int = ...,
) -> None: ...
