"""Type checking of attribute access"""

from mypy.types import (
    Type, Instance, Any, TupleType, Callable, FunctionLike, TypeVars,
    TypeVarDef, Overloaded, TypeVar, TypeTranslator, BasicTypes
)
from mypy.nodes import TypeInfo, FuncBase, Var, FuncDef, SymbolNode, Context
from mypy.nodes import ARG_POS, function_type, Decorator
from mypy.messages import MessageBuilder
from mypy.subtypes import map_instance_to_supertype
from mypy.expandtype import expand_type_by_instance
from mypy.nodes import method_type
from mypy.semanal import self_type
from mypy import messages
from mypy import subtypes


Type analyse_member_access(str name, Type typ, Context node, bool is_lvalue,
                           bool is_super, BasicTypes basic_types,
                           MessageBuilder msg, TypeInfo override_info=None,
                           Type report_type=None):
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
            return Any()
        
        # The base object has an instance type.
        itype = (Instance)typ
        
        info = itype.type
        if override_info:
            info = override_info
        
        # Look up the member. First look up the method dictionary.
        method = info.get_method(name)
        if method:
            if is_lvalue:
                msg.fail(messages.CANNOT_ASSIGN_TO_METHOD, node)
            itype = map_instance_to_supertype(itype, method.info)
            return expand_type_by_instance(method_type(method), itype)
        else:
            # Not a method.
            return analyse_member_var_access(name, itype, info, node,
                                             is_lvalue, is_super, msg,
                                             report_type=report_type)
    elif isinstance(typ, Any):
        # The base object has dynamic type.
        return Any()
    elif isinstance(typ, TupleType):
        # Actually look up from the 'tuple' type.
        return analyse_member_access(name, basic_types.tuple, node, is_lvalue,
                                     is_super, basic_types, msg)
    elif isinstance(typ, FunctionLike) and ((FunctionLike)typ).is_type_obj():
        # TODO super?
        sig = (FunctionLike)typ
        itype = (Instance)sig.items()[0].ret_type
        result = analyse_class_attribute_access(itype, name, node, is_lvalue,
                                                msg)
        if result:
            return result
        # Look up from the 'type' type.
        return analyse_member_access(name, basic_types.type_type, node,
                                     is_lvalue, is_super, basic_types, msg,
                                     report_type=report_type)
    elif isinstance(typ, FunctionLike):
        # Look up from the 'function' type.
        return analyse_member_access(name, basic_types.function, node,
                                     is_lvalue, is_super, basic_types, msg,
                                     report_type=report_type)
    return msg.has_no_attr(report_type, name, node)


Type analyse_member_var_access(str name, Instance itype, TypeInfo info,
                               Context node, bool is_lvalue, bool is_super,
                               MessageBuilder msg, Type report_type=None):
    """Analyse attribute access that does not target a method.

    This is logically part of analyse_member_access and the arguments are
    similar.
    """
    # It was not a method. Try looking up a variable.
    v = lookup_member_var_or_accessor(info, name, is_lvalue)
    
    if isinstance(v, Decorator):
        # The associated Var node of a decorator contains the type.
        v = ((Decorator)v).var
    
    if isinstance(v, Var):
        # Found a member variable.
        var = (Var)v
        itype = map_instance_to_supertype(itype, var.info)
        if var.type:
            t = expand_type_by_instance(var.type, itype)
            if var.is_initialized_in_class and isinstance(t, FunctionLike):
                # Class-level function object becomes a bound method.
                functype = (FunctionLike)t
                check_method_type(functype, itype, node, msg)
                return method_type(functype)
            return t
        else:
            if not var.is_ready:
                msg.cannot_determine_type(var.name(), node)
            # Implicit 'any' type.
            return Any()
    elif isinstance(v, FuncDef):
        # Found a getter or a setter.
        raise NotImplementedError()
    
    # Could not find the member.
    if is_super:
        msg.undefined_in_superclass(name, node)
        return Any()
    else:
        return msg.has_no_attr(report_type or itype, name, node)


SymbolNode lookup_member_var_or_accessor(TypeInfo info, str name,
                                         bool is_lvalue):
    """Find the attribute/accessor node that refers to a member of a type."""
    # TODO handle lvalues
    node = info.get(name)
    if node:
        return node.node
    else:
        return None


