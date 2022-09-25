from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO
from typing_extensions import TypeAlias

__all__ = ["ZipAppError", "create_archive", "get_interpreter"]

_Path: TypeAlias = str | Path | BinaryIO

class ZipAppError(ValueError): ...

def create_archive(
    source: _Path,
    target: _Path | None = ...,
    interpreter: str | None = ...,
    main: str | None = ...,
    filter: Callable[[Path], bool] | None = ...,
    compressed: bool = ...,
) -> None: ...
def get_interpreter(archive: _Path) -> str: ...
