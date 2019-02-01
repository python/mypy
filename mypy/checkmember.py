"""Type checking of attribute access"""

from typing import cast, Callable, List, Optional, TypeVar

from mypy.types import (
    Type, Instance, AnyType, TupleType, TypedDictType, CallableType, FunctionLike, TypeVarDef,
    Overloaded, TypeVarType, UnionType, PartialType, UninhabitedType, TypeOfAny, LiteralType,
    DeletedType, NoneTyp, TypeType, function_type, get_type_vars,
)
from mypy.nodes import (
    TypeInfo, FuncBase, Var, FuncDef, SymbolNode, Context, MypyFile, TypeVarExpr,
    ARG_POS, ARG_STAR, ARG_STAR2, Decorator, OverloadedFuncDef, TypeAlias, TempNode,
    is_final_node
)
from mypy.messages import MessageBuilder
from mypy.maptype import map_instance_to_supertype
from mypy.expandtype import expand_type_by_instance, expand_type, freshen_function_type_vars
from mypy.infer import infer_type_arguments
from mypy.typevars import fill_typevars
from mypy.plugin import AttributeContext
from mypy.typeanal import set_any_tvars
from mypy import message_registry
from mypy import subtypes
from mypy import meet

MYPY = False
if MYPY:  # import for forward declaration only
    import mypy.checker

from mypy import state


class MemberContext:
    """Information and objects needed to type check attribute access.

    Look at the docstring of analyze_member_access for more information.
    """

    def __init__(self,
                 is_lvalue: bool,
                 is_super: bool,
                 is_operator: bool,
                 original_type: Type,
                 context: Context,
                 msg: MessageBuilder,
                 chk: 'mypy.checker.TypeChecker') -> None:
        self.is_lvalue = is_lvalue
        self.is_super = is_super
        self.is_operator = is_operator
        self.original_type = original_type
        self.context = context  # Error context
        self.msg = msg
        self.chk = chk

    def builtin_type(self, name: str) -> Instance:
        return self.chk.named_type(name)

    def not_ready_callback(self, name: str, context: Context) -> None:
        self.chk.handle_cannot_determine_type(name, context)

    def copy_modified(self, messages: MessageBuilder) -> 'MemberContext':
        return MemberContext(self.is_lvalue, self.is_super, self.is_operator,
                             self.original_type, self.context, messages, self.chk)


