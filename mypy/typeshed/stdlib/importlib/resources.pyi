import os
import sys
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any, BinaryIO, TextIO
from typing_extensions import TypeAlias

if sys.version_info >= (3, 10):
    __all__ = [
        "Package",
        "Resource",
        "ResourceReader",
        "as_file",
        "contents",
        "files",
        "is_resource",
        "open_binary",
        "open_text",
        "path",
        "read_binary",
        "read_text",
    ]
elif sys.version_info >= (3, 9):
    __all__ = [
        "Package",
        "Resource",
        "as_file",
        "contents",
        "files",
        "is_resource",
        "open_binary",
        "open_text",
        "path",
        "read_binary",
        "read_text",
    ]
else:
    __all__ = ["Package", "Resource", "contents", "is_resource", "open_binary", "open_text", "path", "read_binary", "read_text"]

Package: TypeAlias = str | ModuleType
Resource: TypeAlias = str | os.PathLike[Any]

def open_binary(package: Package, resource: Resource) -> BinaryIO: ...
def open_text(package: Package, resource: Resource, encoding: str = ..., errors: str = ...) -> TextIO: ...
def read_binary(package: Package, resource: Resource) -> bytes: ...
def read_text(package: Package, resource: Resource, encoding: str = ..., errors: str = ...) -> str: ...
def path(package: Package, resource: Resource) -> AbstractContextManager[Path]: ...
def is_resource(package: Package, name: str) -> bool: ...
def contents(package: Package) -> Iterator[str]: ...

if sys.version_info >= (3, 9):
    from importlib.abc import Traversable
    def files(package: Package) -> Traversable: ...
    def as_file(path: Traversable) -> AbstractContextManager[Path]: ...

if sys.version_info >= (3, 10):
    from importlib.abc import ResourceReader as ResourceReader
