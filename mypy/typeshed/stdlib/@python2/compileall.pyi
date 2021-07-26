from typing import Any, Optional, Pattern, Text

# rx can be any object with a 'search' method; once we have Protocols we can change the type
def compile_dir(
    dir: Text,
    maxlevels: int = ...,
    ddir: Optional[Text] = ...,
    force: bool = ...,
    rx: Optional[Pattern[Any]] = ...,
    quiet: int = ...,
) -> int: ...
def compile_file(
    fullname: Text, ddir: Optional[Text] = ..., force: bool = ..., rx: Optional[Pattern[Any]] = ..., quiet: int = ...
) -> int: ...
def compile_path(skip_curdir: bool = ..., maxlevels: int = ..., force: bool = ..., quiet: int = ...) -> int: ...
