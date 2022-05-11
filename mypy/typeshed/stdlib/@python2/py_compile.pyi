from typing import Text

_EitherStr = bytes | Text

class PyCompileError(Exception):
    exc_type_name: str
    exc_value: BaseException
    file: str
    msg: str
    def __init__(self, exc_type: type[BaseException], exc_value: BaseException, file: str, msg: str = ...) -> None: ...

def compile(file: _EitherStr, cfile: _EitherStr | None = ..., dfile: _EitherStr | None = ..., doraise: bool = ...) -> None: ...
def main(args: list[Text] | None = ...) -> int: ...
