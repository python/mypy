"""Representation classes for Type subclasses and TypeVars.

These are used for source-source transformation that preserves original
formatting and comments.
"""

from typing import List, Any

from mypy.lex import Token


class VoidRepr:
    """Representation of the 'None' type."""
    def __init__(self, void: Any) -> None:
        self.void = void


class CallableRepr:
    """Representation of CallableType."""
    def __init__(self, func: Any, langle: Any, lparen: Any, commas: Any,
                 rparen: Any, rangle: Any) -> None:
        self.func = func
        self.langle = langle
        self.lparen = lparen
        self.commas = commas
        self.rparen = rparen
        self.rangle = rangle


class TypeVarRepr:
    """Representation of TypeVarType."""
    def __init__(self, name: Any) -> None:
        self.name = name


class TypeVarsRepr:
    """Representation of TypeVars."""
    def __init__(self, langle: Any, commas: List[Token], rangle: Any) -> None:
        self.langle = langle
        self.commas = commas
        self.rangle = rangle


class TypeVarDefRepr:
    """Representation of TypeVarDef."""
    def __init__(self, name: Any, is_tok: Any) -> None:
        # TODO remove is_tok
        self.name = name
        self.is_tok = is_tok
