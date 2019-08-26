"""Miscellaneuus type operations and helpers for use during type checking.

NOTE: These must not be accessed from mypy.nodes or mypy.types to avoid import
      cycles. These must not be called from the semantic analysis main pass
      since these may assume that MROs are ready.
"""

# TODO: Move more type operations here

from typing import cast, Optional, List

from mypy.types import (
    TupleType, Instance, FunctionLike, Type, CallableType, TypeVarDef, Overloaded,
    TypeVarType, TypeType, UninhabitedType, FormalArgument,
    get_proper_type,
)
from mypy.nodes import (
    TypeInfo, TypeVar, ARG_STAR,
)
from mypy.maptype import map_instance_to_supertype
from mypy.expandtype import expand_type_by_instance, expand_type

from mypy.typevars import fill_typevars

def tuple_fallback(typ: TupleType) -> Instance:
    """Return fallback type for a tuple."""
    from mypy.join import join_type_list

    info = typ.partial_fallback.type
    if info.fullname() != 'builtins.tuple':
        return typ.partial_fallback
    return Instance(info, [join_type_list(typ.items)])


def type_object_type_from_function(signature: FunctionLike,
                                   info: TypeInfo,
                                   def_info: TypeInfo,
                                   fallback: Instance,
                                   is_new: bool) -> FunctionLike:
    # The __init__ method might come from a generic superclass
    # (init_or_new.info) with type variables that do not map
    # identically to the type variables of the class being constructed
    # (info). For example
    #
    #   class A(Generic[T]): def __init__(self, x: T) -> None: pass
    #   class B(A[List[T]], Generic[T]): pass
    #
    # We need to first map B's __init__ to the type (List[T]) -> None.
    signature = bind_self(signature, original_type=fill_typevars(info), is_classmethod=is_new)
    signature = cast(FunctionLike,
                     map_type_from_supertype(signature, info, def_info))
    special_sig = None  # type: Optional[str]
    if def_info.fullname() == 'builtins.dict':
        # Special signature!
        special_sig = 'dict'

    if isinstance(signature, CallableType):
        return class_callable(signature, info, fallback, special_sig, is_new)
    else:
        # Overloaded __init__/__new__.
        assert isinstance(signature, Overloaded)
        items = []  # type: List[CallableType]
        for item in signature.items():
            items.append(class_callable(item, info, fallback, special_sig, is_new))
        return Overloaded(items)


def class_callable(init_type: CallableType, info: TypeInfo, type_type: Instance,
                   special_sig: Optional[str],
                   is_new: bool) -> CallableType:
    """Create a type object type based on the signature of __init__."""
    variables = []  # type: List[TypeVarDef]
    variables.extend(info.defn.type_vars)
    variables.extend(init_type.variables)

    init_ret_type = get_proper_type(init_type.ret_type)
    if is_new and isinstance(init_ret_type, (Instance, TupleType)):
        ret_type = init_type.ret_type  # type: Type
    else:
        ret_type = fill_typevars(info)

    callable_type = init_type.copy_modified(
        ret_type=ret_type, fallback=type_type, name=None, variables=variables,
        special_sig=special_sig)
    c = callable_type.with_name(info.name())
    return c


def map_type_from_supertype(typ: Type,
                            sub_info: TypeInfo,
                            super_info: TypeInfo) -> Type:
    """Map type variables in a type defined in a supertype context to be valid
    in the subtype context. Assume that the result is unique; if more than
    one type is possible, return one of the alternatives.

    For example, assume

    . class D(Generic[S]) ...
    . class C(D[E[T]], Generic[T]) ...

    Now S in the context of D would be mapped to E[T] in the context of C.
    """
    # Create the type of self in subtype, of form t[a1, ...].
    inst_type = fill_typevars(sub_info)
    if isinstance(inst_type, TupleType):
        inst_type = tuple_fallback(inst_type)
    # Map the type of self to supertype. This gets us a description of the
    # supertype type variables in terms of subtype variables, i.e. t[t1, ...]
    # so that any type variables in tN are to be interpreted in subtype
    # context.
    inst_type = map_instance_to_supertype(inst_type, super_info)
    # Finally expand the type variables in type with those in the previously
    # constructed type. Note that both type and inst_type may have type
    # variables, but in type they are interpreted in supertype context while
    # in inst_type they are interpreted in subtype context. This works even if
    # the names of type variables in supertype and subtype overlap.
    return expand_type_by_instance(typ, inst_type)


