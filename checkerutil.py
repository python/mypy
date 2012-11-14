from types import Instance, Typ, Callable, TupleType, Any, TypeVar, FunctionLike, Overloaded
from nodes import TypeInfo, FuncBase, FuncDef, AccessorNode


# Type for reporting parsing context in error messages.
interface Context:
    
    @property
    int line():
        pass


# Collection of Instance types of basic types (object, type, etc.).
class BasicTypes:
    Instance object  # object
    Instance std_type # type
    Typ tuple        # tuple
    Typ function     # function TODO
    
    void __init__(self, Instance object, Instance std_type, Typ tuple, Typ function):
        self.object = object
        self.std_type = std_type
        self.tuple = tuple
        self.function = function


# Return a boolean indicating whether a call expression has a (potentially)
# compatible number of arguments for calling a function. Varargs at caller are
# not checked.
bool is_valid_argc(int nargs, bool is_var_arg, Callable callable):
    if is_var_arg:
        if callable.is_var_arg:
            return True
        else:
            return nargs - 1 <= callable.max_fixed_args
    elif callable.is_var_arg:
        return nargs >= callable.min_args
    else:
        # Neither has varargs.
        return nargs <= len(callable.arg_types) and nargs >= callable.min_args


# Expand the caller argument types in a varargs call. Fixedargc is the maximum
# number of fixed arguments that the target function accepts.
#
# Return (fixed argument types, type of the rest of the arguments). Return
# (nil, nil) if the last (vararg) argument had an invalid type. If the vararg
# argument was not an array (nor dynamic), the last item in the returned
# tuple is nil.
tuple<list<Typ>, Typ> expand_caller_var_args(list<Typ> arg_types, int fixed_argc):
    if isinstance(arg_types[-1], TupleType):
        return arg_types[:-1] + ((TupleType)arg_types[-1]).items, None
    else:
        Typ item_type
        if isinstance(arg_types[-1], Any):
            item_type = Any()
        elif isinstance(arg_types[-1], Instance) and ((Instance)arg_types[-1]).typ.full_name == 'builtins.list':
            # List.
            item_type = ((Instance)arg_types[-1]).args[0]
        else:
            return None, None
        
        if len(arg_types) > fixed_argc:
            return arg_types[:-1], item_type
        else:
            return arg_types[:-1] + [item_type] * (fixed_argc - len(arg_types) + 1), item_type


Callable update_callable_implicit_bounds(Callable t, list<tuple<int, Typ>> arg_types):
    # FIX what if there are existing bounds?
    return Callable(t.arg_types, t.min_args, t.is_var_arg, t.ret_type, t.is_type_obj, t.name, t.variables, arg_types, t.line, t.repr)


# For a non-generic type, return instance type representing the type.
# For a generic G type with parameters T1, .., Tn, return G<T1, ..., Tn>.
Instance self_type(TypeInfo typ):
    list<Typ> tv = []
    for i in range(len(typ.type_vars)):
        tv.append(TypeVar(typ.type_vars[i], i + 1))
    return Instance(typ, tv)


# Return the signature of a function.
FunctionLike function_type(FuncBase func):
    if func.typ is not None:
        return (FunctionLike)func.typ.typ
    else:
        # Implicit type signature with dynamic types.
        
        # Overloaded functions always have a signature, so func must be an
        # ordinary function.
        fdef = (FuncDef)func
        
        name = func.name
        if name is not None:
            name = '"{}"'.format(name)
        return Callable(<Typ> [Any()] * len(fdef.args), fdef.min_args, fdef.var_arg is not None, Any(), False, name)     


# Return the signature of a method (omit self).
FunctionLike method_type(FuncBase func):
    t = function_type(func)
    if isinstance(t, Callable):
        return method_callable((Callable)t)
    else:
        o = (Overloaded)t
        list<Callable> it = []
        for c in o.items():
            it.append(method_callable(c))
        return Overloaded(it)


Callable method_callable(Callable c):
    return Callable(c.arg_types[1:], c.min_args - 1, c.is_var_arg, c.ret_type, c.is_type_obj, c.name, c.variables)


# Return the type of a getter, a setter or a variable.
Typ accessor_type(AccessorNode acc):
    if acc.typ is not None:
        return acc.typ.typ
    # Implicit dynamic type.
    return Any()


# Map type variables in a type defined in a supertype context to be valid
# in the subtype context. Assume that the result is unique; if more than
# one type is possible, return one of the alternatives.
#
# For example, assume
#
#   class D<S> ...
#   class C<T> is D<E<T>> ...
#
# Now S in the context of D would be mapped to E<T> in the context of C.
Typ map_type_from_supertype(Typ typ, TypeInfo sub_info, TypeInfo super_info):
    # Create the type of self in subtype, of form t<a1, ...>.
    inst_type = self_type(sub_info)
    # Map the type of self to supertype. This gets us a description of the
    # supertype type variables in terms of subtype variables, i.e. t<t1, ...>
    # so that any type variables in tN are to be interpreted in subtype
    # context.
    inst_type = map_instance_to_supertype(inst_type, super_info)
    # Finally expand the type variables in type with those in the previously
    # constructed type. Note that both type and instType may have type
    # variables, but in type they are interpreterd in supertype context while
    # in instType they are interpreted in subtype context. This works even if
    # the names of type variables in supertype and subtype overlap.
    return expand_type_by_instance(typ, inst_type)


# Find the original overridden definition of a member (highest type in the
# subclass hierarchy that defines it). If member was first defined in the
# specified type, return nil.
AccessorNode find_original_member_definition(TypeInfo typ, str member):
    AccessorNode n = None
    while typ.base is not None:
        AccessorNode nn = typ.base.get_method(member)
        if nn is None:
            nn = typ.base.get_var_or_getter(member)
        if nn is None:
            break
        n = nn
        typ = n.info
    return n


# If the list has duplicates, return one of the duplicates. Otherwise, return
# nil.
T find_duplicate<T>(list<T> list):
    for i in range(1, len(list)):
        if list[i] in list[:i]:
            return list[i]
    return None
