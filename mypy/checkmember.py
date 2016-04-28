"""Type checking of attribute access"""

from typing import cast, Callable, List, Optional

from mypy.types import (
    Type, Instance, AnyType, TupleType, CallableType, FunctionLike, TypeVarDef,
    Overloaded, TypeVarType, TypeTranslator, UnionType, PartialType, DeletedType, NoneTyp
)
from mypy.nodes import TypeInfo, FuncBase, Var, FuncDef, SymbolNode, Context
from mypy.nodes import ARG_POS, ARG_STAR, ARG_STAR2, function_type, Decorator, OverloadedFuncDef
from mypy.messages import MessageBuilder
from mypy.maptype import map_instance_to_supertype
from mypy.expandtype import expand_type_by_instance
from mypy.nodes import method_type, method_type_with_fallback
from mypy.semanal import self_type
from mypy import messages
from mypy import subtypes


def analyze_member_access(name: str, typ: Type, node: Context, is_lvalue: bool,
                          is_super: bool,
                          builtin_type: Callable[[str], Instance],
                          not_ready_callback: Callable[[str, Context], None],
                          msg: MessageBuilder, override_info: TypeInfo = None,
                          report_type: Type = None) -> Type:
    """Analyse attribute access.

    This is a general operation that supports various different variations:

      1. lvalue or non-lvalue access (i.e. setter or getter access)
      2. supertype access (when using super(); is_super == True and
         override_info should refer to the supertype)
    """
    report_type = report_type or typ
    if isinstance(typ, Instance):
        if name == '__init__' and not is_super:
            # Accessing __init__ in statically typed code would compromise
            # type safety unless used via super().
            msg.fail(messages.CANNOT_ACCESS_INIT, node)
            return AnyType()

        # The base object has an instance type.

        info = typ.type
        if override_info:
            info = override_info

        # Look up the member. First look up the method dictionary.
        method = info.get_method(name)
        if method:
            if method.is_property:
                assert isinstance(method, OverloadedFuncDef)
                method = cast(OverloadedFuncDef, method)
                return analyze_var(name, method.items[0].var, typ, info, node, is_lvalue, msg,
                                   not_ready_callback)
            if is_lvalue:
                msg.cant_assign_to_method(node)
            typ = map_instance_to_supertype(typ, method.info)
            if name == '__new__':
                # __new__ is special and behaves like a static method -- don't strip
                # the first argument.
                signature = function_type(method, builtin_type('builtins.function'))
            else:
                signature = method_type_with_fallback(method, builtin_type('builtins.function'))
            return expand_type_by_instance(signature, typ)
        else:
            # Not a method.
            return analyze_member_var_access(name, typ, info, node,
                                             is_lvalue, is_super, builtin_type,
                                             not_ready_callback, msg,
                                             report_type=report_type)
    elif isinstance(typ, AnyType):
        # The base object has dynamic type.
        return AnyType()
    elif isinstance(typ, UnionType):
        # The base object has dynamic type.
        msg.disable_type_names += 1
        results = [analyze_member_access(name, subtype, node, is_lvalue,
                                         is_super, builtin_type, not_ready_callback, msg)
                   for subtype in typ.items]
        msg.disable_type_names -= 1
        return UnionType.make_simplified_union(results)
    elif isinstance(typ, TupleType):
        # Actually look up from the fallback instance type.
        return analyze_member_access(name, typ.fallback, node, is_lvalue,
                                     is_super, builtin_type, not_ready_callback, msg)
    elif isinstance(typ, FunctionLike) and typ.is_type_obj():
        # Class attribute.
        # TODO super?
        ret_type = typ.items()[0].ret_type
        if isinstance(ret_type, TupleType):
            ret_type = ret_type.fallback
        if isinstance(ret_type, Instance):
            result = analyze_class_attribute_access(ret_type, name, node, is_lvalue,
                                                    builtin_type, not_ready_callback, msg)
            if result:
                return result
            # Look up from the 'type' type.
            return analyze_member_access(name, typ.fallback, node, is_lvalue, is_super,
                                         builtin_type, not_ready_callback, msg,
                                         report_type=report_type)
        else:
            assert False, 'Unexpected type {}'.format(repr(ret_type))
    elif isinstance(typ, FunctionLike):
        # Look up from the 'function' type.
        return analyze_member_access(name, typ.fallback, node, is_lvalue, is_super,
                                     builtin_type, not_ready_callback, msg,
                                     report_type=report_type)
    elif isinstance(typ, TypeVarType):
        return analyze_member_access(name, typ.upper_bound, node, is_lvalue, is_super,
                                     builtin_type, not_ready_callback, msg,
                                     report_type=report_type)
    elif isinstance(typ, DeletedType):
        msg.deleted_as_rvalue(typ, node)
        return AnyType()
    return msg.has_no_attr(report_type, name, node)


