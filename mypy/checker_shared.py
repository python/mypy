"""Shared definitions used by different parts of mypy type checker."""

from abc import abstractmethod

from mypy_extensions import trait

from mypy.errorcodes import ErrorCode
from mypy.message_registry import ErrorMessage
from mypy.nodes import Context, Expression, SymbolTableNode, TypeInfo, Var
from mypy.types import CallableType, Instance, Overloaded, PartialType, Type, TypeType


@trait
class CheckerCoreInterface:
    """
    A core abstract interface to generic type checker functionality.
    """

    @abstractmethod
    def fail(
        self, msg: str | ErrorMessage, ctx: Context, *, code: ErrorCode | None = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def note(
        self,
        msg: str | ErrorMessage,
        context: Context,
        offset: int = 0,
        *,
        code: ErrorCode | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def lookup(self, name: str) -> SymbolTableNode:
        raise NotImplementedError

    @abstractmethod
    def lookup_qualified(self, name: str) -> SymbolTableNode:
        raise NotImplementedError

    @abstractmethod
    def lookup_typeinfo(self, fullname: str) -> TypeInfo:
        raise NotImplementedError

    @abstractmethod
    def lookup_type_or_none(self, node: Expression) -> Type | None:
        raise NotImplementedError

    @abstractmethod
    def lookup_type(self, node: Expression) -> Type:
        raise NotImplementedError


@trait
class TypeCheckerInterface:
    @abstractmethod
    def handle_partial_var_type(
        self, typ: PartialType, is_lvalue: bool, node: Var, context: Context
    ) -> Type:
        raise NotImplementedError

    @abstractmethod
    def handle_cannot_determine_type(self, name: str, context: Context) -> None:
        raise NotImplementedError

    @abstractmethod
    def named_type(self, name: str) -> Instance:
        raise NotImplementedError

    @abstractmethod
    def type_is_iterable(self, type: Type) -> bool:
        raise NotImplementedError

    @abstractmethod
    def iterable_item_type(
        self, it: Instance | CallableType | TypeType | Overloaded, context: Context
    ) -> Type:
        raise NotImplementedError

    @abstractmethod
    def named_generic_type(self, name: str, args: list[Type]) -> Instance:
        raise NotImplementedError
