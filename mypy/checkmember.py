"""Type checking of attribute access"""

from typing import cast, Callable, List, Optional, TypeVar

from mypy.types import (
    Type, Instance, AnyType, TupleType, TypedDictType, CallableType, FunctionLike, TypeVarDef,
    Overloaded, TypeVarType, UnionType, PartialType, UninhabitedType, TypeOfAny,
    DeletedType, NoneTyp, TypeType, function_type, get_type_vars,
)
from mypy.nodes import (
    TypeInfo, FuncBase, Var, FuncDef, SymbolNode, Context, MypyFile, TypeVarExpr,
    ARG_POS, ARG_STAR, ARG_STAR2,
    Decorator, OverloadedFuncDef,
)
from mypy.messages import MessageBuilder
from mypy.maptype import map_instance_to_supertype
from mypy.expandtype import expand_type_by_instance, expand_type, freshen_function_type_vars
from mypy.infer import infer_type_arguments
from mypy.typevars import fill_typevars
from mypy.plugin import Plugin, AttributeContext
from mypy import messages
from mypy import subtypes
from mypy import meet

MYPY = False
if MYPY:  # import for forward declaration only
    import mypy.checker

from mypy import experiments


def analyze_member_access(name: str,
                          typ: Type,
                          node: Context,
                          is_lvalue: bool,
                          is_super: bool,
                          is_operator: bool,
                          builtin_type: Callable[[str], Instance],
                          not_ready_callback: Callable[[str, Context], None],
                          msg: MessageBuilder, *,
                          original_type: Type,
                          chk: 'mypy.checker.TypeChecker',
                          override_info: Optional[TypeInfo] = None) -> Type:
    """Return the type of attribute `name` of typ.

    This is a general operation that supports various different variations:

      1. lvalue or non-lvalue access (i.e. setter or getter access)
      2. supertype access (when using super(); is_super == True and
         override_info should refer to the supertype)

    original_type is the most precise inferred or declared type of the base object
    that we have available. typ is generally a supertype of original_type.
    When looking for an attribute of typ, we may perform recursive calls targeting
    the fallback type, for example.
    original_type is always the type used in the initial call.
    """
    # TODO: this and following functions share some logic with subtypes.find_member,
    # consider refactoring.
    if isinstance(typ, Instance):
        if name == '__init__' and not is_super:
            # Accessing __init__ in statically typed code would compromise
            # type safety unless used via super().
            msg.fail(messages.CANNOT_ACCESS_INIT, node)
            return AnyType(TypeOfAny.from_error)

        # The base object has an instance type.

        info = typ.type
        if override_info:
            info = override_info

        if (experiments.find_occurrences and
                info.name() == experiments.find_occurrences[0] and
                name == experiments.find_occurrences[1]):
            msg.note("Occurrence of '{}.{}'".format(*experiments.find_occurrences), node)

        # Look up the member. First look up the method dictionary.
        method = info.get_method(name)
        if method:
            if method.is_property:
                assert isinstance(method, OverloadedFuncDef)
                first_item = cast(Decorator, method.items[0])
                return analyze_var(name, first_item.var, typ, info, node, is_lvalue, msg,
                                   original_type, not_ready_callback, chk=chk)
            if is_lvalue:
                msg.cant_assign_to_method(node)
            signature = function_type(method, builtin_type('builtins.function'))
            signature = freshen_function_type_vars(signature)
            if name == '__new__':
                # __new__ is special and behaves like a static method -- don't strip
                # the first argument.
                pass
            else:
                signature = bind_self(signature, original_type)
            typ = map_instance_to_supertype(typ, method.info)
            member_type = expand_type_by_instance(signature, typ)
            freeze_type_vars(member_type)
            return member_type
        else:
            # Not a method.
            return analyze_member_var_access(name, typ, info, node,
                                             is_lvalue, is_super, builtin_type,
                                             not_ready_callback, msg,
                                             original_type=original_type, chk=chk)
    elif isinstance(typ, AnyType):
        # The base object has dynamic type.
        return AnyType(TypeOfAny.from_another_any, source_any=typ)
    elif isinstance(typ, NoneTyp):
        if chk.should_suppress_optional_error([typ]):
            return AnyType(TypeOfAny.from_error)
        # The only attribute NoneType has are those it inherits from object
        return analyze_member_access(name, builtin_type('builtins.object'), node, is_lvalue,
                                     is_super, is_operator, builtin_type, not_ready_callback, msg,
                                     original_type=original_type, chk=chk)
    elif isinstance(typ, UnionType):
        # The base object has dynamic type.
        msg.disable_type_names += 1
        results = [analyze_member_access(name, subtype, node, is_lvalue, is_super,
                                         is_operator, builtin_type, not_ready_callback, msg,
                                         original_type=original_type, chk=chk)
                   for subtype in typ.relevant_items()]
        msg.disable_type_names -= 1
        return UnionType.make_simplified_union(results)
    elif isinstance(typ, TupleType):
        # Actually look up from the fallback instance type.
        return analyze_member_access(name, typ.fallback, node, is_lvalue, is_super,
                                     is_operator, builtin_type, not_ready_callback, msg,
                                     original_type=original_type, chk=chk)
    elif isinstance(typ, TypedDictType):
        # Actually look up from the fallback instance type.
        return analyze_member_access(name, typ.fallback, node, is_lvalue, is_super,
                                     is_operator, builtin_type, not_ready_callback, msg,
                                     original_type=original_type, chk=chk)
    elif isinstance(typ, FunctionLike) and typ.is_type_obj():
        # Class attribute.
        # TODO super?
        ret_type = typ.items()[0].ret_type
        if isinstance(ret_type, TupleType):
            ret_type = ret_type.fallback
        if isinstance(ret_type, Instance):
            if not is_operator:
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
                result = analyze_class_attribute_access(ret_type, name, node, is_lvalue,
                                                        builtin_type, not_ready_callback, msg,
                                                        original_type=original_type)
                if result:
                    return result
            # Look up from the 'type' type.
            return analyze_member_access(name, typ.fallback, node, is_lvalue, is_super,
                                         is_operator, builtin_type, not_ready_callback, msg,
                                         original_type=original_type, chk=chk)
        else:
            assert False, 'Unexpected type {}'.format(repr(ret_type))
    elif isinstance(typ, FunctionLike):
        # Look up from the 'function' type.
        return analyze_member_access(name, typ.fallback, node, is_lvalue, is_super,
                                     is_operator, builtin_type, not_ready_callback, msg,
                                     original_type=original_type, chk=chk)
    elif isinstance(typ, TypeVarType):
        return analyze_member_access(name, typ.upper_bound, node, is_lvalue, is_super,
                                     is_operator, builtin_type, not_ready_callback, msg,
                                     original_type=original_type, chk=chk)
    elif isinstance(typ, DeletedType):
        msg.deleted_as_rvalue(typ, node)
        return AnyType(TypeOfAny.from_error)
    elif isinstance(typ, TypeType):
        # Similar to FunctionLike + is_type_obj() above.
        item = None
        fallback = builtin_type('builtins.type')
        ignore_messages = msg.copy()
        ignore_messages.disable_errors()
        if isinstance(typ.item, Instance):
            item = typ.item
        elif isinstance(typ.item, AnyType):
            return analyze_member_access(name, fallback, node, is_lvalue, is_super,
                                     is_operator, builtin_type, not_ready_callback,
                                     ignore_messages, original_type=original_type, chk=chk)
        elif isinstance(typ.item, TypeVarType):
            if isinstance(typ.item.upper_bound, Instance):
                item = typ.item.upper_bound
        elif isinstance(typ.item, FunctionLike) and typ.item.is_type_obj():
            item = typ.item.fallback
        elif isinstance(typ.item, TypeType):
            # Access member on metaclass object via Type[Type[C]]
            if isinstance(typ.item.item, Instance):
                item = typ.item.item.type.metaclass_type
        if item and not is_operator:
            # See comment above for why operators are skipped
            result = analyze_class_attribute_access(item, name, node, is_lvalue,
                                                    builtin_type, not_ready_callback, msg,
                                                    original_type=original_type)
            if result:
                if not (isinstance(result, AnyType) and item.type.fallback_to_any):
                    return result
                else:
                    # We don't want errors on metaclass lookup for classes with Any fallback
                    msg = ignore_messages
        if item is not None:
            fallback = item.type.metaclass_type or fallback
        return analyze_member_access(name, fallback, node, is_lvalue, is_super,
                                     is_operator, builtin_type, not_ready_callback, msg,
                                     original_type=original_type, chk=chk)

    if chk.should_suppress_optional_error([typ]):
        return AnyType(TypeOfAny.from_error)
    return msg.has_no_attr(original_type, typ, name, node)


