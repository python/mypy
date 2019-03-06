"""Type visitor classes.

This module defines the type visitors that are intended to be
subclassed by other code.  They have been separated out into their own
module to ease converting mypy to run under mypyc, since currently
mypyc-extension classes can extend interpreted classes but not the
other way around. Separating them out, then, allows us to compile
types before we can compile everything that uses a TypeVisitor.

The visitors are all re-exported from mypy.types and that is how
other modules refer to them.
"""

from abc import abstractmethod
from collections import OrderedDict
from typing import Generic, TypeVar, cast, Any, List, Callable, Iterable, Optional
from mypy_extensions import trait

T = TypeVar('T')

from mypy.types import (
    Type, AnyType, CallableType, Overloaded, TupleType, TypedDictType, LiteralType,
    RawExpressionType, Instance, NoneTyp, TypeType,
    UnionType, TypeVarType, PartialType, DeletedType, UninhabitedType, TypeVarDef,
    UnboundType, ErasedType, ForwardRef, StarType, EllipsisType, TypeList, CallableArgument,
    PlaceholderType,
)


@trait
class TypeVisitor(Generic[T]):
    """Visitor class for types (Type subclasses).

    The parameter T is the return type of the visit methods.
    """

    def _notimplemented_helper(self, name: str) -> NotImplementedError:
        return NotImplementedError("Method {}.visit_{}() not implemented\n"
                                   .format(type(self).__name__, name)
                                   + "This is a known bug, track development in "
                                   + "'https://github.com/JukkaL/mypy/issues/730'")

    @abstractmethod
    def visit_unbound_type(self, t: UnboundType) -> T:
        pass

    @abstractmethod
    def visit_any(self, t: AnyType) -> T:
        pass

    @abstractmethod
    def visit_none_type(self, t: NoneTyp) -> T:
        pass

    @abstractmethod
    def visit_uninhabited_type(self, t: UninhabitedType) -> T:
        pass

    def visit_erased_type(self, t: ErasedType) -> T:
        raise self._notimplemented_helper('erased_type')

    @abstractmethod
    def visit_deleted_type(self, t: DeletedType) -> T:
        pass

    @abstractmethod
    def visit_type_var(self, t: TypeVarType) -> T:
        pass

    @abstractmethod
    def visit_instance(self, t: Instance) -> T:
        pass

    @abstractmethod
    def visit_callable_type(self, t: CallableType) -> T:
        pass

    def visit_overloaded(self, t: Overloaded) -> T:
        raise self._notimplemented_helper('overloaded')

    @abstractmethod
    def visit_tuple_type(self, t: TupleType) -> T:
        pass

    @abstractmethod
    def visit_typeddict_type(self, t: TypedDictType) -> T:
        pass

    @abstractmethod
    def visit_literal_type(self, t: LiteralType) -> T:
        pass

    @abstractmethod
    def visit_union_type(self, t: UnionType) -> T:
        pass

    @abstractmethod
    def visit_partial_type(self, t: PartialType) -> T:
        pass

    @abstractmethod
    def visit_type_type(self, t: TypeType) -> T:
        pass

    def visit_forwardref_type(self, t: ForwardRef) -> T:
        raise RuntimeError('Internal error: unresolved forward reference')

    def visit_placeholder_type(self, t: PlaceholderType) -> T:
        raise RuntimeError('Internal error: unresolved placeholder type {}'.format(t.fullname))


@trait
class SyntheticTypeVisitor(TypeVisitor[T]):
    """A TypeVisitor that also knows how to visit synthetic AST constructs.

       Not just real types."""

    @abstractmethod
    def visit_star_type(self, t: StarType) -> T:
        pass

    @abstractmethod
    def visit_type_list(self, t: TypeList) -> T:
        pass

    @abstractmethod
    def visit_callable_argument(self, t: CallableArgument) -> T:
        pass

    @abstractmethod
    def visit_ellipsis_type(self, t: EllipsisType) -> T:
        pass

    @abstractmethod
    def visit_raw_expression_type(self, t: RawExpressionType) -> T:
        pass


