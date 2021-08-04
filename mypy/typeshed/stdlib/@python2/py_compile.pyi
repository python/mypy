from typing import List, Optional, Text, Type, Union

_EitherStr = Union[bytes, Text]

class PyCompileError(Exception):
    exc_type_name: str
    exc_value: BaseException
    file: str
    msg: str
    def __init__(self, exc_type: Type[BaseException], exc_value: BaseException, file: str, msg: str = ...) -> None: ...

def compile(
    file: _EitherStr, cfile: Optional[_EitherStr] = ..., dfile: Optional[_EitherStr] = ..., doraise: bool = ...
) -> None: ...
def main(args: Optional[List[Text]] = ...) -> int: ...
