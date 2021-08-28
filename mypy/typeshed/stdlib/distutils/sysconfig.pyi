from distutils.ccompiler import CCompiler
from typing import Mapping

PREFIX: str
EXEC_PREFIX: str

def get_config_var(name: str) -> int | str | None: ...
def get_config_vars(*args: str) -> Mapping[str, int | str]: ...
def get_config_h_filename() -> str: ...
def get_makefile_filename() -> str: ...
def get_python_inc(plat_specific: bool = ..., prefix: str | None = ...) -> str: ...
def get_python_lib(plat_specific: bool = ..., standard_lib: bool = ..., prefix: str | None = ...) -> str: ...
def customize_compiler(compiler: CCompiler) -> None: ...