def analyze_member_var_access(name: str, itype: Instance, info: TypeInfo,
                              node: Context, is_lvalue: bool, is_super: bool,
                              builtin_type: Callable[[str], Instance],
                              not_ready_callback: Callable[[str, Context], None],
                              msg: MessageBuilder,
                              original_type: Type,
                              chk: 'mypy.checker.TypeChecker') -> Type:
    """Analyse attribute access that does not target a method.

    This is logically part of analyze_member_access and the arguments are similar.

    original_type is the type of E in the expression E.var
    """
    # It was not a method. Try looking up a variable.
    v = lookup_member_var_or_accessor(info, name, is_lvalue)

    vv = v
    if isinstance(vv, Decorator):
        # The associated Var node of a decorator contains the type.
        v = vv.var

    if isinstance(vv, TypeInfo):
        # If the associated variable is a TypeInfo synthesize a Var node for
        # the purposes of type checking.  This enables us to type check things
        # like accessing class attributes on an inner class.
        v = Var(name, type=type_object_type(vv, builtin_type))
        v.info = info

    if isinstance(v, Var):
        return analyze_var(name, v, itype, info, node, is_lvalue, msg,
                           original_type, not_ready_callback, chk=chk)
    elif isinstance(v, FuncDef):
        assert False, "Did not expect a function"
    elif not v and name not in ['__getattr__', '__setattr__', '__getattribute__']:
        if not is_lvalue:
            for method_name in ('__getattribute__', '__getattr__'):
                method = info.get_method(method_name)
                # __getattribute__ is defined on builtins.object and returns Any, so without
                # the guard this search will always find object.__getattribute__ and conclude
                # that the attribute exists
                if method and method.info.fullname() != 'builtins.object':
                    function = function_type(method, builtin_type('builtins.function'))
                    bound_method = bind_self(function, original_type)
                    typ = map_instance_to_supertype(itype, method.info)
                    getattr_type = expand_type_by_instance(bound_method, typ)
                    if isinstance(getattr_type, CallableType):
                        return getattr_type.ret_type
        else:
            setattr_meth = info.get_method('__setattr__')
            if setattr_meth and setattr_meth.info.fullname() != 'builtins.object':
                setattr_func = function_type(setattr_meth, builtin_type('builtins.function'))
                bound_type = bind_self(setattr_func, original_type)
                typ = map_instance_to_supertype(itype, setattr_meth.info)
                setattr_type = expand_type_by_instance(bound_type, typ)
                if isinstance(setattr_type, CallableType) and len(setattr_type.arg_types) > 0:
                    return setattr_type.arg_types[-1]

    if itype.type.fallback_to_any:
        return AnyType(TypeOfAny.special_form)

    # Could not find the member.
    if is_super:
        msg.undefined_in_superclass(name, node)
        return AnyType(TypeOfAny.from_error)
    else:
        if chk and chk.should_suppress_optional_error([itype]):
            return AnyType(TypeOfAny.from_error)
        return msg.has_no_attr(original_type, itype, name, node)