F = TypeVar('F', bound=FunctionLike)


def bind_self(method: F, original_type: Optional[Type] = None, is_classmethod: bool = False) -> F:
    """Return a copy of `method`, with the type of its first parameter (usually
    self or cls) bound to original_type.

    If the type of `self` is a generic type (T, or Type[T] for classmethods),
    instantiate every occurrence of type with original_type in the rest of the
    signature and in the return type.

    original_type is the type of E in the expression E.copy(). It is None in
    compatibility checks. In this case we treat it as the erasure of the
    declared type of self.

    This way we can express "the type of self". For example:

    T = TypeVar('T', bound='A')
    class A:
        def copy(self: T) -> T: ...

    class B(A): pass

    b = B().copy()  # type: B

    """
    from mypy.infer import infer_type_arguments

    if isinstance(method, Overloaded):
        return cast(F, Overloaded([bind_self(c, original_type) for c in method.items()]))
    assert isinstance(method, CallableType)
    func = method
    if not func.arg_types:
        # invalid method. return something
        return cast(F, func)
    if func.arg_kinds[0] == ARG_STAR:
        # The signature is of the form 'def foo(*args, ...)'.
        # In this case we shouldn't drop the first arg,
        # since func will be absorbed by the *args.

        # TODO: infer bounds on the type of *args?
        return cast(F, func)
    self_param_type = get_proper_type(func.arg_types[0])
    if func.variables and (isinstance(self_param_type, TypeVarType) or
                           (isinstance(self_param_type, TypeType) and
                            isinstance(self_param_type.item, TypeVarType))):
        if original_type is None:
            # Type check method override
            # XXX value restriction as union?
            original_type = erase_to_bound(self_param_type)
        original_type = get_proper_type(original_type)

        ids = [x.id for x in func.variables]
        typearg = get_proper_type(infer_type_arguments(ids, self_param_type, original_type)[0])
        if (is_classmethod and isinstance(typearg, UninhabitedType)
                and isinstance(original_type, (Instance, TypeVarType, TupleType))):
            # In case we call a classmethod through an instance x, fallback to type(x)
            # TODO: handle Union
            typearg = get_proper_type(infer_type_arguments(ids, self_param_type,
                                                           TypeType(original_type))[0])

        def expand(target: Type) -> Type:
            assert typearg is not None
            return expand_type(target, {func.variables[0].id: typearg})

        arg_types = [expand(x) for x in func.arg_types[1:]]
        ret_type = expand(func.ret_type)
        variables = func.variables[1:]
    else:
        arg_types = func.arg_types[1:]
        ret_type = func.ret_type
        variables = func.variables

    original_type = get_proper_type(original_type)
    if isinstance(original_type, CallableType) and original_type.is_type_obj():
        original_type = TypeType.make_normalized(original_type.ret_type)
    res = func.copy_modified(arg_types=arg_types,
                             arg_kinds=func.arg_kinds[1:],
                             arg_names=func.arg_names[1:],
                             variables=variables,
                             ret_type=ret_type,
                             bound_args=[original_type])
    return cast(F, res)


def erase_to_bound(t: Type) -> Type:
    t = get_proper_type(t)
    if isinstance(t, TypeVarType):
        return t.upper_bound
    if isinstance(t, TypeType):
        if isinstance(t.item, TypeVarType):
            return TypeType.make_normalized(t.item.upper_bound)
    return t


def callable_corresponding_argument(typ: CallableType,
                                    model: FormalArgument) -> Optional[FormalArgument]:
    """Return the argument a function that corresponds to `model`"""

    by_name = typ.argument_by_name(model.name)
    by_pos = typ.argument_by_position(model.pos)
    if by_name is None and by_pos is None:
        return None
    if by_name is not None and by_pos is not None:
        if by_name == by_pos:
            return by_name
        # If we're dealing with an optional pos-only and an optional
        # name-only arg, merge them.  This is the case for all functions
        # taking both *args and **args, or a pair of functions like so:

        # def right(a: int = ...) -> None: ...
        # def left(__a: int = ..., *, a: int = ...) -> None: ...
        from mypy.subtypes import is_equivalent

        if (not (by_name.required or by_pos.required)
                and by_pos.name is None
                and by_name.pos is None
                and is_equivalent(by_name.typ, by_pos.typ)):
            return FormalArgument(by_name.name, by_pos.pos, by_name.typ, False)
    return by_name if by_name is not None else by_pos