def analyze_member_var_access(name: str, itype: Instance, info: TypeInfo,
                              node: Context, is_lvalue: bool, is_super: bool,
                              builtin_type: Callable[[str], Instance],
                              not_ready_callback: Callable[[str, Context], None],
                              msg: MessageBuilder,
                              report_type: Type = None) -> Type:
    """Analyse attribute access that does not target a method.

    This is logically part of analyze_member_access and the arguments are
    similar.
    """
    # It was not a method. Try looking up a variable.
    v = lookup_member_var_or_accessor(info, name, is_lvalue)

    vv = v
    if isinstance(vv, Decorator):
        # The associated Var node of a decorator contains the type.
        v = vv.var

    if isinstance(v, Var):
        return analyze_var(name, v, itype, info, node, is_lvalue, msg, not_ready_callback)
    elif isinstance(v, FuncDef):
        assert False, "Did not expect a function"
    elif not v and name not in ['__getattr__', '__setattr__']:
        if not is_lvalue:
            method = info.get_method('__getattr__')
            if method:
                typ = map_instance_to_supertype(itype, method.info)
                getattr_type = expand_type_by_instance(
                    method_type_with_fallback(method, builtin_type('builtins.function')), typ)
                if isinstance(getattr_type, CallableType):
                    return getattr_type.ret_type

    if itype.type.fallback_to_any:
        return AnyType()

    # Could not find the member.
    if is_super:
        msg.undefined_in_superclass(name, node)
        return AnyType()
    else:
        return msg.has_no_attr(report_type or itype, name, node)


def analyze_var(name: str, var: Var, itype: Instance, info: TypeInfo, node: Context,
               is_lvalue: bool, msg: MessageBuilder,
               not_ready_callback: Callable[[str, Context], None]) -> Type:
    """Analyze access to an attribute via a Var node.

    This is conceptually part of analyze_member_access and the arguments are similar.
    """
    # Found a member variable.
    itype = map_instance_to_supertype(itype, var.info)
    typ = var.type
    if typ:
        if isinstance(typ, PartialType):
            return handle_partial_attribute_type(typ, is_lvalue, msg, var)
        t = expand_type_by_instance(typ, itype)
        if var.is_initialized_in_class and isinstance(t, FunctionLike):
            if is_lvalue:
                if var.is_property:
                    if not var.is_settable_property:
                        msg.read_only_property(name, info, node)
                else:
                    msg.cant_assign_to_method(node)

            if not var.is_staticmethod:
                # Class-level function objects and classmethods become bound
                # methods: the former to the instance, the latter to the
                # class.
                functype = cast(FunctionLike, t)
                check_method_type(functype, itype, var.is_classmethod, node, msg)
                signature = method_type(functype)
                if var.is_property:
                    # A property cannot have an overloaded type => the cast
                    # is fine.
                    return cast(CallableType, signature).ret_type
                else:
                    return signature
        return t
    else:
        if not var.is_ready:
            not_ready_callback(var.name(), node)
        # Implicit 'Any' type.
        return AnyType()


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
        return AnyType()


def lookup_member_var_or_accessor(info: TypeInfo, name: str,
                                  is_lvalue: bool) -> SymbolNode:
    """Find the attribute/accessor node that refers to a member of a type."""
    # TODO handle lvalues
    node = info.get(name)
    if node:
        return node.node
    else:
        return None


def check_method_type(functype: FunctionLike, itype: Instance, is_classmethod: bool,
                      context: Context, msg: MessageBuilder) -> None:
    for item in functype.items():
        if not item.arg_types or item.arg_kinds[0] not in (ARG_POS, ARG_STAR):
            # No positional first (self) argument (*args is okay).
            msg.invalid_method_type(item, context)
        elif not is_classmethod:
            # Check that self argument has type 'Any' or valid instance type.
            selfarg = item.arg_types[0]
            if not subtypes.is_equivalent(selfarg, itype):
                msg.invalid_method_type(item, context)
        else:
            # Check that cls argument has type 'Any' or valid class type.
            # (This is sufficient for the current treatment of @classmethod,
            # but probably needs to be revisited when we implement Type[C]
            # or advanced variants of it like Type[<args>, C].)
            clsarg = item.arg_types[0]
            if isinstance(clsarg, CallableType) and clsarg.is_type_obj():
                if not subtypes.is_equivalent(clsarg.ret_type, itype):
                    msg.invalid_class_method_type(item, context)
            else:
                if not subtypes.is_equivalent(clsarg, AnyType()):
                    msg.invalid_class_method_type(item, context)


def analyze_class_attribute_access(itype: Instance,
                                   name: str,
                                   context: Context,
                                   is_lvalue: bool,
                                   builtin_type: Callable[[str], Instance],
                                   not_ready_callback: Callable[[str, Context], None],
                                   msg: MessageBuilder) -> Type:
    node = itype.type.get(name)
    if not node:
        if itype.type.fallback_to_any:
            return AnyType()
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
            return handle_partial_attribute_type(t, is_lvalue, msg, node.node)
        is_classmethod = is_decorated and cast(Decorator, node.node).func.is_class
        return add_class_tvars(t, itype.type, is_classmethod, builtin_type)
    elif isinstance(node.node, Var):
        not_ready_callback(name, context)
        return AnyType()

    if isinstance(node.node, TypeInfo):
        return type_object_type(node.node, builtin_type)

    if is_decorated:
        # TODO: Return type of decorated function. This is quick hack to work around #998.
        return AnyType()
    else:
        return function_type(cast(FuncBase, node.node), builtin_type('builtins.function'))


