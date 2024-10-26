import sys
import types
from _typeshed import ReadableBuffer
from importlib.machinery import ModuleSpec
from typing import Any

check_hash_based_pycs: str

def source_hash(key: int, source: ReadableBuffer) -> bytes: ...
def create_builtin(spec: ModuleSpec, /) -> types.ModuleType: ...
def create_dynamic(spec: ModuleSpec, file: Any = None, /) -> types.ModuleType: ...
def acquire_lock() -> None: ...
def exec_builtin(mod: types.ModuleType, /) -> int: ...
def exec_dynamic(mod: types.ModuleType, /) -> int: ...
def extension_suffixes() -> list[str]: ...
def init_frozen(name: str, /) -> types.ModuleType: ...
def is_builtin(name: str, /) -> int: ...
def is_frozen(name: str, /) -> bool: ...
def is_frozen_package(name: str, /) -> bool: ...
def lock_held() -> bool: ...
def release_lock() -> None: ...

if sys.version_info >= (3, 11):
    def find_frozen(name: str, /, *, withdata: bool = False) -> tuple[memoryview | None, bool, str | None] | None: ...
    def get_frozen_object(name: str, data: ReadableBuffer | None = None, /) -> types.CodeType: ...

else:
    def get_frozen_object(name: str, /) -> types.CodeType: ...
