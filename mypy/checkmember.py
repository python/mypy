"""Type checking of attribute access"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Callable, cast

from mypy import message_registry, subtypes
from mypy.erasetype import erase_typevars
from mypy.expandtype import (
    expand_self_type,
    expand_type_by_instance,
    freshen_all_functions_type_vars,
)
from mypy.maptype import map_instance_to_supertype
from mypy.messages import MessageBuilder
from mypy.nodes import (
    ARG_POS,
    ARG_STAR,
    ARG_STAR2,
    EXCLUDED_ENUM_ATTRIBUTES,
    SYMBOL_FUNCBASE_TYPES,
    ArgKind,
    Context,
    Decorator,
    FuncBase,
    FuncDef,
    IndexExpr,
    MypyFile,
    NameExpr,
    OverloadedFuncDef,
    SymbolNode,
    SymbolTable,
    TempNode,
    TypeAlias,
    TypeInfo,
    TypeVarExpr,
    Var,
    is_final_node,
)
from mypy.plugin import AttributeContext
from mypy.typeops import (
    bind_self,
    class_callable,
    erase_to_bound,
    function_type,
    get_type_vars,
    make_simplified_union,
    supported_self_type,
    tuple_fallback,
    type_object_type_from_function,
)
from mypy.types import (
    AnyType,
    CallableType,
    DeletedType,
    FunctionLike,
    Instance,
    LiteralType,
    NoneType,
    Overloaded,
    ParamSpecType,
    PartialType,
    ProperType,
    TupleType,
    Type,
    TypedDictType,
    TypeOfAny,
    TypeType,
    TypeVarLikeType,
    TypeVarTupleType,
    TypeVarType,
    UninhabitedType,
    UnionType,
    get_proper_type,
)
from mypy.typetraverser import TypeTraverserVisitor

if TYPE_CHECKING:  # import for forward declaration only
    import mypy.checker

from mypy import state


class MemberContext:
    """Information and objects needed to type check attribute access.

    Look at the docstring of analyze_member_access for more information.
    """

    def __init__(
        self,
        *,
        is_lvalue: bool,
        is_super: bool,
        is_operator: bool,
        original_type: Type,
        context: Context,
        msg: MessageBuilder,
        chk: mypy.checker.TypeChecker,
        self_type: Type | None,
        module_symbol_table: SymbolTable | None = None,
        no_deferral: bool = False,
        is_self: bool = False,
    ) -> None:
        self.is_lvalue = is_lvalue
        self.is_super = is_super
        self.is_operator = is_operator
        self.original_type = original_type
        self.self_type = self_type or original_type
        self.context = context  # Error context
        self.msg = msg
        self.chk = chk
        self.module_symbol_table = module_symbol_table
        self.no_deferral = no_deferral
        self.is_self = is_self

    def named_type(self, name: str) -> Instance:
        return self.chk.named_type(name)

    def not_ready_callback(self, name: str, context: Context) -> None:
        self.chk.handle_cannot_determine_type(name, context)

    def copy_modified(
        self,
        *,
        messages: MessageBuilder | None = None,
        self_type: Type | None = None,
        is_lvalue: bool | None = None,
        original_type: Type | None = None,
    ) -> MemberContext:
        mx = MemberContext(
            is_lvalue=self.is_lvalue,
            is_super=self.is_super,
            is_operator=self.is_operator,
            original_type=self.original_type,
            context=self.context,
            msg=self.msg,
            chk=self.chk,
            self_type=self.self_type,
            module_symbol_table=self.module_symbol_table,
            no_deferral=self.no_deferral,
        )
        if messages is not None:
            mx.msg = messages
        if self_type is not None:
            mx.self_type = self_type
        if is_lvalue is not None:
            mx.is_lvalue = is_lvalue
        if original_type is not None:
            mx.original_type = original_type
        return mx


def analyze_member_access(
    name: str,
    typ: Type,
    context: Context,
    *,
    is_lvalue: bool,
    is_super: bool,
    is_operator: bool,
    msg: MessageBuilder,
    original_type: Type,
    chk: mypy.checker.TypeChecker,
    override_info: TypeInfo | None = None,
    in_literal_context: bool = False,
    self_type: Type | None = None,
    module_symbol_table: SymbolTable | None = None,
    no_deferral: bool = False,
    is_self: bool = False,
) -> Type:
    """Return the type of attribute 'name' of 'typ'.

    The actual implementation is in '_analyze_member_access' and this docstring
    also applies to it.

    This is a general operation that supports various different variations:

      1. lvalue or non-lvalue access (setter or getter access)
      2. supertype access when using super() (is_super == True and
         'override_info' should refer to the supertype)

    'original_type' is the most precise inferred or declared type of the base object
    that we have available. When looking for an attribute of 'typ', we may perform
    recursive calls targeting the fallback type, and 'typ' may become some supertype
    of 'original_type'. 'original_type' is always preserved as the 'typ' type used in
    the initial, non-recursive call. The 'self_type' is a component of 'original_type'
    to which generic self should be bound (a narrower type that has a fallback to instance).
    Currently this is used only for union types.

    'module_symbol_table' is passed to this function if 'typ' is actually a module
    and we want to keep track of the available attributes of the module (since they
    are not available via the type object directly)
    """
    mx = MemberContext(
        is_lvalue=is_lvalue,
        is_super=is_super,
        is_operator=is_operator,
        original_type=original_type,
        context=context,
        msg=msg,
        chk=chk,
        self_type=self_type,
        module_symbol_table=module_symbol_table,
        no_deferral=no_deferral,
        is_self=is_self,
    )
    result = _analyze_member_access(name, typ, mx, override_info)
    possible_literal = get_proper_type(result)
    if (
        in_literal_context
        and isinstance(possible_literal, Instance)
        and possible_literal.last_known_value is not None
    ):
        return possible_literal.last_known_value
    else:
        return result


def _analyze_member_access(
    name: str, typ: Type, mx: MemberContext, override_info: TypeInfo | None = None
) -> Type:
    # TODO: This and following functions share some logic with subtypes.find_member;
    #       consider refactoring.
    typ = get_proper_type(typ)
    if isinstance(typ, Instance):
        return analyze_instance_member_access(name, typ, mx, override_info)
    elif isinstance(typ, AnyType):
        # The base object has dynamic type.
        return AnyType(TypeOfAny.from_another_any, source_any=typ)
    elif isinstance(typ, UnionType):
        return analyze_union_member_access(name, typ, mx)
    elif isinstance(typ, FunctionLike) and typ.is_type_obj():
        return analyze_type_callable_member_access(name, typ, mx)
    elif isinstance(typ, TypeType):
        return analyze_type_type_member_access(name, typ, mx, override_info)
    elif isinstance(typ, TupleType):
        # Actually look up from the fallback instance type.
        return _analyze_member_access(name, tuple_fallback(typ), mx, override_info)
    elif isinstance(typ, (LiteralType, FunctionLike)):
        # Actually look up from the fallback instance type.
        return _analyze_member_access(name, typ.fallback, mx, override_info)
    elif isinstance(typ, TypedDictType):
        return analyze_typeddict_access(name, typ, mx, override_info)
    elif isinstance(typ, NoneType):
        return analyze_none_member_access(name, typ, mx)
    elif isinstance(typ, TypeVarLikeType):
        if isinstance(typ, TypeVarType) and typ.values:
            return _analyze_member_access(
                name, make_simplified_union(typ.values), mx, override_info
            )
        return _analyze_member_access(name, typ.upper_bound, mx, override_info)
    elif isinstance(typ, DeletedType):
        mx.msg.deleted_as_rvalue(typ, mx.context)
        return AnyType(TypeOfAny.from_error)
    elif isinstance(typ, UninhabitedType):
        return UninhabitedType()
    return report_missing_attribute(mx.original_type, typ, name, mx)


def may_be_awaitable_attribute(
    name: str, typ: Type, mx: MemberContext, override_info: TypeInfo | None = None
) -> bool:
    """Check if the given type has the attribute when awaited."""
    if mx.chk.checking_missing_await:
        # Avoid infinite recursion.
        return False
    with mx.chk.checking_await_set(), mx.msg.filter_errors() as local_errors:
        aw_type = mx.chk.get_precise_awaitable_type(typ, local_errors)
        if aw_type is None:
            return False
        _ = _analyze_member_access(
            name, aw_type, mx.copy_modified(self_type=aw_type), override_info
        )
        return not local_errors.has_new_errors()


def report_missing_attribute(
    original_type: Type,
    typ: Type,
    name: str,
    mx: MemberContext,
    override_info: TypeInfo | None = None,
) -> Type:
    error_code = mx.msg.has_no_attr(original_type, typ, name, mx.context, mx.module_symbol_table)
    if not mx.msg.prefer_simple_messages():
        if may_be_awaitable_attribute(name, typ, mx, override_info):
            mx.msg.possible_missing_await(mx.context, error_code)
    return AnyType(TypeOfAny.from_error)


# The several functions that follow implement analyze_member_access for various
# types and aren't documented individually.


def analyze_instance_member_access(
    name: str, typ: Instance, mx: MemberContext, override_info: TypeInfo | None
) -> Type:
    if name == "__init__" and not mx.is_super:
        # Accessing __init__ in statically typed code would compromise
        # type safety unless used via super().
        mx.msg.fail(message_registry.CANNOT_ACCESS_INIT, mx.context)
        return AnyType(TypeOfAny.from_error)

    # The base object has an instance type.

    info = typ.type
    if override_info:
        info = override_info

    if (
        state.find_occurrences
        and info.name == state.find_occurrences[0]
        and name == state.find_occurrences[1]
    ):
        mx.msg.note("Occurrence of '{}.{}'".format(*state.find_occurrences), mx.context)

    # Look up the member. First look up the method dictionary.
    method = info.get_method(name)
    if method and not isinstance(method, Decorator):
        if mx.is_super:
            validate_super_call(method, mx)

        if method.is_property:
            assert isinstance(method, OverloadedFuncDef)
            getter = method.items[0]
            assert isinstance(getter, Decorator)
            if mx.is_lvalue and (len(items := method.items) > 1):
                mx.chk.warn_deprecated(items[1], mx.context)
            return analyze_var(name, getter.var, typ, mx)

        if mx.is_lvalue:
            mx.msg.cant_assign_to_method(mx.context)
        if not isinstance(method, OverloadedFuncDef):
            signature = function_type(method, mx.named_type("builtins.function"))
        else:
            if method.type is None:
                # Overloads may be not ready if they are decorated. Handle this in same
                # manner as we would handle a regular decorated function: defer if possible.
                if not mx.no_deferral and method.items:
                    mx.not_ready_callback(method.name, mx.context)
                return AnyType(TypeOfAny.special_form)
            assert isinstance(method.type, Overloaded)
            signature = method.type
        signature = freshen_all_functions_type_vars(signature)
        if not method.is_static:
            signature = check_self_arg(
                signature, mx.self_type, method.is_class, mx.context, name, mx.msg
            )
            signature = bind_self(signature, mx.self_type, is_classmethod=method.is_class)
        # TODO: should we skip these steps for static methods as well?
        # Since generic static methods should not be allowed.
        typ = map_instance_to_supertype(typ, method.info)
        member_type = expand_type_by_instance(signature, typ)
        freeze_all_type_vars(member_type)
        return member_type
    else:
        # Not a method.
        return analyze_member_var_access(name, typ, info, mx)


def validate_super_call(node: FuncBase, mx: MemberContext) -> None:
    unsafe_super = False
    if isinstance(node, FuncDef) and node.is_trivial_body:
        unsafe_super = True
        impl = node
    elif isinstance(node, OverloadedFuncDef):
        if node.impl:
            impl = node.impl if isinstance(node.impl, FuncDef) else node.impl.func
            unsafe_super = impl.is_trivial_body
    if unsafe_super:
        mx.msg.unsafe_super(node.name, node.info.name, mx.context)


def analyze_type_callable_member_access(name: str, typ: FunctionLike, mx: MemberContext) -> Type:
    # Class attribute.
    # TODO super?
    ret_type = typ.items[0].ret_type
    assert isinstance(ret_type, ProperType)
    if isinstance(ret_type, TupleType):
        ret_type = tuple_fallback(ret_type)
    if isinstance(ret_type, TypedDictType):
        ret_type = ret_type.fallback
    if isinstance(ret_type, Instance):
        if not mx.is_operator:
            # When Python sees an operator (eg `3 == 4`), it automatically translates that
            # into something like `int.__eq__(3, 4)` instead of `(3).__eq__(4)` as an
            # optimization.
            #
            # While it normally it doesn't matter which of the two versions are used, it
            # does cause inconsistencies when working with classes. For example, translating
            # `int == int` to `int.__eq__(int)` would not work since `int.__eq__` is meant to
            # compare two int _instances_. What we really want is `type(int).__eq__`, which
            # is meant to compare two types or classes.
            #
            # This check makes sure that when we encounter an operator, we skip looking up
            # the corresponding method in the current instance to avoid this edge case.
            # See https://github.com/python/mypy/pull/1787 for more info.
            # TODO: do not rely on same type variables being present in all constructor overloads.
            result = analyze_class_attribute_access(
                ret_type, name, mx, original_vars=typ.items[0].variables, mcs_fallback=typ.fallback
            )
            if result:
                return result
        # Look up from the 'type' type.
        return _analyze_member_access(name, typ.fallback, mx)
    else:
        assert False, f"Unexpected type {ret_type!r}"


def analyze_type_type_member_access(
    name: str, typ: TypeType, mx: MemberContext, override_info: TypeInfo | None
) -> Type:
    # Similar to analyze_type_callable_attribute_access.
    item = None
    fallback = mx.named_type("builtins.type")
    if isinstance(typ.item, Instance):
        item = typ.item
    elif isinstance(typ.item, AnyType):
        with mx.msg.filter_errors():
            return _analyze_member_access(name, fallback, mx, override_info)
    elif isinstance(typ.item, TypeVarType):
        upper_bound = get_proper_type(typ.item.upper_bound)
        if isinstance(upper_bound, Instance):
            item = upper_bound
        elif isinstance(upper_bound, UnionType):
            return _analyze_member_access(
                name,
                TypeType.make_normalized(upper_bound, line=typ.line, column=typ.column),
                mx,
                override_info,
            )
        elif isinstance(upper_bound, TupleType):
            item = tuple_fallback(upper_bound)
        elif isinstance(upper_bound, AnyType):
            with mx.msg.filter_errors():
                return _analyze_member_access(name, fallback, mx, override_info)
    elif isinstance(typ.item, TupleType):
        item = tuple_fallback(typ.item)
    elif isinstance(typ.item, FunctionLike) and typ.item.is_type_obj():
        item = typ.item.fallback
    elif isinstance(typ.item, TypeType):
        # Access member on metaclass object via Type[Type[C]]
        if isinstance(typ.item.item, Instance):
            item = typ.item.item.type.metaclass_type
    ignore_messages = False

    if item is not None:
        fallback = item.type.metaclass_type or fallback

    if item and not mx.is_operator:
        # See comment above for why operators are skipped
        result = analyze_class_attribute_access(
            item, name, mx, mcs_fallback=fallback, override_info=override_info
        )
        if result:
            if not (isinstance(get_proper_type(result), AnyType) and item.type.fallback_to_any):
                return result
            else:
                # We don't want errors on metaclass lookup for classes with Any fallback
                ignore_messages = True

    with mx.msg.filter_errors(filter_errors=ignore_messages):
        return _analyze_member_access(name, fallback, mx, override_info)


def analyze_union_member_access(name: str, typ: UnionType, mx: MemberContext) -> Type:
    with mx.msg.disable_type_names():
        results = []
        for subtype in typ.relevant_items():
            # Self types should be bound to every individual item of a union.
            item_mx = mx.copy_modified(self_type=subtype)
            results.append(_analyze_member_access(name, subtype, item_mx))
    return make_simplified_union(results)


def analyze_none_member_access(name: str, typ: NoneType, mx: MemberContext) -> Type:
    if name == "__bool__":
        literal_false = LiteralType(False, fallback=mx.named_type("builtins.bool"))
        return CallableType(
            arg_types=[],
            arg_kinds=[],
            arg_names=[],
            ret_type=literal_false,
            fallback=mx.named_type("builtins.function"),
        )
    else:
        return _analyze_member_access(name, mx.named_type("builtins.object"), mx)


def analyze_member_var_access(
    name: str, itype: Instance, info: TypeInfo, mx: MemberContext
) -> Type:
    """Analyse attribute access that does not target a method.

    This is logically part of analyze_member_access and the arguments are similar.

    original_type is the type of E in the expression E.var
    """
    # It was not a method. Try looking up a variable.
    v = lookup_member_var_or_accessor(info, name, mx.is_lvalue)

    mx.chk.warn_deprecated(v, mx.context)

    vv = v
    if isinstance(vv, Decorator):
        # The associated Var node of a decorator contains the type.
        v = vv.var
        if mx.is_super:
            validate_super_call(vv.func, mx)

    if isinstance(vv, TypeInfo):
        # If the associated variable is a TypeInfo synthesize a Var node for
        # the purposes of type checking.  This enables us to type check things
        # like accessing class attributes on an inner class.
        v = Var(name, type=type_object_type(vv, mx.named_type))
        v.info = info

    if isinstance(vv, TypeAlias):
        # Similar to the above TypeInfo case, we allow using
        # qualified type aliases in runtime context if it refers to an
        # instance type. For example:
        #     class C:
        #         A = List[int]
        #     x = C.A() <- this is OK
        typ = mx.chk.expr_checker.alias_type_in_runtime_context(
            vv, ctx=mx.context, alias_definition=mx.is_lvalue
        )
        v = Var(name, type=typ)
        v.info = info

    if isinstance(v, Var):
        implicit = info[name].implicit

        # An assignment to final attribute is always an error,
        # independently of types.
        if mx.is_lvalue and not mx.chk.get_final_context():
            check_final_member(name, info, mx.msg, mx.context)

        return analyze_var(name, v, itype, mx, implicit=implicit)
    elif isinstance(v, FuncDef):
        assert False, "Did not expect a function"
    elif isinstance(v, MypyFile):
        mx.chk.module_refs.add(v.fullname)
        return mx.chk.expr_checker.module_type(v)
    elif (
        not v
        and name not in ["__getattr__", "__setattr__", "__getattribute__"]
        and not mx.is_operator
        and mx.module_symbol_table is None
    ):
        # Above we skip ModuleType.__getattr__ etc. if we have a
        # module symbol table, since the symbol table allows precise
        # checking.
        if not mx.is_lvalue:
            for method_name in ("__getattribute__", "__getattr__"):
                method = info.get_method(method_name)

                # __getattribute__ is defined on builtins.object and returns Any, so without
                # the guard this search will always find object.__getattribute__ and conclude
                # that the attribute exists
                if method and method.info.fullname != "builtins.object":
                    bound_method = analyze_decorator_or_funcbase_access(
                        defn=method, itype=itype, name=method_name, mx=mx
                    )
                    typ = map_instance_to_supertype(itype, method.info)
                    getattr_type = get_proper_type(expand_type_by_instance(bound_method, typ))
                    if isinstance(getattr_type, CallableType):
                        result = getattr_type.ret_type
                    else:
                        result = getattr_type

                    # Call the attribute hook before returning.
                    fullname = f"{method.info.fullname}.{name}"
                    hook = mx.chk.plugin.get_attribute_hook(fullname)
                    if hook:
                        result = hook(
                            AttributeContext(
                                get_proper_type(mx.original_type),
                                result,
                                mx.is_lvalue,
                                mx.context,
                                mx.chk,
                            )
                        )
                    return result
        else:
            setattr_meth = info.get_method("__setattr__")
            if setattr_meth and setattr_meth.info.fullname != "builtins.object":
                bound_type = analyze_decorator_or_funcbase_access(
                    defn=setattr_meth, itype=itype, name=name, mx=mx.copy_modified(is_lvalue=False)
                )
                typ = map_instance_to_supertype(itype, setattr_meth.info)
                setattr_type = get_proper_type(expand_type_by_instance(bound_type, typ))
                if isinstance(setattr_type, CallableType) and len(setattr_type.arg_types) > 0:
                    return setattr_type.arg_types[-1]

    if itype.type.fallback_to_any:
        return AnyType(TypeOfAny.special_form)

    # Could not find the member.
    if itype.extra_attrs and name in itype.extra_attrs.attrs:
        # For modules use direct symbol table lookup.
        if not itype.extra_attrs.mod_name:
            return itype.extra_attrs.attrs[name]

    if mx.is_super:
        mx.msg.undefined_in_superclass(name, mx.context)
        return AnyType(TypeOfAny.from_error)
    else:
        ret = report_missing_attribute(mx.original_type, itype, name, mx)
        # Avoid paying double jeopardy if we can't find the member due to --no-implicit-reexport
        if (
            mx.module_symbol_table is not None
            and name in mx.module_symbol_table
            and not mx.module_symbol_table[name].module_public
        ):
            v = mx.module_symbol_table[name].node
            e = NameExpr(name)
            e.set_line(mx.context)
            e.node = v
            return mx.chk.expr_checker.analyze_ref_expr(e, lvalue=mx.is_lvalue)
        return ret


def check_final_member(name: str, info: TypeInfo, msg: MessageBuilder, ctx: Context) -> None:
    """Give an error if the name being assigned was declared as final."""
    for base in info.mro:
        sym = base.names.get(name)
        if sym and is_final_node(sym.node):
            msg.cant_assign_to_final(name, attr_assign=True, ctx=ctx)


def analyze_descriptor_access(
    descriptor_type: Type, mx: MemberContext, *, assignment: bool = False
) -> Type:
    """Type check descriptor access.

    Arguments:
        descriptor_type: The type of the descriptor attribute being accessed
            (the type of ``f`` in ``a.f`` when ``f`` is a descriptor).
        mx: The current member access context.
    Return:
        The return type of the appropriate ``__get__`` overload for the descriptor.
    """
    instance_type = get_proper_type(mx.self_type)
    orig_descriptor_type = descriptor_type
    descriptor_type = get_proper_type(descriptor_type)

    if isinstance(descriptor_type, UnionType):
        # Map the access over union types
        return make_simplified_union(
            [
                analyze_descriptor_access(typ, mx, assignment=assignment)
                for typ in descriptor_type.items
            ]
        )
    elif not isinstance(descriptor_type, Instance):
        return orig_descriptor_type

    if not descriptor_type.type.has_readable_member("__get__"):
        return orig_descriptor_type

    dunder_get = descriptor_type.type.get_method("__get__")
    if dunder_get is None:
        mx.msg.fail(
            message_registry.DESCRIPTOR_GET_NOT_CALLABLE.format(
                descriptor_type.str_with_options(mx.msg.options)
            ),
            mx.context,
        )
        return AnyType(TypeOfAny.from_error)

    bound_method = analyze_decorator_or_funcbase_access(
        defn=dunder_get,
        itype=descriptor_type,
        name="__get__",
        mx=mx.copy_modified(self_type=descriptor_type),
    )

    typ = map_instance_to_supertype(descriptor_type, dunder_get.info)
    dunder_get_type = expand_type_by_instance(bound_method, typ)

    if isinstance(instance_type, FunctionLike) and instance_type.is_type_obj():
        owner_type = instance_type.items[0].ret_type
        instance_type = NoneType()
    elif isinstance(instance_type, TypeType):
        owner_type = instance_type.item
        instance_type = NoneType()
    else:
        owner_type = instance_type

    callable_name = mx.chk.expr_checker.method_fullname(descriptor_type, "__get__")
    dunder_get_type = mx.chk.expr_checker.transform_callee_type(
        callable_name,
        dunder_get_type,
        [
            TempNode(instance_type, context=mx.context),
            TempNode(TypeType.make_normalized(owner_type), context=mx.context),
        ],
        [ARG_POS, ARG_POS],
        mx.context,
        object_type=descriptor_type,
    )

    _, inferred_dunder_get_type = mx.chk.expr_checker.check_call(
        dunder_get_type,
        [
            TempNode(instance_type, context=mx.context),
            TempNode(TypeType.make_normalized(owner_type), context=mx.context),
        ],
        [ARG_POS, ARG_POS],
        mx.context,
        object_type=descriptor_type,
        callable_name=callable_name,
    )

    if not assignment:
        mx.chk.check_deprecated(dunder_get, mx.context)
        mx.chk.warn_deprecated_overload_item(
            dunder_get, mx.context, target=inferred_dunder_get_type, selftype=descriptor_type
        )

    inferred_dunder_get_type = get_proper_type(inferred_dunder_get_type)
    if isinstance(inferred_dunder_get_type, AnyType):
        # check_call failed, and will have reported an error
        return inferred_dunder_get_type

    if not isinstance(inferred_dunder_get_type, CallableType):
        mx.msg.fail(
            message_registry.DESCRIPTOR_GET_NOT_CALLABLE.format(
                descriptor_type.str_with_options(mx.msg.options)
            ),
            mx.context,
        )
        return AnyType(TypeOfAny.from_error)

    return inferred_dunder_get_type.ret_type


def is_instance_var(var: Var) -> bool:
    """Return if var is an instance variable according to PEP 526."""
    return (
        # check the type_info node is the var (not a decorated function, etc.)
        var.name in var.info.names
        and var.info.names[var.name].node is var
        and not var.is_classvar
        # variables without annotations are treated as classvar
        and not var.is_inferred
    )


def analyze_var(
    name: str, var: Var, itype: Instance, mx: MemberContext, *, implicit: bool = False
) -> Type:
    """Analyze access to an attribute via a Var node.

    This is conceptually part of analyze_member_access and the arguments are similar.
    itype is the instance type in which attribute should be looked up
    original_type is the type of E in the expression E.var
    if implicit is True, the original Var was created as an assignment to self
    """
    # Found a member variable.
    original_itype = itype
    itype = map_instance_to_supertype(itype, var.info)
    if var.is_settable_property and mx.is_lvalue:
        typ: Type | None = var.setter_type
        if typ is None and var.is_ready:
            # Existing synthetic properties may not set setter type. Fall back to getter.
            typ = var.type
    else:
        typ = var.type
    if typ:
        if isinstance(typ, PartialType):
            return mx.chk.handle_partial_var_type(typ, mx.is_lvalue, var, mx.context)
        if mx.is_lvalue and var.is_property and not var.is_settable_property:
            # TODO allow setting attributes in subclass (although it is probably an error)
            mx.msg.read_only_property(name, itype.type, mx.context)
        if mx.is_lvalue and var.is_classvar:
            mx.msg.cant_assign_to_classvar(name, mx.context)
        t = freshen_all_functions_type_vars(typ)
        t = expand_self_type_if_needed(t, mx, var, original_itype)
        t = expand_type_by_instance(t, itype)
        freeze_all_type_vars(t)
        result = t
        typ = get_proper_type(typ)

        call_type: ProperType | None = None
        if var.is_initialized_in_class and (not is_instance_var(var) or mx.is_operator):
            if isinstance(typ, FunctionLike) and not typ.is_type_obj():
                call_type = typ
            elif var.is_property:
                call_type = get_proper_type(
                    _analyze_member_access("__call__", typ, mx.copy_modified(self_type=typ))
                )
            else:
                call_type = typ

        if isinstance(call_type, FunctionLike) and not call_type.is_type_obj():
            if mx.is_lvalue:
                if var.is_property:
                    if not var.is_settable_property:
                        mx.msg.read_only_property(name, itype.type, mx.context)
                else:
                    mx.msg.cant_assign_to_method(mx.context)

            if not var.is_staticmethod:
                # Class-level function objects and classmethods become bound methods:
                # the former to the instance, the latter to the class.
                functype: FunctionLike = call_type
                signature = freshen_all_functions_type_vars(functype)
                bound = get_proper_type(expand_self_type(var, signature, mx.original_type))
                assert isinstance(bound, FunctionLike)
                signature = bound
                signature = check_self_arg(
                    signature, mx.self_type, var.is_classmethod, mx.context, name, mx.msg
                )
                signature = bind_self(signature, mx.self_type, var.is_classmethod)
                expanded_signature = expand_type_by_instance(signature, itype)
                freeze_all_type_vars(expanded_signature)
                if var.is_property:
                    # A property cannot have an overloaded type => the cast is fine.
                    assert isinstance(expanded_signature, CallableType)
                    if var.is_settable_property and mx.is_lvalue and var.setter_type is not None:
                        result = expanded_signature.arg_types[0]
                    else:
                        result = expanded_signature.ret_type
                else:
                    result = expanded_signature
    else:
        if not var.is_ready and not mx.no_deferral:
            mx.not_ready_callback(var.name, mx.context)
        # Implicit 'Any' type.
        result = AnyType(TypeOfAny.special_form)
    fullname = f"{var.info.fullname}.{name}"
    hook = mx.chk.plugin.get_attribute_hook(fullname)
    if result and not mx.is_lvalue and not implicit:
        result = analyze_descriptor_access(result, mx)
    if hook:
        result = hook(
            AttributeContext(
                get_proper_type(mx.original_type), result, mx.is_lvalue, mx.context, mx.chk
            )
        )
    return result


def expand_self_type_if_needed(
    t: Type, mx: MemberContext, var: Var, itype: Instance, is_class: bool = False
) -> Type:
    """Expand special Self type in a backwards compatible manner.

    This should ensure that mixing old-style and new-style self-types work
    seamlessly. Also, re-bind new style self-types in subclasses if needed.
    """
    original = get_proper_type(mx.self_type)
    if not (mx.is_self or mx.is_super):
        repl = mx.self_type
        if is_class:
            if isinstance(original, TypeType):
                repl = original.item
            elif isinstance(original, CallableType):
                # Problematic access errors should have been already reported.
                repl = erase_typevars(original.ret_type)
            else:
                repl = itype
        return expand_self_type(var, t, repl)
    elif supported_self_type(
        # Support compatibility with plain old style T -> T and Type[T] -> T only.
        get_proper_type(mx.self_type),
        allow_instances=False,
        allow_callable=False,
    ):
        repl = mx.self_type
        if is_class and isinstance(original, TypeType):
            repl = original.item
        return expand_self_type(var, t, repl)
    elif (
        mx.is_self
        and itype.type != var.info
        # If an attribute with Self-type was defined in a supertype, we need to
        # rebind the Self type variable to Self type variable of current class...
        and itype.type.self_type is not None
        # ...unless `self` has an explicit non-trivial annotation.
        and itype == mx.chk.scope.active_self_type()
    ):
        return expand_self_type(var, t, itype.type.self_type)
    else:
        return t


def freeze_all_type_vars(member_type: Type) -> None:
    member_type.accept(FreezeTypeVarsVisitor())


class FreezeTypeVarsVisitor(TypeTraverserVisitor):
    def visit_callable_type(self, t: CallableType) -> None:
        for v in t.variables:
            v.id.meta_level = 0
        super().visit_callable_type(t)


def lookup_member_var_or_accessor(info: TypeInfo, name: str, is_lvalue: bool) -> SymbolNode | None:
    """Find the attribute/accessor node that refers to a member of a type."""
    # TODO handle lvalues
    node = info.get(name)
    if node:
        return node.node
    else:
        return None


def check_self_arg(
    functype: FunctionLike,
    dispatched_arg_type: Type,
    is_classmethod: bool,
    context: Context,
    name: str,
    msg: MessageBuilder,
) -> FunctionLike:
    """Check that an instance has a valid type for a method with annotated 'self'.

    For example if the method is defined as:
        class A:
            def f(self: S) -> T: ...
    then for 'x.f' we check that type(x) <: S. If the method is overloaded, we select
    only overloads items that satisfy this requirement. If there are no matching
    overloads, an error is generated.
    """
    items = functype.items
    if not items:
        return functype
    new_items = []
    if is_classmethod:
        dispatched_arg_type = TypeType.make_normalized(dispatched_arg_type)

    for item in items:
        if not item.arg_types or item.arg_kinds[0] not in (ARG_POS, ARG_STAR):
            # No positional first (self) argument (*args is okay).
            msg.no_formal_self(name, item, context)
            # This is pretty bad, so just return the original signature if
            # there is at least one such error.
            return functype
        else:
            selfarg = get_proper_type(item.arg_types[0])
            # This level of erasure matches the one in checker.check_func_def(),
            # better keep these two checks consistent.
            if subtypes.is_subtype(dispatched_arg_type, erase_typevars(erase_to_bound(selfarg))):
                new_items.append(item)
            elif isinstance(selfarg, ParamSpecType):
                # TODO: This is not always right. What's the most reasonable thing to do here?
                new_items.append(item)
            elif isinstance(selfarg, TypeVarTupleType):
                raise NotImplementedError
    if not new_items:
        # Choose first item for the message (it may be not very helpful for overloads).
        msg.incompatible_self_argument(
            name, dispatched_arg_type, items[0], is_classmethod, context
        )
        return functype
    if len(new_items) == 1:
        return new_items[0]
    return Overloaded(new_items)


def analyze_class_attribute_access(
    itype: Instance,
    name: str,
    mx: MemberContext,
    *,
    mcs_fallback: Instance,
    override_info: TypeInfo | None = None,
    original_vars: Sequence[TypeVarLikeType] | None = None,
) -> Type | None:
    """Analyze access to an attribute on a class object.

    itype is the return type of the class object callable, original_type is the type
    of E in the expression E.var, original_vars are type variables of the class callable
    (for generic classes).
    """
    info = itype.type
    if override_info:
        info = override_info

    fullname = f"{info.fullname}.{name}"
    hook = mx.chk.plugin.get_class_attribute_hook(fullname)

    node = info.get(name)
    if not node:
        if itype.extra_attrs and name in itype.extra_attrs.attrs:
            # For modules use direct symbol table lookup.
            if not itype.extra_attrs.mod_name:
                return itype.extra_attrs.attrs[name]
        if info.fallback_to_any or info.meta_fallback_to_any:
            return apply_class_attr_hook(mx, hook, AnyType(TypeOfAny.special_form))
        return None

    if (
        isinstance(node.node, Var)
        and not node.node.is_classvar
        and not hook
        and mcs_fallback.type.get(name)
    ):
        # If the same attribute is declared on the metaclass and the class but with different types,
        # and the attribute on the class is not a ClassVar,
        # the type of the attribute on the metaclass should take priority
        # over the type of the attribute on the class,
        # when the attribute is being accessed from the class object itself.
        #
        # Return `None` here to signify that the name should be looked up
        # on the class object itself rather than the instance.
        return None

    mx.chk.warn_deprecated(node.node, mx.context)

    is_decorated = isinstance(node.node, Decorator)
    is_method = is_decorated or isinstance(node.node, FuncBase)
    if mx.is_lvalue:
        if is_method:
            mx.msg.cant_assign_to_method(mx.context)
        if isinstance(node.node, TypeInfo):
            mx.msg.fail(message_registry.CANNOT_ASSIGN_TO_TYPE, mx.context)

    # Refuse class attribute access if slot defined
    if info.slots and name in info.slots:
        mx.msg.fail(message_registry.CLASS_VAR_CONFLICTS_SLOTS.format(name), mx.context)

    # If a final attribute was declared on `self` in `__init__`, then it
    # can't be accessed on the class object.
    if node.implicit and isinstance(node.node, Var) and node.node.is_final:
        mx.msg.fail(
            message_registry.CANNOT_ACCESS_FINAL_INSTANCE_ATTR.format(node.node.name), mx.context
        )

    # An assignment to final attribute on class object is also always an error,
    # independently of types.
    if mx.is_lvalue and not mx.chk.get_final_context():
        check_final_member(name, info, mx.msg, mx.context)

    if info.is_enum and not (mx.is_lvalue or is_decorated or is_method):
        enum_class_attribute_type = analyze_enum_class_attribute_access(itype, name, mx)
        if enum_class_attribute_type:
            return apply_class_attr_hook(mx, hook, enum_class_attribute_type)

    t = node.type
    if t:
        if isinstance(t, PartialType):
            symnode = node.node
            assert isinstance(symnode, Var)
            return apply_class_attr_hook(
                mx, hook, mx.chk.handle_partial_var_type(t, mx.is_lvalue, symnode, mx.context)
            )

        # Find the class where method/variable was defined.
        if isinstance(node.node, Decorator):
            super_info: TypeInfo | None = node.node.var.info
        elif isinstance(node.node, (Var, SYMBOL_FUNCBASE_TYPES)):
            super_info = node.node.info
        else:
            super_info = None

        # Map the type to how it would look as a defining class. For example:
        #     class C(Generic[T]): ...
        #     class D(C[Tuple[T, S]]): ...
        #     D[int, str].method()
        # Here itype is D[int, str], isuper is C[Tuple[int, str]].
        if not super_info:
            isuper = None
        else:
            isuper = map_instance_to_supertype(itype, super_info)

        if isinstance(node.node, Var):
            assert isuper is not None
            # Check if original variable type has type variables. For example:
            #     class C(Generic[T]):
            #         x: T
            #     C.x  # Error, ambiguous access
            #     C[int].x  # Also an error, since C[int] is same as C at runtime
            # Exception is Self type wrapped in ClassVar, that is safe.
            def_vars = set(node.node.info.defn.type_vars)
            if not node.node.is_classvar and node.node.info.self_type:
                def_vars.add(node.node.info.self_type)
            typ_vars = set(get_type_vars(t))
            if def_vars & typ_vars:
                # Exception: access on Type[...], including first argument of class methods is OK.
                if not isinstance(get_proper_type(mx.original_type), TypeType) or node.implicit:
                    if node.node.is_classvar:
                        message = message_registry.GENERIC_CLASS_VAR_ACCESS
                    else:
                        message = message_registry.GENERIC_INSTANCE_VAR_CLASS_ACCESS
                    mx.msg.fail(message, mx.context)
            t = expand_self_type_if_needed(t, mx, node.node, itype, is_class=True)
            # Erase non-mapped variables, but keep mapped ones, even if there is an error.
            # In the above example this means that we infer following types:
            #     C.x -> Any
            #     C[int].x -> int
            t = erase_typevars(expand_type_by_instance(t, isuper), {tv.id for tv in def_vars})

        is_classmethod = (is_decorated and cast(Decorator, node.node).func.is_class) or (
            isinstance(node.node, SYMBOL_FUNCBASE_TYPES) and node.node.is_class
        )
        is_staticmethod = (is_decorated and cast(Decorator, node.node).func.is_static) or (
            isinstance(node.node, SYMBOL_FUNCBASE_TYPES) and node.node.is_static
        )
        t = get_proper_type(t)
        if isinstance(t, FunctionLike) and is_classmethod:
            t = check_self_arg(t, mx.self_type, False, mx.context, name, mx.msg)
        result = add_class_tvars(
            t, isuper, is_classmethod, is_staticmethod, mx.self_type, original_vars=original_vars
        )
        if not mx.is_lvalue:
            result = analyze_descriptor_access(result, mx)

        return apply_class_attr_hook(mx, hook, result)
    elif isinstance(node.node, Var):
        mx.not_ready_callback(name, mx.context)
        return AnyType(TypeOfAny.special_form)

    if isinstance(node.node, TypeVarExpr):
        mx.msg.fail(
            message_registry.CANNOT_USE_TYPEVAR_AS_EXPRESSION.format(info.name, name), mx.context
        )
        return AnyType(TypeOfAny.from_error)

    # TODO: some logic below duplicates analyze_ref_expr in checkexpr.py
    if isinstance(node.node, TypeInfo):
        if node.node.typeddict_type:
            # We special-case TypedDict, because they don't define any constructor.
            return typeddict_callable(node.node, mx.named_type)
        elif node.node.fullname == "types.NoneType":
            # We special case NoneType, because its stub definition is not related to None.
            return TypeType(NoneType())
        else:
            return type_object_type(node.node, mx.named_type)

    if isinstance(node.node, MypyFile):
        # Reference to a module object.
        return mx.named_type("types.ModuleType")

    if isinstance(node.node, TypeAlias):
        return mx.chk.expr_checker.alias_type_in_runtime_context(
            node.node, ctx=mx.context, alias_definition=mx.is_lvalue
        )

    if is_decorated:
        assert isinstance(node.node, Decorator)
        if node.node.type:
            return apply_class_attr_hook(mx, hook, node.node.type)
        else:
            mx.not_ready_callback(name, mx.context)
            return AnyType(TypeOfAny.from_error)
    else:
        assert isinstance(node.node, SYMBOL_FUNCBASE_TYPES)
        typ = function_type(node.node, mx.named_type("builtins.function"))
        # Note: if we are accessing class method on class object, the cls argument is bound.
        # Annotated and/or explicit class methods go through other code paths above, for
        # unannotated implicit class methods we do this here.
        if node.node.is_class:
            typ = bind_self(typ, is_classmethod=True)
        return apply_class_attr_hook(mx, hook, typ)


def apply_class_attr_hook(
    mx: MemberContext, hook: Callable[[AttributeContext], Type] | None, result: Type
) -> Type | None:
    if hook:
        result = hook(
            AttributeContext(
                get_proper_type(mx.original_type), result, mx.is_lvalue, mx.context, mx.chk
            )
        )
    return result


def analyze_enum_class_attribute_access(
    itype: Instance, name: str, mx: MemberContext
) -> Type | None:
    # Skip these since Enum will remove it
    if name in EXCLUDED_ENUM_ATTRIBUTES:
        return report_missing_attribute(mx.original_type, itype, name, mx)
    # Dunders and private names are not Enum members
    if name.startswith("__") and name.replace("_", "") != "":
        return None

    node = itype.type.get(name)
    if node and node.type:
        proper = get_proper_type(node.type)
        # Support `A = nonmember(1)` function call and decorator.
        if (
            isinstance(proper, Instance)
            and proper.type.fullname == "enum.nonmember"
            and proper.args
        ):
            return proper.args[0]

    enum_literal = LiteralType(name, fallback=itype)
    return itype.copy_modified(last_known_value=enum_literal)


def analyze_typeddict_access(
    name: str, typ: TypedDictType, mx: MemberContext, override_info: TypeInfo | None
) -> Type:
    if name == "__setitem__":
        if isinstance(mx.context, IndexExpr):
            # Since we can get this during `a['key'] = ...`
            # it is safe to assume that the context is `IndexExpr`.
            item_type, key_names = mx.chk.expr_checker.visit_typeddict_index_expr(
                typ, mx.context.index, setitem=True
            )
            assigned_readonly_keys = typ.readonly_keys & key_names
            if assigned_readonly_keys:
                mx.msg.readonly_keys_mutated(assigned_readonly_keys, context=mx.context)
        else:
            # It can also be `a.__setitem__(...)` direct call.
            # In this case `item_type` can be `Any`,
            # because we don't have args available yet.
            # TODO: check in `default` plugin that `__setitem__` is correct.
            item_type = AnyType(TypeOfAny.implementation_artifact)
        return CallableType(
            arg_types=[mx.chk.named_type("builtins.str"), item_type],
            arg_kinds=[ARG_POS, ARG_POS],
            arg_names=[None, None],
            ret_type=NoneType(),
            fallback=mx.chk.named_type("builtins.function"),
            name=name,
        )
    elif name == "__delitem__":
        return CallableType(
            arg_types=[mx.chk.named_type("builtins.str")],
            arg_kinds=[ARG_POS],
            arg_names=[None],
            ret_type=NoneType(),
            fallback=mx.chk.named_type("builtins.function"),
            name=name,
        )
    return _analyze_member_access(name, typ.fallback, mx, override_info)


def add_class_tvars(
    t: ProperType,
    isuper: Instance | None,
    is_classmethod: bool,
    is_staticmethod: bool,
    original_type: Type,
    original_vars: Sequence[TypeVarLikeType] | None = None,
) -> Type:
    """Instantiate type variables during analyze_class_attribute_access,
    e.g T and Q in the following:

    class A(Generic[T]):
        @classmethod
        def foo(cls: Type[Q]) -> Tuple[T, Q]: ...

    class B(A[str]): pass
    B.foo()

    Args:
        t: Declared type of the method (or property)
        isuper: Current instance mapped to the superclass where method was defined, this
            is usually done by map_instance_to_supertype()
        is_classmethod: True if this method is decorated with @classmethod
        is_staticmethod: True if this method is decorated with @staticmethod
        original_type: The value of the type B in the expression B.foo() or the corresponding
            component in case of a union (this is used to bind the self-types)
        original_vars: Type variables of the class callable on which the method was accessed
    Returns:
        Expanded method type with added type variables (when needed).
    """
    # TODO: verify consistency between Q and T

    # We add class type variables if the class method is accessed on class object
    # without applied type arguments, this matches the behavior of __init__().
    # For example (continuing the example in docstring):
    #     A       # The type of callable is def [T] () -> A[T], _not_ def () -> A[Any]
    #     A[int]  # The type of callable is def () -> A[int]
    # and
    #     A.foo       # The type is generic def [T] () -> Tuple[T, A[T]]
    #     A[int].foo  # The type is non-generic def () -> Tuple[int, A[int]]
    #
    # This behaviour is useful for defining alternative constructors for generic classes.
    # To achieve such behaviour, we add the class type variables that are still free
    # (i.e. appear in the return type of the class object on which the method was accessed).
    if isinstance(t, CallableType):
        tvars = original_vars if original_vars is not None else []
        t = freshen_all_functions_type_vars(t)
        if is_classmethod:
            t = bind_self(t, original_type, is_classmethod=True)
        if is_classmethod or is_staticmethod:
            assert isuper is not None
            t = expand_type_by_instance(t, isuper)
        freeze_all_type_vars(t)
        return t.copy_modified(variables=list(tvars) + list(t.variables))
    elif isinstance(t, Overloaded):
        return Overloaded(
            [
                cast(
                    CallableType,
                    add_class_tvars(
                        item,
                        isuper,
                        is_classmethod,
                        is_staticmethod,
                        original_type,
                        original_vars=original_vars,
                    ),
                )
                for item in t.items
            ]
        )
    if isuper is not None:
        t = expand_type_by_instance(t, isuper)
    return t


def typeddict_callable(info: TypeInfo, named_type: Callable[[str], Instance]) -> CallableType:
    """Construct a reasonable type for a TypedDict type in runtime context.

    If it appears as a callee, it will be special-cased anyway, e.g. it is
    also allowed to accept a single positional argument if it is a dict literal.

    Note it is not safe to move this to type_object_type() since it will crash
    on plugin-generated TypedDicts, that may not have the special_alias.
    """
    assert info.special_alias is not None
    target = info.special_alias.target
    assert isinstance(target, ProperType) and isinstance(target, TypedDictType)
    expected_types = list(target.items.values())
    kinds = [ArgKind.ARG_NAMED] * len(expected_types)
    names = list(target.items.keys())
    return CallableType(
        expected_types,
        kinds,
        names,
        target,
        named_type("builtins.type"),
        variables=info.defn.type_vars,
    )


def type_object_type(info: TypeInfo, named_type: Callable[[str], Instance]) -> ProperType:
    """Return the type of a type object.

    For a generic type G with type variables T and S the type is generally of form

      Callable[..., G[T, S]]

    where ... are argument types for the __init__/__new__ method (without the self
    argument). Also, the fallback type will be 'type' instead of 'function'.
    """

    # We take the type from whichever of __init__ and __new__ is first
    # in the MRO, preferring __init__ if there is a tie.
    init_method = info.get("__init__")
    new_method = info.get("__new__")
    if not init_method or not is_valid_constructor(init_method.node):
        # Must be an invalid class definition.
        return AnyType(TypeOfAny.from_error)
    # There *should* always be a __new__ method except the test stubs
    # lack it, so just copy init_method in that situation
    new_method = new_method or init_method
    if not is_valid_constructor(new_method.node):
        # Must be an invalid class definition.
        return AnyType(TypeOfAny.from_error)

    # The two is_valid_constructor() checks ensure this.
    assert isinstance(new_method.node, (SYMBOL_FUNCBASE_TYPES, Decorator))
    assert isinstance(init_method.node, (SYMBOL_FUNCBASE_TYPES, Decorator))

    init_index = info.mro.index(init_method.node.info)
    new_index = info.mro.index(new_method.node.info)

    fallback = info.metaclass_type or named_type("builtins.type")
    if init_index < new_index:
        method: FuncBase | Decorator = init_method.node
        is_new = False
    elif init_index > new_index:
        method = new_method.node
        is_new = True
    else:
        if init_method.node.info.fullname == "builtins.object":
            # Both are defined by object.  But if we've got a bogus
            # base class, we can't know for sure, so check for that.
            if info.fallback_to_any:
                # Construct a universal callable as the prototype.
                any_type = AnyType(TypeOfAny.special_form)
                sig = CallableType(
                    arg_types=[any_type, any_type],
                    arg_kinds=[ARG_STAR, ARG_STAR2],
                    arg_names=["_args", "_kwds"],
                    ret_type=any_type,
                    fallback=named_type("builtins.function"),
                )
                return class_callable(sig, info, fallback, None, is_new=False)

        # Otherwise prefer __init__ in a tie. It isn't clear that this
        # is the right thing, but __new__ caused problems with
        # typeshed (#5647).
        method = init_method.node
        is_new = False
    # Construct callable type based on signature of __init__. Adjust
    # return type and insert type arguments.
    if isinstance(method, FuncBase):
        t = function_type(method, fallback)
    else:
        assert isinstance(method.type, ProperType)
        assert isinstance(method.type, FunctionLike)  # is_valid_constructor() ensures this
        t = method.type
    return type_object_type_from_function(t, info, method.info, fallback, is_new)


def analyze_decorator_or_funcbase_access(
    defn: Decorator | FuncBase, itype: Instance, name: str, mx: MemberContext
) -> Type:
    """Analyzes the type behind method access.

    The function itself can possibly be decorated.
    See: https://github.com/python/mypy/issues/10409
    """
    if isinstance(defn, Decorator):
        return analyze_var(name, defn.var, itype, mx)
    return bind_self(
        function_type(defn, mx.chk.named_type("builtins.function")), original_type=mx.self_type
    )


def is_valid_constructor(n: SymbolNode | None) -> bool:
    """Does this node represents a valid constructor method?

    This includes normal functions, overloaded functions, and decorators
    that return a callable type.
    """
    if isinstance(n, SYMBOL_FUNCBASE_TYPES):
        return True
    if isinstance(n, Decorator):
        return isinstance(get_proper_type(n.type), FunctionLike)
    return False