def add_class_tvars(t: Type, info: TypeInfo, is_classmethod: bool,
                    builtin_type: Callable[[str], Instance]) -> Type:
    if isinstance(t, CallableType):
        # TODO: Should we propagate type variable values?
        vars = [TypeVarDef(n, i + 1, None, builtin_type('builtins.object'), tv.variance)
                for (i, n), tv in zip(enumerate(info.type_vars), info.defn.type_vars)]
        arg_types = t.arg_types
        arg_kinds = t.arg_kinds
        arg_names = t.arg_names
        if is_classmethod:
            arg_types = arg_types[1:]
            arg_kinds = arg_kinds[1:]
            arg_names = arg_names[1:]
        return t.copy_modified(arg_types=arg_types, arg_kinds=arg_kinds, arg_names=arg_names,
                               variables=vars + t.variables)
    elif isinstance(t, Overloaded):
        return Overloaded([cast(CallableType, add_class_tvars(i, info, is_classmethod,
                                                              builtin_type))
                           for i in t.items()])
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
        return AnyType()
    else:
        fallback = builtin_type('builtins.type')
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
                sig = CallableType(arg_types=[AnyType(), AnyType()],
                                   arg_kinds=[ARG_STAR, ARG_STAR2],
                                   arg_names=["_args", "_kwds"],
                                   ret_type=AnyType(),
                                   fallback=builtin_type('builtins.function'))
                return class_callable(sig, info, fallback, None)
        # Construct callable type based on signature of __init__. Adjust
        # return type and insert type arguments.
        return type_object_type_from_function(init_method, info, fallback)


def type_object_type_from_function(init_or_new: FuncBase, info: TypeInfo,
                                   fallback: Instance) -> FunctionLike:
    signature = method_type_with_fallback(init_or_new, fallback)

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

    if init_or_new.info.fullname() == 'builtins.dict':
        # Special signature!
        special_sig = 'dict'
    else:
        special_sig = None

    if isinstance(signature, CallableType):
        return class_callable(signature, info, fallback, special_sig)
    else:
        # Overloaded __init__/__new__.
        items = []  # type: List[CallableType]
        for item in cast(Overloaded, signature).items():
            items.append(class_callable(item, info, fallback, special_sig))
        return Overloaded(items)


def class_callable(init_type: CallableType, info: TypeInfo, type_type: Instance,
                   special_sig: Optional[str]) -> CallableType:
    """Create a type object type based on the signature of __init__."""
    variables = []  # type: List[TypeVarDef]
    for i, tvar in enumerate(info.defn.type_vars):
        variables.append(TypeVarDef(tvar.name, i + 1, tvar.values, tvar.upper_bound,
                                    tvar.variance))

    initvars = init_type.variables
    variables.extend(initvars)

    callable_type = init_type.copy_modified(
        ret_type=self_type(info), fallback=type_type, name=None, variables=variables,
        special_sig=special_sig)
    c = callable_type.with_name('"{}"'.format(info.name()))
    cc = convert_class_tvars_to_func_tvars(c, len(initvars))
    cc.is_classmethod_class = True
    return cc


def convert_class_tvars_to_func_tvars(callable: CallableType,
                                      num_func_tvars: int) -> CallableType:
    return cast(CallableType, callable.accept(TvarTranslator(num_func_tvars)))


class TvarTranslator(TypeTranslator):
    def __init__(self, num_func_tvars: int) -> None:
        super().__init__()
        self.num_func_tvars = num_func_tvars

    def visit_type_var(self, t: TypeVarType) -> Type:
        if t.id < 0:
            return t
        else:
            return TypeVarType(t.name, -t.id - self.num_func_tvars, t.values, t.upper_bound,
                               t.variance)

    def translate_variables(self,
                            variables: List[TypeVarDef]) -> List[TypeVarDef]:
        if not variables:
            return variables
        items = []  # type: List[TypeVarDef]
        for v in variables:
            if v.id > 0:
                items.append(TypeVarDef(v.name, -v.id - self.num_func_tvars,
                                        v.values, v.upper_bound, v.variance))
            else:
                items.append(v)
        return items


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
    inst_type = self_type(sub_info)
    if isinstance(inst_type, TupleType):
        inst_type = inst_type.fallback
    # Map the type of self to supertype. This gets us a description of the
    # supertype type variables in terms of subtype variables, i.e. t[t1, ...]
    # so that any type variables in tN are to be interpreted in subtype
    # context.
    inst_type = map_instance_to_supertype(inst_type, super_info)
    # Finally expand the type variables in type with those in the previously
    # constructed type. Note that both type and inst_type may have type
    # variables, but in type they are interpreterd in supertype context while
    # in inst_type they are interpreted in subtype context. This works even if
    # the names of type variables in supertype and subtype overlap.
    return expand_type_by_instance(typ, inst_type)
