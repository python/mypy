"""Shared definitions used by different parts of semantic analysis."""

from abc import abstractmethod, abstractproperty
from typing import Optional, List, Callable
from mypy_extensions import trait

from mypy.nodes import (
    Context, SymbolTableNode, MypyFile, ImportedName, FuncDef, Node, TypeInfo, Expression, GDEF
)
from mypy.util import correct_relative_import
from mypy.types import Type, FunctionLike, Instance
from mypy.tvar_scope import TypeVarScope

MYPY = False
if False:
    from typing_extensions import Final

# Priorities for ordering of patches within the final "patch" phase of semantic analysis
# (after pass 3):

# Fix forward references (needs to happen first)
PRIORITY_FORWARD_REF = 0  # type: Final
# Fix fallbacks (does joins)
PRIORITY_FALLBACKS = 1  # type: Final
# Checks type var values (does subtype checks)
PRIORITY_TYPEVAR_VALUES = 2  # type: Final


@trait
class SemanticAnalyzerCoreInterface:
    """A core abstract interface to generic semantic analyzer functionality.

    This is implemented by both semantic analyzer passes 2 and 3.
    """

    @abstractmethod
    def lookup_qualified(self, name: str, ctx: Context,
                         suppress_errors: bool = False) -> Optional[SymbolTableNode]:
        raise NotImplementedError

    @abstractmethod
    def lookup_fully_qualified(self, name: str) -> SymbolTableNode:
        raise NotImplementedError

    @abstractmethod
    def fail(self, msg: str, ctx: Context, serious: bool = False, *,
             blocker: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def note(self, msg: str, ctx: Context) -> None:
        raise NotImplementedError

    @abstractmethod
    def dereference_module_cross_ref(
            self, node: Optional[SymbolTableNode]) -> Optional[SymbolTableNode]:
        raise NotImplementedError


@trait
class SemanticAnalyzerInterface(SemanticAnalyzerCoreInterface):
    """A limited abstract interface to some generic semantic analyzer pass 2 functionality.

    We use this interface for various reasons:

    * Looser coupling
    * Cleaner import graph
    * Less need to pass around callback functions
    """

    @abstractmethod
    def lookup(self, name: str, ctx: Context,
               suppress_errors: bool = False) -> Optional[SymbolTableNode]:
        raise NotImplementedError

    @abstractmethod
    def named_type(self, qualified_name: str, args: Optional[List[Type]] = None) -> Instance:
        raise NotImplementedError

    @abstractmethod
    def named_type_or_none(self, qualified_name: str,
                           args: Optional[List[Type]] = None) -> Optional[Instance]:
        raise NotImplementedError

    @abstractmethod
    def accept(self, node: Node) -> None:
        raise NotImplementedError

    @abstractmethod
    def anal_type(self, t: Type, *,
                  tvar_scope: Optional[TypeVarScope] = None,
                  allow_tuple_literal: bool = False,
                  allow_unbound_tvars: bool = False,
                  report_invalid_types: bool = True,
                  third_pass: bool = False) -> Type:
        raise NotImplementedError

    @abstractmethod
    def basic_new_typeinfo(self, name: str, basetype_or_fallback: Instance) -> TypeInfo:
        raise NotImplementedError

    @abstractmethod
    def schedule_patch(self, priority: int, fn: Callable[[], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_symbol_table_node(self, name: str, stnode: SymbolTableNode) -> None:
        """Add node to global symbol table (or to nearest class if there is one)."""
        raise NotImplementedError

    @abstractmethod
    def parse_bool(self, expr: Expression) -> Optional[bool]:
        raise NotImplementedError

    @abstractmethod
    def qualified_name(self, n: str) -> str:
        raise NotImplementedError

    @abstractproperty
    def is_typeshed_stub_file(self) -> bool:
        raise NotImplementedError


def create_indirect_imported_name(file_node: MypyFile,
                                  module: str,
                                  relative: int,
                                  imported_name: str) -> Optional[SymbolTableNode]:
    """Create symbol table entry for a name imported from another module.

    These entries act as indirect references.
    """
    target_module, ok = correct_relative_import(
        file_node.fullname(),
        relative,
        module,
        file_node.is_package_init_file())
    if not ok:
        return None
    target_name = '%s.%s' % (target_module, imported_name)
    link = ImportedName(target_name)
    # Use GDEF since this refers to a module-level definition.
    return SymbolTableNode(GDEF, link)


def set_callable_name(sig: Type, fdef: FuncDef) -> Type:
    if isinstance(sig, FunctionLike):
        if fdef.info:
            if fdef.info.fullname() == 'mypy_extensions._TypedDict':
                # Avoid exposing the internal _TypedDict name.
                class_name = 'TypedDict'
            else:
                class_name = fdef.info.name()
            return sig.with_name(
                '{} of {}'.format(fdef.name(), class_name))
        else:
            return sig.with_name(fdef.name())
    else:
        return sig
