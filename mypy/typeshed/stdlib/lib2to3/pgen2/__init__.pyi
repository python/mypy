from collections.abc import Callable
from lib2to3.pgen2.grammar import Grammar
from lib2to3.pytree import _RawNode
from typing import Any
from typing_extensions import TypeAlias

# This is imported in several lib2to3/pgen2 submodules
_Convert: TypeAlias = Callable[[Grammar, _RawNode], Any]  # noqa: Y047