@trait
class TypeTranslator(TypeVisitor[Type]):
    """Identity type transformation.

    Subclass this and override some methods to implement a non-trivial
    transformation.
    """

    def visit_unbound_type(self, t: UnboundType) -> Type:
        return t

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_erased_type(self, t: ErasedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_instance(self, t: Instance) -> Type:
        final_value = None  # type: Optional[LiteralType]
        if t.final_value is not None:
            raw_final_value = t.final_value.accept(self)
            assert isinstance(raw_final_value, LiteralType)
            final_value = raw_final_value
        return Instance(
            typ=t.type,
            args=self.translate_types(t.args),
            line=t.line,
            column=t.column,
            final_value=final_value,
        )

    def visit_type_var(self, t: TypeVarType) -> Type:
        return t

    def visit_partial_type(self, t: PartialType) -> Type:
        return t

    def visit_callable_type(self, t: CallableType) -> Type:
        return t.copy_modified(arg_types=self.translate_types(t.arg_types),
                               ret_type=t.ret_type.accept(self),
                               variables=self.translate_variables(t.variables))

    def visit_tuple_type(self, t: TupleType) -> Type:
        return TupleType(self.translate_types(t.items),
                         # TODO: This appears to be unsafe.
                         cast(Any, t.partial_fallback.accept(self)),
                         t.line, t.column)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        items = OrderedDict([
            (item_name, item_type.accept(self))
            for (item_name, item_type) in t.items.items()
        ])
        return TypedDictType(items,
                             t.required_keys,
                             # TODO: This appears to be unsafe.
                             cast(Any, t.fallback.accept(self)),
                             t.line, t.column)

    def visit_literal_type(self, t: LiteralType) -> Type:
        fallback = t.fallback.accept(self)
        assert isinstance(fallback, Instance)
        return LiteralType(
            value=t.value,
            fallback=fallback,
            line=t.line,
            column=t.column,
        )

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.translate_types(t.items), t.line, t.column)

    def translate_types(self, types: List[Type]) -> List[Type]:
        return [t.accept(self) for t in types]

    def translate_variables(self,
                            variables: List[TypeVarDef]) -> List[TypeVarDef]:
        return variables

    def visit_overloaded(self, t: Overloaded) -> Type:
        items = []  # type: List[CallableType]
        for item in t.items():
            new = item.accept(self)
            if isinstance(new, CallableType):
                items.append(new)
            else:
                raise RuntimeError('CallableType expected, but got {}'.format(type(new)))
        return Overloaded(items=items)

    def visit_type_type(self, t: TypeType) -> Type:
        return TypeType.make_normalized(t.item.accept(self), line=t.line, column=t.column)

    def visit_forwardref_type(self, t: ForwardRef) -> Type:
        return t

    def visit_placeholder_type(self, t: PlaceholderType) -> Type:
        return PlaceholderType(t.fullname, self.translate_types(t.args), t.line)


@trait
class TypeQuery(SyntheticTypeVisitor[T]):
    """Visitor for performing queries of types.

    strategy is used to combine results for a series of types

    Common use cases involve a boolean query using `any` or `all`
    """

    def __init__(self, strategy: Callable[[Iterable[T]], T]) -> None:
        self.strategy = strategy
        self.seen = []  # type: List[Type]

    def visit_unbound_type(self, t: UnboundType) -> T:
        return self.query_types(t.args)

    def visit_type_list(self, t: TypeList) -> T:
        return self.query_types(t.items)

    def visit_callable_argument(self, t: CallableArgument) -> T:
        return t.typ.accept(self)

    def visit_any(self, t: AnyType) -> T:
        return self.strategy([])

    def visit_uninhabited_type(self, t: UninhabitedType) -> T:
        return self.strategy([])

    def visit_none_type(self, t: NoneTyp) -> T:
        return self.strategy([])

    def visit_erased_type(self, t: ErasedType) -> T:
        return self.strategy([])

    def visit_deleted_type(self, t: DeletedType) -> T:
        return self.strategy([])

    def visit_type_var(self, t: TypeVarType) -> T:
        return self.strategy([])

    def visit_partial_type(self, t: PartialType) -> T:
        return self.query_types(t.inner_types)

    def visit_instance(self, t: Instance) -> T:
        return self.query_types(t.args)

    def visit_callable_type(self, t: CallableType) -> T:
        # FIX generics
        return self.query_types(t.arg_types + [t.ret_type])

    def visit_tuple_type(self, t: TupleType) -> T:
        return self.query_types(t.items)

    def visit_typeddict_type(self, t: TypedDictType) -> T:
        return self.query_types(t.items.values())

    def visit_raw_expression_type(self, t: RawExpressionType) -> T:
        return self.strategy([])

    def visit_literal_type(self, t: LiteralType) -> T:
        return self.strategy([])

    def visit_star_type(self, t: StarType) -> T:
        return t.type.accept(self)

    def visit_union_type(self, t: UnionType) -> T:
        return self.query_types(t.items)

    def visit_overloaded(self, t: Overloaded) -> T:
        return self.query_types(t.items())

    def visit_type_type(self, t: TypeType) -> T:
        return t.item.accept(self)

    def visit_forwardref_type(self, t: ForwardRef) -> T:
        if t.resolved:
            return t.resolved.accept(self)
        else:
            return t.unbound.accept(self)

    def visit_ellipsis_type(self, t: EllipsisType) -> T:
        return self.strategy([])

    def visit_placeholder_type(self, t: PlaceholderType) -> T:
        return self.query_types(t.args)

    def query_types(self, types: Iterable[Type]) -> T:
        """Perform a query for a list of types.

        Use the strategy to combine the results.
        Skip types already visited types to avoid infinite recursion.
        Note: types can be recursive until they are fully analyzed and "unentangled"
        in patches after the semantic analysis.
        """
        res = []  # type: List[T]
        for t in types:
            if any(t is s for s in self.seen):
                continue
            self.seen.append(t)
            res.append(t.accept(self))
        return self.strategy(res)