def analyze_var(name: str, var: Var, itype: Instance, info: TypeInfo, node: Context,
                is_lvalue: bool, msg: MessageBuilder, original_type: Type,
                not_ready_callback: Callable[[str, Context], None], *,
                chk: 'mypy.checker.TypeChecker') -> Type:
    """Analyze access to an attribute via a Var node.

    This is conceptually part of analyze_member_access and the arguments are similar.

    itype is the class object in which var is dedined
    original_type is the type of E in the expression E.var
    """
    # Found a member variable.
    itype = map_instance_to_supertype(itype, var.info)
    typ = var.type
    if typ:
        if isinstance(typ, PartialType):
            return handle_partial_attribute_type(typ, is_lvalue, msg, var)
        t = expand_type_by_instance(typ, itype)
        if is_lvalue and var.is_property and not var.is_settable_property:
            # TODO allow setting attributes in subclass (although it is probably an error)
            msg.read_only_property(name, info, node)
        if is_lvalue and var.is_classvar:
            msg.cant_assign_to_classvar(name, node)
        result = t
        if var.is_initialized_in_class and isinstance(t, FunctionLike) and not t.is_type_obj():
            if is_lvalue:
                if var.is_property:
                    if not var.is_settable_property:
                        msg.read_only_property(name, info, node)
                else:
                    msg.cant_assign_to_method(node)

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
                dispatched_type = meet.meet_types(original_type, itype)
                check_self_arg(functype, dispatched_type, var.is_classmethod, node, name, msg)
                signature = bind_self(functype, original_type, var.is_classmethod)
                if var.is_property:
                    # A property cannot have an overloaded type => the cast is fine.
                    assert isinstance(signature, CallableType)
                    result = signature.ret_type
                else:
                    result = signature
    else:
        if not var.is_ready:
            not_ready_callback(var.name(), node)
        # Implicit 'Any' type.
        result = AnyType(TypeOfAny.special_form)
    fullname = '{}.{}'.format(var.info.fullname(), name)
    hook = chk.plugin.get_attribute_hook(fullname)
    if hook:
        result = hook(AttributeContext(original_type, result, node, chk))
    return result


