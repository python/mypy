"""Type checking of attribute access"""

from typing import cast, Function, List

from mypy.types import (
    Type, Instance, AnyType, TupleType, Callable, FunctionLike, TypeVarDef,
    Overloaded, TypeVar, TypeTranslator, UnionType
)
from mypy.nodes import TypeInfo, FuncBase, Var, FuncDef, SymbolNode, Context
from mypy.nodes import ARG_POS, function_type, Decorator
from mypy.messages import MessageBuilder
from mypy.maptype import map_instance_to_supertype
from mypy.expandtype import expand_type_by_instance
from mypy.nodes import method_type
from mypy.semanal import self_type
from mypy import messages
from mypy import subtypes


def analyse_member_access(name: str, typ: Type, node: Context, is_lvalue: bool,
                          is_super: bool,
                          builtin_type: Function[[str], Instance],
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
            if is_lvalue:
                msg.cant_assign_to_method(node)
            typ = map_instance_to_supertype(typ, method.info)
            return expand_type_by_instance(
                method_type(method, builtin_type('builtins.function')), typ)
        else:
            # Not a method.
            return analyse_member_var_access(name, typ, info, node,
                                             is_lvalue, is_super, builtin_type,
                                             msg,
                                             report_type=report_type)
    elif isinstance(typ, AnyType):
        # The base object has dynamic type.
        return AnyType()
    elif isinstance(typ, UnionType):
        # The base object has dynamic type.
        msg.disable_type_names += 1
        results = [analyse_member_access(name, subtype, node, is_lvalue,
                                         is_super, builtin_type, msg)
                   for subtype in typ.items]
        msg.disable_type_names -= 1
        return UnionType.make_simplified_union(results)
    elif isinstance(typ, TupleType):
        # Actually look up from the fallback instance type.
        return analyse_member_access(name, typ.fallback, node, is_lvalue,
                                     is_super, builtin_type, msg)
    elif (isinstance(typ, FunctionLike) and
          cast(FunctionLike, typ).is_type_obj()):
        # Class attribute.
        # TODO super?
        sig = cast(FunctionLike, typ)
        itype = cast(Instance, sig.items()[0].ret_type)
        result = analyse_class_attribute_access(itype, name, node, is_lvalue, builtin_type, msg)
        if result:
            return result
        # Look up from the 'type' type.
        return analyse_member_access(name, sig.fallback, node, is_lvalue, is_super,
                                     builtin_type, msg, report_type=report_type)
    elif isinstance(typ, FunctionLike):
        # Look up from the 'function' type.
        return analyse_member_access(name, typ.fallback, node, is_lvalue, is_super,
                                     builtin_type, msg, report_type=report_type)
    return msg.has_no_attr(report_type, name, node)


def analyse_member_var_access(name: str, itype: Instance, info: TypeInfo,
                              node: Context, is_lvalue: bool, is_super: bool,
                              builtin_type: Function[[str], Instance],
                              msg: MessageBuilder,
                              report_type: Type = None) -> Type:
    """Analyse attribute access that does not target a method.

    This is logically part of analyse_member_access and the arguments are
    similar.
    """
    # It was not a method. Try looking up a variable.
    v = lookup_member_var_or_accessor(info, name, is_lvalue)

    vv = v
    if isinstance(vv, Decorator):
        # The associated Var node of a decorator contains the type.
        v = vv.var

    if isinstance(v, Var):
        # Found a member variable.
        var = v
        itype = map_instance_to_supertype(itype, var.info)
        if var.type:
            t = expand_type_by_instance(var.type, itype)
            if var.is_initialized_in_class and isinstance(t, FunctionLike):
                if is_lvalue:
                    if var.is_property:
                        msg.read_only_property(name, info, node)
                    else:
                        msg.cant_assign_to_method(node)

                if not var.is_staticmethod:
                    # Class-level function objects and classmethods become bound
                    # methods: the former to the instance, the latter to the
                    # class.
                    functype = cast(FunctionLike, t)
                    check_method_type(functype, itype, node, msg)
                    signature = method_type(functype)
                    if var.is_property:
                        # A property cannot have an overloaded type => the cast
                        # is fine.
                        return cast(Callable, signature).ret_type
                    else:
                        return signature
            return t
        else:
            if not var.is_ready:
                msg.cannot_determine_type(var.name(), node)
            # Implicit 'Any' type.
            return AnyType()
    elif isinstance(v, FuncDef):
        assert False, "Did not expect a function"
    elif not v and name not in ['__getattr__', '__setattr__']:
        if is_lvalue:
            pass # TODO
        else:
            method = info.get_method('__getattr__')
            if method:
                typ = map_instance_to_supertype(itype, method.info)
                getattr_type = expand_type_by_instance(
                    method_type(method, builtin_type('builtins.function')), typ)
                return getattr_type.ret_type

    # Could not find the member.
    if is_super:
        msg.undefined_in_superclass(name, node)
        return AnyType()
    else:
        return msg.has_no_attr(report_type or itype, name, node)


def lookup_member_var_or_accessor(info: TypeInfo, name: str,
                                  is_lvalue: bool) -> SymbolNode:
    """Find the attribute/accessor node that refers to a member of a type."""
    # TODO handle lvalues
    node = info.get(name)
    if node:
        return node.node
    else:
        return None


def check_method_type(functype: FunctionLike, itype: Instance,
                      context: Context, msg: MessageBuilder) -> None:
    for item in functype.items():
        if not item.arg_types or item.arg_kinds[0] != ARG_POS:
            # No positional first (self) argument.
            msg.invalid_method_type(item, context)
        else:
            # Check that self argument has type 'Any' or valid instance type.
            selfarg = item.arg_types[0]
            if not subtypes.is_equivalent(selfarg, itype):
                msg.invalid_method_type(item, context)


def analyse_class_attribute_access(itype: Instance,
                                   name: str,
                                   context: Context,
                                   is_lvalue: bool,
                                   builtin_type: Function[[str], Instance],
                                   msg: MessageBuilder) -> Type:
    node = itype.type.get(name)
    if not node:
        return None

    is_decorated = isinstance(node.node, Decorator)
    is_method = is_decorated or isinstance(node.node, FuncDef)
    if is_lvalue:
        if is_method:
            msg.cant_assign_to_method(context)
        if isinstance(node.node, TypeInfo):
            msg.fail(messages.CANNOT_ASSIGN_TO_TYPE, context)

    t = node.type
    if t:
        is_classmethod = is_decorated and cast(Decorator, node.node).func.is_class
        return add_class_tvars(t, itype.type, is_classmethod, builtin_type)

    if isinstance(node.node, TypeInfo):
        return type_object_type(cast(TypeInfo, node.node), builtin_type)

    return function_type(cast(FuncBase, node.node), builtin_type('builtins.function'))


def add_class_tvars(t: Type, info: TypeInfo, is_classmethod: bool,
                    builtin_type: Function[[str], Instance]) -> Type:
    if isinstance(t, Callable):
        # TODO: Should we propagate type variable values?
        vars = [TypeVarDef(n, i + 1, None, builtin_type('builtins.object'))
                for i, n in enumerate(info.type_vars)]
        arg_types = t.arg_types
        arg_kinds = t.arg_kinds
        arg_names = t.arg_names
        if is_classmethod:
            arg_types = arg_types[1:]
            arg_kinds = arg_kinds[1:]
            arg_names = arg_names[1:]
        return Callable(arg_types,
                        arg_kinds,
                        arg_names,
                        t.ret_type,
                        t.fallback,
                        t.name,
                        vars + t.variables,
                        t.bound_vars,
                        t.line, None)
    elif isinstance(t, Overloaded):
        return Overloaded([cast(Callable, add_class_tvars(i, info, is_classmethod, builtin_type))
                           for i in t.items()])
    return t


def type_object_type(info: TypeInfo, builtin_type: Function[[str], Instance]) -> Type:
    """Return the type of a type object.

    For a generic type G with type variables T and S the type is of form

      def [T, S](...) -> G[T, S],

    where ... are argument types for the __init__ method (without the self argument).
    """
    init_method = info.get_method('__init__')
    if not init_method:
        # Must be an invalid class definition.
        return AnyType()
    else:
        # Construct callable type based on signature of __init__. Adjust
        # return type and insert type arguments.
        init_type = method_type(init_method, builtin_type('builtins.function'))
        if isinstance(init_type, Callable):
            return class_callable(init_type, info, builtin_type('builtins.type'))
        else:
            # Overloaded __init__.
            items = []  # type: List[Callable]
            for it in cast(Overloaded, init_type).items():
                items.append(class_callable(it, info, builtin_type('builtins.type')))
            return Overloaded(items)


def class_callable(init_type: Callable, info: TypeInfo, type_type: Instance) -> Callable:
    """Create a type object type based on the signature of __init__."""
    variables = []  # type: List[TypeVarDef]
    for i, tvar in enumerate(info.defn.type_vars):
        variables.append(TypeVarDef(tvar.name, i + 1, tvar.values, tvar.upper_bound))

    initvars = init_type.variables
    variables.extend(initvars)

    c = Callable(init_type.arg_types,
                 init_type.arg_kinds,
                 init_type.arg_names,
                 self_type(info),
                 type_type,
                 None,
                 variables).with_name('"{}"'.format(info.name()))
    return convert_class_tvars_to_func_tvars(c, len(initvars))


def convert_class_tvars_to_func_tvars(callable: Callable,
                                      num_func_tvars: int) -> Callable:
    return cast(Callable, callable.accept(TvarTranslator(num_func_tvars)))


class TvarTranslator(TypeTranslator):
    def __init__(self, num_func_tvars: int) -> None:
        super().__init__()
        self.num_func_tvars = num_func_tvars

    def visit_type_var(self, t: TypeVar) -> Type:
        if t.id < 0:
            return t
        else:
            return TypeVar(t.name, -t.id - self.num_func_tvars, t.values, t.upper_bound)

    def translate_variables(self,
                            variables: List[TypeVarDef]) -> List[TypeVarDef]:
        if not variables:
            return variables
        items = []  # type: List[TypeVarDef]
        for v in variables:
            if v.id > 0:
                items.append(TypeVarDef(v.name, -v.id - self.num_func_tvars,
                                        v.values, v.upper_bound))
            else:
                items.append(v)
        return items
