from __future__ import annotations

import importlib.abc
import importlib.util
import pathlib
import sys
import zipfile
from collections.abc import Sequence
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing_extensions import Self

# Assert that some Path classes are Traversable.
if sys.version_info >= (3, 9):

    def traverse(t: importlib.abc.Traversable) -> None:
        pass

    traverse(pathlib.Path())
    traverse(zipfile.Path(""))


class MetaFinder:
    @classmethod
    def find_spec(cls, fullname: str, path: Sequence[str] | None, target: ModuleType | None = None) -> ModuleSpec | None:
        return None  # simplified mock for demonstration purposes only


class PathFinder:
    @classmethod
    def path_hook(cls, path_entry: str) -> type[Self]:
        return cls  # simplified mock for demonstration purposes only

    @classmethod
    def find_spec(cls, fullname: str, target: ModuleType | None = None) -> ModuleSpec | None:
        return None  # simplified mock for demonstration purposes only


class Loader:
    @classmethod
    def load_module(cls, fullname: str) -> ModuleType:
        return ModuleType(fullname)


sys.meta_path.append(MetaFinder)
sys.path_hooks.append(PathFinder.path_hook)
importlib.util.spec_from_loader("xxxx42xxxx", Loader)