def freeze_type_vars(member_type: Type) -> None:
    if isinstance(member_type, CallableType):
        for v in member_type.variables:
            v.id.meta_level = 0
    if isinstance(member_type, Overloaded):
        for it in member_type.items():
            for v in it.variables:
                v.id.meta_level = 0


def handle_partial_attribute_type(typ: PartialType, is_lvalue: bool, msg: MessageBuilder,
                                  context: Context) -> Type:
    if typ.type is None:
        # 'None' partial type. It has a well-defined type -- 'None'.
        # In an lvalue context we want to preserver the knowledge of
        # it being a partial type.
        if not is_lvalue:
            return NoneTyp()
        return typ
    else:
        msg.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
        return AnyType(TypeOfAny.from_error)


def lookup_member_var_or_accessor(info: TypeInfo, name: str,
                                  is_lvalue: bool) -> Optional[SymbolNode]:
    """Find the attribute/accessor node that refers to a member of a type."""
    # TODO handle lvalues
    node = info.get(name)
    if node:
        return node.node
    else:
        return None


def check_self_arg(functype: FunctionLike, dispatched_arg_type: Type, is_classmethod: bool,
                   context: Context, name: str, msg: MessageBuilder) -> None:
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
                                   context: Context,
                                   is_lvalue: bool,
                                   builtin_type: Callable[[str], Instance],
                                   not_ready_callback: Callable[[str, Context], None],
                                   msg: MessageBuilder,
                                   original_type: Type) -> Optional[Type]:
    """original_type is the type of E in the expression E.var"""
    node = itype.type.get(name)
    if not node:
        if itype.type.fallback_to_any:
            return AnyType(TypeOfAny.special_form)
        return None

    is_decorated = isinstance(node.node, Decorator)
    is_method = is_decorated or isinstance(node.node, FuncDef)
    if is_lvalue:
        if is_method:
            msg.cant_assign_to_method(context)
        if isinstance(node.node, TypeInfo):
            msg.fail(messages.CANNOT_ASSIGN_TO_TYPE, context)

    if itype.type.is_enum and not (is_lvalue or is_decorated or is_method):
        return itype

    t = node.type
    if t:
        if isinstance(t, PartialType):
            symnode = node.node
            assert symnode is not None
            return handle_partial_attribute_type(t, is_lvalue, msg, symnode)
        if not is_method and (isinstance(t, TypeVarType) or get_type_vars(t)):
            msg.fail(messages.GENERIC_INSTANCE_VAR_CLASS_ACCESS, context)
        is_classmethod = is_decorated and cast(Decorator, node.node).func.is_class
        return add_class_tvars(t, itype, is_classmethod, builtin_type, original_type)
    elif isinstance(node.node, Var):
        not_ready_callback(name, context)
        return AnyType(TypeOfAny.special_form)

    if isinstance(node.node, TypeVarExpr):
        msg.fail('Type variable "{}.{}" cannot be used as an expression'.format(
                 itype.type.name(), name), context)
        return AnyType(TypeOfAny.from_error)

    if isinstance(node.node, TypeInfo):
        return type_object_type(node.node, builtin_type)

    if isinstance(node.node, MypyFile):
        # Reference to a module object.
        return builtin_type('types.ModuleType')

    if is_decorated:
        # TODO: Return type of decorated function. This is quick hack to work around #998.
        return AnyType(TypeOfAny.special_form)
    else:
        return function_type(cast(FuncBase, node.node), builtin_type('builtins.function'))


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
        tvars = [TypeVarDef(n, i + 1, [], builtin_type('builtins.object'), tv.variance)
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
    init_method = info.get_method('__init__')
    if not init_method:
        # Must be an invalid class definition.
        return AnyType(TypeOfAny.from_error)
    else:
        fallback = info.metaclass_type or builtin_type('builtins.type')
        if init_method.info.fullname() == 'builtins.object':
            # No non-default __init__ -> look at __new__ instead.
            new_method = info.get_method('__new__')
            if new_method and new_method.info.fullname() != 'builtins.object':
                # Found one! Get signature from __new__.
                return type_object_type_from_function(new_method, info, fallback)
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
        # Construct callable type based on signature of __init__. Adjust
        # return type and insert type arguments.
        return type_object_type_from_function(init_method, info, fallback)


def type_object_type_from_function(init_or_new: FuncBase, info: TypeInfo,
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
    c = callable_type.with_name('"{}"'.format(info.name()))
    return c


def map_type_from_supertype(typ: Type, sub_info: TypeInfo,
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
