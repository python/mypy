"""Shared definitions used by different parts of semantic analysis."""

from abc import abstractmethod

from typing import Optional, List, Callable, Union
from typing_extensions import Final, Protocol
from mypy_extensions import trait

from mypy.nodes import (
    Context, SymbolTableNode, FuncDef, Node, TypeInfo, Expression,
    SymbolNode, SymbolTable
)
from mypy.types import (
    Type, FunctionLike, Instance, TupleType, TPDICT_FB_NAMES, ProperType, get_proper_type,
    ParamSpecType, ParamSpecFlavor, Parameters, TypeVarId
)
from mypy.tvar_scope import TypeVarLikeScope
from mypy.errorcodes import ErrorCode
from mypy import join

# Priorities for ordering of patches within the "patch" phase of semantic analysis
# (after the main pass):

# Fix fallbacks (does joins)
PRIORITY_FALLBACKS: Final = 1


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
    def lookup_fully_qualified_or_none(self, name: str) -> Optional[SymbolTableNode]:
        raise NotImplementedError

    @abstractmethod
    def fail(self, msg: str, ctx: Context, serious: bool = False, *,
             blocker: bool = False, code: Optional[ErrorCode] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def note(self, msg: str, ctx: Context, *, code: Optional[ErrorCode] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def record_incomplete_ref(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def defer(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_incomplete_namespace(self, fullname: str) -> bool:
        """Is a module or class namespace potentially missing some definitions?"""
        raise NotImplementedError

    @property
    @abstractmethod
    def final_iteration(self) -> bool:
        """Is this the final iteration of semantic analysis?"""
        raise NotImplementedError

    @abstractmethod
    def is_future_flag_set(self, flag: str) -> bool:
        """Is the specific __future__ feature imported"""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_stub_file(self) -> bool:
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
    def named_type(self, fullname: str,
                   args: Optional[List[Type]] = None) -> Instance:
        raise NotImplementedError

    @abstractmethod
    def named_type_or_none(self, fullname: str,
                           args: Optional[List[Type]] = None) -> Optional[Instance]:
        raise NotImplementedError

    @abstractmethod
    def accept(self, node: Node) -> None:
        raise NotImplementedError

    @abstractmethod
    def anal_type(self, t: Type, *,
                  tvar_scope: Optional[TypeVarLikeScope] = None,
                  allow_tuple_literal: bool = False,
                  allow_unbound_tvars: bool = False,
                  allow_required: bool = False,
                  report_invalid_types: bool = True) -> Optional[Type]:
        raise NotImplementedError

    @abstractmethod
    def basic_new_typeinfo(self, name: str, basetype_or_fallback: Instance, line: int) -> TypeInfo:
        raise NotImplementedError

    @abstractmethod
    def schedule_patch(self, priority: int, fn: Callable[[], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_symbol_table_node(self, name: str, stnode: SymbolTableNode) -> bool:
        """Add node to the current symbol table."""
        raise NotImplementedError

    @abstractmethod
    def current_symbol_table(self) -> SymbolTable:
        """Get currently active symbol table.

        May be module, class, or local namespace.
        """
        raise NotImplementedError

    @abstractmethod
    def add_symbol(self, name: str, node: SymbolNode, context: Context,
                   module_public: bool = True, module_hidden: bool = False,
                   can_defer: bool = True) -> bool:
        """Add symbol to the current symbol table."""
        raise NotImplementedError

    @abstractmethod
    def add_symbol_skip_local(self, name: str, node: SymbolNode) -> None:
        """Add symbol to the current symbol table, skipping locals.

        This is used to store symbol nodes in a symbol table that
        is going to be serialized (local namespaces are not serialized).
        See implementation docstring for more details.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_bool(self, expr: Expression) -> Optional[bool]:
        raise NotImplementedError

    @abstractmethod
    def qualified_name(self, n: str) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_typeshed_stub_file(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_func_scope(self) -> bool:
        raise NotImplementedError


def set_callable_name(sig: Type, fdef: FuncDef) -> ProperType:
    sig = get_proper_type(sig)
    if isinstance(sig, FunctionLike):
        if fdef.info:
            if fdef.info.fullname in TPDICT_FB_NAMES:
                # Avoid exposing the internal _TypedDict name.
                class_name = 'TypedDict'
            else:
                class_name = fdef.info.name
            return sig.with_name(
                f'{fdef.name} of {class_name}')
        else:
            return sig.with_name(fdef.name)
    else:
        return sig


def calculate_tuple_fallback(typ: TupleType) -> None:
    """Calculate a precise item type for the fallback of a tuple type.

    This must be called only after the main semantic analysis pass, since joins
    aren't available before that.

    Note that there is an apparent chicken and egg problem with respect
    to verifying type arguments against bounds. Verifying bounds might
    require fallbacks, but we might use the bounds to calculate the
    fallbacks. In practice this is not a problem, since the worst that
    can happen is that we have invalid type argument values, and these
    can happen in later stages as well (they will generate errors, but
    we don't prevent their existence).
    """
    fallback = typ.partial_fallback
    assert fallback.type.fullname == 'builtins.tuple'
    fallback.args = (join.join_type_list(list(typ.items)),) + fallback.args[1:]


class _NamedTypeCallback(Protocol):
    def __call__(
        self, fully_qualified_name: str, args: Optional[List[Type]] = None
    ) -> Instance: ...


def paramspec_args(
    name: str, fullname: str, id: Union[TypeVarId, int], *,
    named_type_func: _NamedTypeCallback, line: int = -1, column: int = -1,
    prefix: Optional[Parameters] = None
) -> ParamSpecType:
    return ParamSpecType(
        name,
        fullname,
        id,
        flavor=ParamSpecFlavor.ARGS,
        upper_bound=named_type_func('builtins.tuple', [named_type_func('builtins.object')]),
        line=line,
        column=column,
        prefix=prefix
    )


def paramspec_kwargs(
    name: str, fullname: str, id: Union[TypeVarId, int], *,
    named_type_func: _NamedTypeCallback, line: int = -1, column: int = -1,
    prefix: Optional[Parameters] = None
) -> ParamSpecType:
    return ParamSpecType(
        name,
        fullname,
        id,
        flavor=ParamSpecFlavor.KWARGS,
        upper_bound=named_type_func(
            'builtins.dict',
            [named_type_func('builtins.str'), named_type_func('builtins.object')]
        ),
        line=line,
        column=column,
        prefix=prefix
    )
