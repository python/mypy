from __future__ import annotations
from typing import Annotated

class _EnvironmentVariables():
    def __init__(self, variables: dict[str, bytes]) -> None:
        self.__variables = variables

def EnvironmentVariables(sort: bool):  # noqa (This func is imitating a type name, so upper-camel-case is ok)
    return Annotated[_EnvironmentVariables, dict]

def unsorted_env_variables(variables: EnvironmentVariables(sort=False)) -> None:
    return variables.as_json_obj()