void check_method_type(FunctionLike functype, Instance itype, Context context,
                       MessageBuilder msg):
    for item in functype.items():
        if not item.arg_types or item.arg_kinds[0] != ARG_POS:
            # No positional first (self) argument.
            msg.invalid_method_type(item, context)
        else:
            # Check that self argument has type 'any' or valid instance type.
            selfarg = item.arg_types[0]
            if not subtypes.is_equivalent(selfarg, itype):
                msg.invalid_method_type(item, context)


Type analyse_class_attribute_access(Instance itype, str name, Context context,
                                    bool is_lvalue, MessageBuilder msg):
    node = itype.type.get(name)
    if node:
        if is_lvalue and isinstance(node.node, FuncDef):
            msg.fail(messages.CANNOT_ASSIGN_TO_METHOD, context)
        if is_lvalue and isinstance(node.node, TypeInfo):
            msg.fail(messages.CANNOT_ASSIGN_TO_TYPE, context)
        t = node.type()
        if t:
            return add_class_tvars(t, itype.type)
        elif isinstance(node.node, TypeInfo):
            # TODO add second argument
            return type_object_type((TypeInfo)node.node, None)
        else:
            return function_type((FuncBase)node.node)
    else:
        return None


Type add_class_tvars(Type t, TypeInfo info):
    if isinstance(t, Callable):
        c = (Callable)t
        vars = TypeVars([TypeVarDef(n, i + 1)
                         for i, n in enumerate(info.type_vars)])
        return Callable(c.arg_types,
                        c.arg_kinds,
                        c.arg_names,
                        c.ret_type,
                        c.is_type_obj(),
                        c.name,
                        TypeVars(vars.items + c.variables.items),
                        c.bound_vars,
                        c.line, None)
    elif isinstance(t, Overloaded):
        o = (Overloaded)t
        return Overloaded([(Callable)add_class_tvars(i, info)
                           for i in o.items()])
    return t


Type type_object_type(TypeInfo info, func<Type()> type_type):
    """Return the type of a type object.

    For a generic type G with type variables T and S the type is of form

      def [T, S](...) -> G[T, S],

    where ... are argument types for the __init__ method.
    """
    init_method = info.get_method('__init__')
    if not init_method:
        # Must be an invalid class definition.
        return Any()
    else:
        # Construct callable type based on signature of __init__. Adjust
        # return type and insert type arguments.
        init_type = method_type(init_method)
        if isinstance(init_type, Callable):
            return class_callable((Callable)init_type, info)
        else:
            # Overloaded __init__.
            Callable[] items = []
            for it in ((Overloaded)init_type).items():
                items.append(class_callable(it, info))
            return Overloaded(items)
    

Callable class_callable(Callable init_type, TypeInfo info):
    """Create a type object type based on the signature of __init__."""
    variables = <TypeVarDef> []
    for i in range(len(info.type_vars)): # TODO bounds
        variables.append(TypeVarDef(info.type_vars[i], i + 1, None))

    initvars = init_type.variables.items
    variables.extend(initvars)

    c = Callable(init_type.arg_types,
                 init_type.arg_kinds,
                 init_type.arg_names,
                 self_type(info),
                 True,
                 None,
                 TypeVars(variables)).with_name(
                                      '"{}"'.format(info.name()))
    return convert_class_tvars_to_func_tvars(c, len(initvars))


Callable convert_class_tvars_to_func_tvars(Callable callable,
                                           int num_func_tvars):
    return (Callable)callable.accept(TvarTranslator(num_func_tvars))


class TvarTranslator(TypeTranslator):
    void __init__(self, int num_func_tvars):
        super().__init__()
        self.num_func_tvars = num_func_tvars
    
    Type visit_type_var(self, TypeVar t):
        if t.id < 0:
            return t
        else:
            return TypeVar(t.name, -t.id - self.num_func_tvars)
    
    TypeVars translate_variables(self, TypeVars variables):
        if not variables.items:
            return variables
        items = <TypeVarDef> []
        for v in variables.items:
            if v.id > 0:
                # TODO translate bound
                items.append(TypeVarDef(v.name, -v.id - self.num_func_tvars,
                                        v.bound))
            else:
                items.append(v)
        return TypeVars(items)