def analyze_member_access(name: str,
                          typ: Type,
                          context: Context,
                          is_lvalue: bool,
                          is_super: bool,
                          is_operator: bool,
                          msg: MessageBuilder, *,
                          original_type: Type,
                          chk: 'mypy.checker.TypeChecker',
                          override_info: Optional[TypeInfo] = None,
                          in_literal_context: bool = False) -> Type:
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
    the initial, non-recursive call.
    """
    mx = MemberContext(is_lvalue,
                       is_super,
                       is_operator,
                       original_type,
                       context,
                       msg,
                       chk=chk)
    result = _analyze_member_access(name, typ, mx, override_info)
    if in_literal_context and isinstance(result, Instance) and result.final_value is not None:
        return result.final_value
    else:
        return result


def _analyze_member_access(name: str,
                           typ: Type,
                           mx: MemberContext,
                           override_info: Optional[TypeInfo] = None) -> Type:
    # TODO: This and following functions share some logic with subtypes.find_member;
    #       consider refactoring.
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
        return analyze_type_type_member_access(name, typ, mx)
    elif isinstance(typ, (TupleType, TypedDictType, LiteralType, FunctionLike)):
        # Actually look up from the fallback instance type.
        return _analyze_member_access(name, typ.fallback, mx)
    elif isinstance(typ, NoneTyp):
        return analyze_none_member_access(name, typ, mx)
    elif isinstance(typ, TypeVarType):
        return _analyze_member_access(name, typ.upper_bound, mx)
    elif isinstance(typ, DeletedType):
        mx.msg.deleted_as_rvalue(typ, mx.context)
        return AnyType(TypeOfAny.from_error)
    if mx.chk.should_suppress_optional_error([typ]):
        return AnyType(TypeOfAny.from_error)
    return mx.msg.has_no_attr(mx.original_type, typ, name, mx.context)


# The several functions that follow implement analyze_member_access for various
# types and aren't documented individually.


def analyze_instance_member_access(name: str,
                                   typ: Instance,
                                   mx: MemberContext,
                                   override_info: Optional[TypeInfo]) -> Type:
    if name == '__init__' and not mx.is_super:
        # Accessing __init__ in statically typed code would compromise
        # type safety unless used via super().
        mx.msg.fail(message_registry.CANNOT_ACCESS_INIT, mx.context)
        return AnyType(TypeOfAny.from_error)

    # The base object has an instance type.

    info = typ.type
    if override_info:
        info = override_info

    if (state.find_occurrences and
            info.name() == state.find_occurrences[0] and
            name == state.find_occurrences[1]):
        mx.msg.note("Occurrence of '{}.{}'".format(*state.find_occurrences), mx.context)

    # Look up the member. First look up the method dictionary.
    method = info.get_method(name)
    if method:
        if method.is_property:
            assert isinstance(method, OverloadedFuncDef)
            first_item = cast(Decorator, method.items[0])
            return analyze_var(name, first_item.var, typ, info, mx)
        if mx.is_lvalue:
            mx.msg.cant_assign_to_method(mx.context)
        signature = function_type(method, mx.builtin_type('builtins.function'))
        signature = freshen_function_type_vars(signature)
        if name == '__new__':
            # __new__ is special and behaves like a static method -- don't strip
            # the first argument.
            pass
        else:
            signature = bind_self(signature, mx.original_type)
        typ = map_instance_to_supertype(typ, method.info)
        member_type = expand_type_by_instance(signature, typ)
        freeze_type_vars(member_type)
        return member_type
    else:
        # Not a method.
        return analyze_member_var_access(name, typ, info, mx)


def analyze_type_callable_member_access(name: str,
                                        typ: FunctionLike,
                                        mx: MemberContext) -> Type:
    # Class attribute.
    # TODO super?
    ret_type = typ.items()[0].ret_type
    if isinstance(ret_type, TupleType):
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
            result = analyze_class_attribute_access(ret_type, name, mx)
            if result:
                return result
        # Look up from the 'type' type.
        return _analyze_member_access(name, typ.fallback, mx)
    else:
        assert False, 'Unexpected type {}'.format(repr(ret_type))


def analyze_type_type_member_access(name: str, typ: TypeType, mx: MemberContext) -> Type:
    # Similar to analyze_type_callable_attribute_access.
    item = None
    fallback = mx.builtin_type('builtins.type')
    ignore_messages = mx.msg.copy()
    ignore_messages.disable_errors()
    if isinstance(typ.item, Instance):
        item = typ.item
    elif isinstance(typ.item, AnyType):
        mx = mx.copy_modified(messages=ignore_messages)
        return _analyze_member_access(name, fallback, mx)
    elif isinstance(typ.item, TypeVarType):
        if isinstance(typ.item.upper_bound, Instance):
            item = typ.item.upper_bound
    elif isinstance(typ.item, TupleType):
        item = typ.item.fallback
    elif isinstance(typ.item, FunctionLike) and typ.item.is_type_obj():
        item = typ.item.fallback
    elif isinstance(typ.item, TypeType):
        # Access member on metaclass object via Type[Type[C]]
        if isinstance(typ.item.item, Instance):
            item = typ.item.item.type.metaclass_type
    if item and not mx.is_operator:
        # See comment above for why operators are skipped
        result = analyze_class_attribute_access(item, name, mx)
        if result:
            if not (isinstance(result, AnyType) and item.type.fallback_to_any):
                return result
            else:
                # We don't want errors on metaclass lookup for classes with Any fallback
                mx = mx.copy_modified(messages=ignore_messages)
    if item is not None:
        fallback = item.type.metaclass_type or fallback
    return _analyze_member_access(name, fallback, mx)


def analyze_union_member_access(name: str, typ: UnionType, mx: MemberContext) -> Type:
    mx.msg.disable_type_names += 1
    results = [_analyze_member_access(name, subtype, mx)
               for subtype in typ.relevant_items()]
    mx.msg.disable_type_names -= 1
    return UnionType.make_simplified_union(results)


def analyze_none_member_access(name: str, typ: NoneTyp, mx: MemberContext) -> Type:
    if mx.chk.should_suppress_optional_error([typ]):
        return AnyType(TypeOfAny.from_error)
    is_python_3 = mx.chk.options.python_version[0] >= 3
    # In Python 2 "None" has exactly the same attributes as "object". Python 3 adds a single
    # extra attribute, "__bool__".
    if is_python_3 and name == '__bool__':
        return CallableType(arg_types=[],
                            arg_kinds=[],
                            arg_names=[],
                            ret_type=mx.builtin_type('builtins.bool'),
                            fallback=mx.builtin_type('builtins.function'))
    else:
        return _analyze_member_access(name, mx.builtin_type('builtins.object'), mx)


def analyze_member_var_access(name: str,
                              itype: Instance,
                              info: TypeInfo,
                              mx: MemberContext) -> Type:
    """Analyse attribute access that does not target a method.

    This is logically part of analyze_member_access and the arguments are similar.

    original_type is the type of E in the expression E.var
    """
    # It was not a method. Try looking up a variable.
    v = lookup_member_var_or_accessor(info, name, mx.is_lvalue)

    vv = v
    if isinstance(vv, Decorator):
        # The associated Var node of a decorator contains the type.
        v = vv.var

    if isinstance(vv, TypeInfo):
        # If the associated variable is a TypeInfo synthesize a Var node for
        # the purposes of type checking.  This enables us to type check things
        # like accessing class attributes on an inner class.
        v = Var(name, type=type_object_type(vv, mx.builtin_type))
        v.info = info

    if isinstance(vv, TypeAlias) and isinstance(vv.target, Instance):
        # Similar to the above TypeInfo case, we allow using
        # qualified type aliases in runtime context if it refers to an
        # instance type. For example:
        #     class C:
        #         A = List[int]
        #     x = C.A() <- this is OK
        typ = instance_alias_type(vv, mx.builtin_type)
        v = Var(name, type=typ)
        v.info = info

    if isinstance(v, Var):
        implicit = info[name].implicit

        # An assignment to final attribute is always an error,
        # independently of types.
        if mx.is_lvalue and not mx.chk.get_final_context():
            check_final_member(name, info, mx.msg, mx.context)

        return analyze_var(name, v, itype, info, mx, implicit=implicit)
    elif isinstance(v, FuncDef):
        assert False, "Did not expect a function"
    elif not v and name not in ['__getattr__', '__setattr__', '__getattribute__']:
        if not mx.is_lvalue:
            for method_name in ('__getattribute__', '__getattr__'):
                method = info.get_method(method_name)
                # __getattribute__ is defined on builtins.object and returns Any, so without
                # the guard this search will always find object.__getattribute__ and conclude
                # that the attribute exists
                if method and method.info.fullname() != 'builtins.object':
                    function = function_type(method, mx.builtin_type('builtins.function'))
                    bound_method = bind_self(function, mx.original_type)
                    typ = map_instance_to_supertype(itype, method.info)
                    getattr_type = expand_type_by_instance(bound_method, typ)
                    if isinstance(getattr_type, CallableType):
                        return getattr_type.ret_type
        else:
            setattr_meth = info.get_method('__setattr__')
            if setattr_meth and setattr_meth.info.fullname() != 'builtins.object':
                setattr_func = function_type(setattr_meth, mx.builtin_type('builtins.function'))
                bound_type = bind_self(setattr_func, mx.original_type)
                typ = map_instance_to_supertype(itype, setattr_meth.info)
                setattr_type = expand_type_by_instance(bound_type, typ)
                if isinstance(setattr_type, CallableType) and len(setattr_type.arg_types) > 0:
                    return setattr_type.arg_types[-1]

    if itype.type.fallback_to_any:
        return AnyType(TypeOfAny.special_form)

    # Could not find the member.
    if mx.is_super:
        mx.msg.undefined_in_superclass(name, mx.context)
        return AnyType(TypeOfAny.from_error)
    else:
        if mx.chk and mx.chk.should_suppress_optional_error([itype]):
            return AnyType(TypeOfAny.from_error)
        return mx.msg.has_no_attr(mx.original_type, itype, name, mx.context)


def check_final_member(name: str, info: TypeInfo, msg: MessageBuilder, ctx: Context) -> None:
    """Give an error if the name being assigned was declared as final."""
    for base in info.mro:
        sym = base.names.get(name)
        if sym and is_final_node(sym.node):
            msg.cant_assign_to_final(name, attr_assign=True, ctx=ctx)


def analyze_descriptor_access(instance_type: Type,
                              descriptor_type: Type,
                              builtin_type: Callable[[str], Instance],
                              msg: MessageBuilder,
                              context: Context, *,
                              chk: 'mypy.checker.TypeChecker') -> Type:
    """Type check descriptor access.

    Arguments:
        instance_type: The type of the instance on which the descriptor
            attribute is being accessed (the type of ``a`` in ``a.f`` when
            ``f`` is a descriptor).
        descriptor_type: The type of the descriptor attribute being accessed
            (the type of ``f`` in ``a.f`` when ``f`` is a descriptor).
        context: The node defining the context of this inference.
    Return:
        The return type of the appropriate ``__get__`` overload for the descriptor.
    """
    if isinstance(descriptor_type, UnionType):
        # Map the access over union types
        return UnionType.make_simplified_union([
            analyze_descriptor_access(instance_type, typ, builtin_type,
                                      msg, context, chk=chk)
            for typ in descriptor_type.items
        ])
    elif not isinstance(descriptor_type, Instance):
        return descriptor_type

    if not descriptor_type.type.has_readable_member('__get__'):
        return descriptor_type

    dunder_get = descriptor_type.type.get_method('__get__')

    if dunder_get is None:
        msg.fail(message_registry.DESCRIPTOR_GET_NOT_CALLABLE.format(descriptor_type), context)
        return AnyType(TypeOfAny.from_error)

    function = function_type(dunder_get, builtin_type('builtins.function'))
    bound_method = bind_self(function, descriptor_type)
    typ = map_instance_to_supertype(descriptor_type, dunder_get.info)
    dunder_get_type = expand_type_by_instance(bound_method, typ)

    if isinstance(instance_type, FunctionLike) and instance_type.is_type_obj():
        owner_type = instance_type.items()[0].ret_type
        instance_type = NoneTyp()
    elif isinstance(instance_type, TypeType):
        owner_type = instance_type.item
        instance_type = NoneTyp()
    else:
        owner_type = instance_type

    _, inferred_dunder_get_type = chk.expr_checker.check_call(
        dunder_get_type,
        [TempNode(instance_type), TempNode(TypeType.make_normalized(owner_type))],
        [ARG_POS, ARG_POS], context)

    if isinstance(inferred_dunder_get_type, AnyType):
        # check_call failed, and will have reported an error
        return inferred_dunder_get_type

    if not isinstance(inferred_dunder_get_type, CallableType):
        msg.fail(message_registry.DESCRIPTOR_GET_NOT_CALLABLE.format(descriptor_type), context)
        return AnyType(TypeOfAny.from_error)

    return inferred_dunder_get_type.ret_type


def instance_alias_type(alias: TypeAlias,
                        builtin_type: Callable[[str], Instance]) -> Type:
    """Type of a type alias node targeting an instance, when appears in runtime context.

    As usual, we first erase any unbound type variables to Any.
    """
    assert isinstance(alias.target, Instance), "Must be called only with aliases to classes"
    target = set_any_tvars(alias.target, alias.alias_tvars, alias.line, alias.column)
    assert isinstance(target, Instance)
    tp = type_object_type(target.type, builtin_type)
    return expand_type_by_instance(tp, target)


def analyze_var(name: str,
                var: Var,
                itype: Instance,
                info: TypeInfo,
                mx: MemberContext, *,
                implicit: bool = False) -> Type:
    """Analyze access to an attribute via a Var node.

    This is conceptually part of analyze_member_access and the arguments are similar.

    itype is the class object in which var is defined
    original_type is the type of E in the expression E.var
    if implicit is True, the original Var was created as an assignment to self
    """
    # Found a member variable.
    itype = map_instance_to_supertype(itype, var.info)
    typ = var.type
    if typ:
        if isinstance(typ, PartialType):
            return mx.chk.handle_partial_var_type(typ, mx.is_lvalue, var, mx.context)
        t = expand_type_by_instance(typ, itype)
        if mx.is_lvalue and var.is_property and not var.is_settable_property:
            # TODO allow setting attributes in subclass (although it is probably an error)
            mx.msg.read_only_property(name, itype.type, mx.context)
        if mx.is_lvalue and var.is_classvar:
            mx.msg.cant_assign_to_classvar(name, mx.context)
        result = t
        if var.is_initialized_in_class and isinstance(t, FunctionLike) and not t.is_type_obj():
            if mx.is_lvalue:
                if var.is_property:
                    if not var.is_settable_property:
                        mx.msg.read_only_property(name, itype.type, mx.context)
                else:
                    mx.msg.cant_assign_to_method(mx.context)

            if not var.is_staticmethod:
                # Class-level function objects and classmethods become bound methods:
                # the former to the instance, the latter to the class.
                functype = t
                # Use meet to narrow original_type to the dispatched type.
                # For example, assume
                # * A.f: Callable[[A1], None] where A1 <: A (maybe A1 == A)
                # * B.f: Callable[[B1], None] where B1 <: B (maybe B1 == B)
                # * x: Union[A1, B1]
                # In `x.f`, when checking `x` against A1 we assume x is compatible with A
                # and similarly for B1 when checking agains B
                dispatched_type = meet.meet_types(mx.original_type, itype)
                check_self_arg(functype, dispatched_type, var.is_classmethod, mx.context, name,
                               mx.msg)
                signature = bind_self(functype, mx.original_type, var.is_classmethod)
                if var.is_property:
                    # A property cannot have an overloaded type => the cast is fine.
                    assert isinstance(signature, CallableType)
                    result = signature.ret_type
                else:
                    result = signature
    else:
        if not var.is_ready:
            mx.not_ready_callback(var.name(), mx.context)
        # Implicit 'Any' type.
        result = AnyType(TypeOfAny.special_form)
    fullname = '{}.{}'.format(var.info.fullname(), name)
    hook = mx.chk.plugin.get_attribute_hook(fullname)
    if result and not mx.is_lvalue and not implicit:
        result = analyze_descriptor_access(mx.original_type, result, mx.builtin_type,
                                           mx.msg, mx.context, chk=mx.chk)
    if hook:
        result = hook(AttributeContext(mx.original_type, result, mx.context, mx.chk))
    return result


def freeze_type_vars(member_type: Type) -> None:
    if isinstance(member_type, CallableType):
        for v in member_type.variables:
            v.id.meta_level = 0
    if isinstance(member_type, Overloaded):
        for it in member_type.items():
            for v in it.variables:
                v.id.meta_level = 0


def lookup_member_var_or_accessor(info: TypeInfo, name: str,
                                  is_lvalue: bool) -> Optional[SymbolNode]:
    """Find the attribute/accessor node that refers to a member of a type."""
    # TODO handle lvalues
    node = info.get(name)
    if node:
        return node.node
    else:
        return None


def check_self_arg(functype: FunctionLike,
                   dispatched_arg_type: Type,
                   is_classmethod: bool,
                   context: Context, name: str,
                   msg: MessageBuilder) -> None:
    """For x.f where A.f: A1 -> T, check that meet(type(x), A) <: A1 for each overload.

    dispatched_arg_type is meet(B, A) in the following example

        def g(x: B): x.f
        class A:
            f: Callable[[A1], None]
    """
    # TODO: this is too strict. We can return filtered overloads for matching definitions
    for item in functype.items():
        if not item.arg_types or item.arg_kinds[0] not in (ARG_POS, ARG_STAR):
            # No positional first (self) argument (*args is okay).
            msg.no_formal_self(name, item, context)
        else:
            selfarg = item.arg_types[0]
            if is_classmethod:
                dispatched_arg_type = TypeType.make_normalized(dispatched_arg_type)
            if not subtypes.is_subtype(dispatched_arg_type, erase_to_bound(selfarg)):
                msg.incompatible_self_argument(name, dispatched_arg_type, item,
                                               is_classmethod, context)


def analyze_class_attribute_access(itype: Instance,
                                   name: str,
                                   mx: MemberContext) -> Optional[Type]:
    """original_type is the type of E in the expression E.var"""
    node = itype.type.get(name)
    if not node:
        if itype.type.fallback_to_any:
            return AnyType(TypeOfAny.special_form)
        return None

    is_decorated = isinstance(node.node, Decorator)
    is_method = is_decorated or isinstance(node.node, FuncBase)
    if mx.is_lvalue:
        if is_method:
            mx.msg.cant_assign_to_method(mx.context)
        if isinstance(node.node, TypeInfo):
            mx.msg.fail(message_registry.CANNOT_ASSIGN_TO_TYPE, mx.context)

    # If a final attribute was declared on `self` in `__init__`, then it
    # can't be accessed on the class object.
    if node.implicit and isinstance(node.node, Var) and node.node.is_final:
        mx.msg.fail(message_registry.CANNOT_ACCESS_FINAL_INSTANCE_ATTR
                    .format(node.node.name()), mx.context)

    # An assignment to final attribute on class object is also always an error,
    # independently of types.
    if mx.is_lvalue and not mx.chk.get_final_context():
        check_final_member(name, itype.type, mx.msg, mx.context)

    if itype.type.is_enum and not (mx.is_lvalue or is_decorated or is_method):
        return itype

    t = node.type
    if t:
        if isinstance(t, PartialType):
            symnode = node.node
            assert isinstance(symnode, Var)
            return mx.chk.handle_partial_var_type(t, mx.is_lvalue, symnode, mx.context)
        if not is_method and (isinstance(t, TypeVarType) or get_type_vars(t)):
            mx.msg.fail(message_registry.GENERIC_INSTANCE_VAR_CLASS_ACCESS, mx.context)
        is_classmethod = ((is_decorated and cast(Decorator, node.node).func.is_class)
                          or (isinstance(node.node, FuncBase) and node.node.is_class))
        result = add_class_tvars(t, itype, is_classmethod, mx.builtin_type, mx.original_type)
        if not mx.is_lvalue:
            result = analyze_descriptor_access(mx.original_type, result, mx.builtin_type,
                                               mx.msg, mx.context, chk=mx.chk)
        return result
    elif isinstance(node.node, Var):
        mx.not_ready_callback(name, mx.context)
        return AnyType(TypeOfAny.special_form)

    if isinstance(node.node, TypeVarExpr):
        mx.msg.fail(message_registry.CANNOT_USE_TYPEVAR_AS_EXPRESSION.format(
                    itype.type.name(), name), mx.context)
        return AnyType(TypeOfAny.from_error)

    if isinstance(node.node, TypeInfo):
        return type_object_type(node.node, mx.builtin_type)

    if isinstance(node.node, MypyFile):
        # Reference to a module object.
        return mx.builtin_type('types.ModuleType')

    if isinstance(node.node, TypeAlias) and isinstance(node.node.target, Instance):
        return instance_alias_type(node.node, mx.builtin_type)

    if is_decorated:
        assert isinstance(node.node, Decorator)
        if node.node.type:
            return node.node.type
        else:
            mx.not_ready_callback(name, mx.context)
            return AnyType(TypeOfAny.from_error)
    else:
        return function_type(cast(FuncBase, node.node), mx.builtin_type('builtins.function'))


def add_class_tvars(t: Type, itype: Instance, is_classmethod: bool,
                    builtin_type: Callable[[str], Instance],
                    original_type: Type) -> Type:
    """Instantiate type variables during analyze_class_attribute_access,
    e.g T and Q in the following:

    def A(Generic(T)):
        @classmethod
        def foo(cls: Type[Q]) -> Tuple[T, Q]: ...

    class B(A): pass

    B.foo()

    original_type is the value of the type B in the expression B.foo()
    """
    # TODO: verify consistency between Q and T
    info = itype.type  # type: TypeInfo
    if isinstance(t, CallableType):
        # TODO: Should we propagate type variable values?
        tvars = [TypeVarDef(n, n, i + 1, [], builtin_type('builtins.object'), tv.variance)
                 for (i, n), tv in zip(enumerate(info.type_vars), info.defn.type_vars)]
        if is_classmethod:
            t = bind_self(t, original_type, is_classmethod=True)
        return t.copy_modified(variables=tvars + t.variables)
    elif isinstance(t, Overloaded):
        return Overloaded([cast(CallableType, add_class_tvars(item, itype, is_classmethod,
                                                              builtin_type, original_type))
                           for item in t.items()])
    return t


def type_object_type(info: TypeInfo, builtin_type: Callable[[str], Instance]) -> Type:
    """Return the type of a type object.

    For a generic type G with type variables T and S the type is generally of form

      Callable[..., G[T, S]]

    where ... are argument types for the __init__/__new__ method (without the self
    argument). Also, the fallback type will be 'type' instead of 'function'.
    """

    # We take the type from whichever of __init__ and __new__ is first
    # in the MRO, preferring __init__ if there is a tie.
    init_method = info.get_method('__init__')
    new_method = info.get_method('__new__')
    if not init_method:
        # Must be an invalid class definition.
        return AnyType(TypeOfAny.from_error)
    # There *should* always be a __new__ method except the test stubs
    # lack it, so just copy init_method in that situation
    new_method = new_method or init_method

    init_index = info.mro.index(init_method.info)
    new_index = info.mro.index(new_method.info)

    fallback = info.metaclass_type or builtin_type('builtins.type')
    if init_index < new_index:
        method = init_method
    elif init_index > new_index:
        method = new_method
    else:
        if init_method.info.fullname() == 'builtins.object':
            # Both are defined by object.  But if we've got a bogus
            # base class, we can't know for sure, so check for that.
            if info.fallback_to_any:
                # Construct a universal callable as the prototype.
                any_type = AnyType(TypeOfAny.special_form)
                sig = CallableType(arg_types=[any_type, any_type],
                                   arg_kinds=[ARG_STAR, ARG_STAR2],
                                   arg_names=["_args", "_kwds"],
                                   ret_type=any_type,
                                   fallback=builtin_type('builtins.function'))
                return class_callable(sig, info, fallback, None)

        # Otherwise prefer __init__ in a tie. It isn't clear that this
        # is the right thing, but __new__ caused problems with
        # typeshed (#5647).
        method = init_method
    # Construct callable type based on signature of __init__. Adjust
    # return type and insert type arguments.
    return type_object_type_from_function(method, info, fallback)


def type_object_type_from_function(init_or_new: FuncBase,
                                   info: TypeInfo,
                                   fallback: Instance) -> FunctionLike:
    signature = bind_self(function_type(init_or_new, fallback))

    # The __init__ method might come from a generic superclass
    # (init_or_new.info) with type variables that do not map
    # identically to the type variables of the class being constructed
    # (info). For example
    #
    #   class A(Generic[T]): def __init__(self, x: T) -> None: pass
    #   class B(A[List[T]], Generic[T]): pass
    #
    # We need to first map B's __init__ to the type (List[T]) -> None.
    signature = cast(FunctionLike,
                     map_type_from_supertype(signature, info, init_or_new.info))
    special_sig = None  # type: Optional[str]
    if init_or_new.info.fullname() == 'builtins.dict':
        # Special signature!
        special_sig = 'dict'

    if isinstance(signature, CallableType):
        return class_callable(signature, info, fallback, special_sig)
    else:
        # Overloaded __init__/__new__.
        assert isinstance(signature, Overloaded)
        items = []  # type: List[CallableType]
        for item in signature.items():
            items.append(class_callable(item, info, fallback, special_sig))
        return Overloaded(items)


def class_callable(init_type: CallableType, info: TypeInfo, type_type: Instance,
                   special_sig: Optional[str]) -> CallableType:
    """Create a type object type based on the signature of __init__."""
    variables = []  # type: List[TypeVarDef]
    variables.extend(info.defn.type_vars)
    variables.extend(init_type.variables)

    callable_type = init_type.copy_modified(
        ret_type=fill_typevars(info), fallback=type_type, name=None, variables=variables,
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
        inst_type = inst_type.fallback
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
    self_param_type = func.arg_types[0]
    if func.variables and (isinstance(self_param_type, TypeVarType) or
                           (isinstance(self_param_type, TypeType) and
                            isinstance(self_param_type.item, TypeVarType))):
        if original_type is None:
            # Type check method override
            # XXX value restriction as union?
            original_type = erase_to_bound(self_param_type)

        ids = [x.id for x in func.variables]
        typearg = infer_type_arguments(ids, self_param_type, original_type)[0]
        if (is_classmethod and isinstance(typearg, UninhabitedType)
                and isinstance(original_type, (Instance, TypeVarType, TupleType))):
            # In case we call a classmethod through an instance x, fallback to type(x)
            # TODO: handle Union
            typearg = infer_type_arguments(ids, self_param_type, TypeType(original_type))[0]

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
    if isinstance(t, TypeVarType):
        return t.upper_bound
    if isinstance(t, TypeType):
        if isinstance(t.item, TypeVarType):
            return TypeType.make_normalized(t.item.upper_bound)
    return t
