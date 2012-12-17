from nodes import (
    FuncDef, Annotation, Var, Node, Block, TypeInfo, NameExpr, MemberExpr,
    CallExpr, ReturnStmt, ExpressionStmt, TypeExpr, function_type
)
import nodes
from noderepr import FuncRepr
from checker import map_type_from_supertype
from mtypes import Callable, Any, Void, RuntimeTypeVar
from replacetvars import replace_type_vars
import transform
from transutil import (
    is_simple_override, tvar_arg_name, self_expr, dynamic_sig, is_generic,
    func_repr_with_name, prepend_arg_type, prepend_arg_repr,
    translate_type_vars_to_bound_vars, translate_function_type_vars_to_dynamic,
    replace_ret_type, translate_type_vars_to_wrapper_vars,
    translate_type_vars_to_wrapped_object_vars
)
from erasetypes import erase_generic_types


# TODO
#  - overloads
#  - generate semantic analysis info during transform (e.g.
#    transformMethodImplementation, Var constructors, NameExpr)


# Class for transforming methods for runtime type checking.
#
# This is used by DyncheckTransformVisitor and TypeTransformer is logically
# aggregated within these classes.
class FuncTransformer:
    # Used for common transformation operations.
    transform.DyncheckTransformVisitor tf
    
    void __init__(self, transform.DyncheckTransformVisitor tf):
        self.tf = tf
    
    # Transform a method. The result is one or more methods.
    FuncDef[] transform_method(self, FuncDef fdef):
        # Transform the body of the method.
        self.tf.transform_function_body(fdef)
        
        FuncDef[] res
        
        if fdef.is_constructor():
            # The method is a constructor. Constructors are transformed to one
            # method.
            res = [self.transform_method_implementation(fdef, fdef.name())]
        else:
            # Normal methods are transformed to 1-3 variants. The first is the
            # main implementation of the method, and the second is the
            # dynamically-typed wrapper. The third variant is for method overrides,
            # and represents the overridden supertype method.
            
            res = [self.transform_method_implementation(
                fdef, fdef.name() + self.tf.type_suffix(fdef))]
            
            if fdef.info.base and fdef.info.base.has_method(fdef.name()):
                # Override.
                
                # Is is an override with a different signature? For trivial overrides
                # we can inherit wrappers.
                if not is_simple_override(fdef, fdef.info):
                    # Create a wrapper for overridden superclass method.
                    res.append(self.override_method_wrapper(fdef))
                    # Create a dynamically-typed method wrapper.
                    res.append(self.dynamic_method_wrapper(fdef))
            else:
                # Not an override.
                
                # Create a dynamically-typed method wrapper.
                res.append(self.dynamic_method_wrapper(fdef))
        
        return res
    
    # Transform the main variant of the method, which contains the actual body
    # (implementation).
    FuncDef transform_method_implementation(self, FuncDef fdef, str name):
        repr = func_repr_with_name(fdef, name)
        args = fdef.args
        
        typ = Annotation(function_type(fdef))
        init = fdef.init_expressions()
        
        if fdef.name() == 'create' and is_generic(fdef):
            args, repr, init = self.prepend_constructor_tvar_args(fdef, typ, args, repr, init)
        
        fdef2 = FuncDef(name, args, init, None, None, len(args), fdef.body, typ)
        fdef2.repr = repr
        fdef2.info = fdef.info
        
        self.tf.prepend_generic_function_tvar_args(fdef2)
        
        return fdef2
    
    # Prepend type variable argument for constructor of a generic type.
    # Return tuple (new args, new repr, new init).
    tuple<Var[], FuncRepr, Node[]> \
                     prepend_constructor_tvar_args(
                             self, FuncDef fdef, Annotation typ,
                             Var[] args, FuncRepr repr, Node[] init):
        Var[] tv = []
        ntvars = len(fdef.info.type_vars)
        for n in range(ntvars):
            tv.append(Var(tvar_arg_name(n + 1)))
            typ.typ = prepend_arg_type((Callable)typ.typ, Any())
        args = tv + args
        init = <Node> [None] * ntvars + init
        for n in reversed(list(range(ntvars))): # TODO remove list(...)
            repr = prepend_arg_repr(repr, tvar_arg_name(n + 1))
        return (args, repr, init)
    
    # Construct a method wrapper for an overridden method.
    FuncDef override_method_wrapper(self, FuncDef fdef):
        orig_fdef = fdef.info.base.get_method(fdef.name())
        return self.method_wrapper((FuncDef)orig_fdef, fdef, False, False)
    
    # Construct a dynamically-typed method wrapper.
    FuncDef dynamic_method_wrapper(self, FuncDef fdef):
        return self.method_wrapper(fdef, fdef, True, False)
    
    # Construct wrapper class methods for a method of a generic class.
    FuncDef[] generic_method_wrappers(self, FuncDef fdef):
        return [self.generic_static_method_wrapper(fdef), self.generic_dynamic_method_wrapper(fdef)]
    
    # Construct statically-typed wrapper class method.
    FuncDef generic_static_method_wrapper(self, FuncDef fdef):
        return self.method_wrapper(fdef, fdef, False, True)
    
    # Construct dynamically-typed wrapper class method.
    FuncDef generic_dynamic_method_wrapper(self, FuncDef fdef):
        return self.method_wrapper(fdef, fdef, True, True)
    
    # Construct a method wrapper that acts as a specific method, coerces
    # arguments, calls the target method and finally coerces the return value.
    FuncDef method_wrapper(self, FuncDef act_as_func_def, FuncDef target_func_def, bool is_dynamic, bool is_wrapper_class):
        is_override = act_as_func_def.info != target_func_def.info
        
        # Determine suffixes.
        target_suffix = self.tf.type_suffix(target_func_def)
        wrapper_suffix = self.get_wrapper_suffix(act_as_func_def, is_dynamic)
        
        # Determine function signatures.
        target_sig = self.get_target_sig(act_as_func_def, target_func_def, is_dynamic, is_wrapper_class)
        wrapper_sig = self.get_wrapper_sig(act_as_func_def, is_dynamic)
        call_sig = self.get_call_sig(act_as_func_def, target_func_def.info, is_dynamic, is_wrapper_class, is_override)
        
        Callable bound_sig = None
        if is_wrapper_class:
            bound_sig = (Callable)translate_type_vars_to_bound_vars(target_sig)
        
        call_stmt = self.call_wrapper(act_as_func_def, is_dynamic, is_wrapper_class, target_sig, call_sig, target_suffix, bound_sig)
        
        wrapper_args = self.get_wrapper_args(act_as_func_def, is_dynamic)    
        wrapper_func_def = FuncDef(act_as_func_def.name() + wrapper_suffix,
                                   wrapper_args,
                                   <Node> [None] * len(wrapper_args),
                                   None, None, len(wrapper_args),
                                   Block([call_stmt]), Annotation(wrapper_sig))
        
        self.tf.add_line_mapping(target_func_def, wrapper_func_def)
        
        if is_wrapper_class and not is_dynamic:
            self.tf.prepend_generic_function_tvar_args(wrapper_func_def)
        
        return wrapper_func_def
    
    # Return the target method signature for a method wrapper.
    Callable get_target_sig(self, FuncDef act_as_func_def, FuncDef target_func_def, bool is_dynamic, bool is_wrapper_class):
        sig = (Callable)function_type(target_func_def)
        if is_wrapper_class:
            if sig.is_generic() and is_dynamic:
                sig = (Callable)translate_function_type_vars_to_dynamic(sig)
            return (Callable)translate_type_vars_to_wrapped_object_vars(sig)
        elif is_dynamic:
            if sig.is_generic():
                return (Callable)translate_function_type_vars_to_dynamic(sig)        
            else:
                return sig
        else:
            return sig
    
    # Return the signature of the wrapper method. The wrapper method signature
    # has an additional type variable argument (with type "dynamic"), and all
    # type variables have been erased.
    Callable get_wrapper_sig(self, FuncDef act_as_func_def, bool is_dynamic):
        sig = (Callable)function_type(act_as_func_def)
        if is_dynamic:
            return dynamic_sig(sig)
        elif is_generic(act_as_func_def):
            return (Callable)erase_generic_types(sig) # FIX REFACTOR?
        else:
            return sig
    
    # Return the signature used for as the source signature in a wrapped call.
    # It has type variables replaced with "dynamic", but as an
    # exception, type variables are intact in the return type in generic
    # wrapper classes. The exception allows omitting an extra return value
    # coercion, as the target return type and the source return type will be
    # the same.
    Callable get_call_sig(self, FuncDef act_as_func_def, TypeInfo current_class, bool is_dynamic, bool is_wrapper_class, bool is_override):
        sig = (Callable)function_type(act_as_func_def)
        if is_dynamic:
            return dynamic_sig(sig)
        elif is_generic(act_as_func_def):
            call_sig = sig
            # If this is an override wrapper, keep type variables intact. Otherwise
            # replace them with dynamic to get desired coercions that check argument
            # types.
            if not is_override or is_wrapper_class:
                call_sig = ((Callable)replace_type_vars(call_sig, False))
            else:
                call_sig = (Callable)map_type_from_supertype(call_sig, current_class, act_as_func_def.info)
            if is_wrapper_class:
                # Replace return type with the original return within wrapper classes
                # to get rid of an unnecessary coercion. There will still be a
                # coercion due to the extra coercion generated for generic wrapper
                # classes. However, function generic type variables still need to be
                # replaced, as the wrapper does not affect them.
                ret = sig.ret_type
                if is_dynamic:
                    ret = translate_function_type_vars_to_dynamic(ret)
                call_sig = replace_ret_type(call_sig, translate_type_vars_to_wrapper_vars(ret))
            return call_sig
        else:
            return sig
    
    # Return the formal arguments of a wrapper method. These may include the
    # type variable argument.
    Var[] get_wrapper_args(self, FuncDef act_as_func_def, bool is_dynamic):
        Var[] args = []
        for a in act_as_func_def.args:
            args.append(Var(a.name()))
        return args
    
    # Return the body of wrapper method. The body contains only a call to the
    # wrapped method and a return statement (if the call returns a value).
    Node call_wrapper(self, FuncDef fdef, bool is_dynamic, bool is_wrapper_class, Callable target_ann, Callable cur_ann, str target_suffix, Callable bound_sig):
        Node callee
        member = fdef.name() + target_suffix
        if not is_wrapper_class:
            callee = NameExpr(member)
        else:
            callee = MemberExpr(MemberExpr(self_expr(), self.tf.object_member_name()), member)
        args = self.call_args(fdef, target_ann, cur_ann, is_dynamic, is_wrapper_class, bound_sig)
        Node call = CallExpr(callee,
                             args,
                             [nodes.ARG_POS] * len(args),
                             <str> [None] * len(args))
        if bound_sig is not None:
            call = self.tf.coerce(call, bound_sig.ret_type, target_ann.ret_type, self.tf.type_context(), is_wrapper_class)
            call = self.tf.coerce(call, cur_ann.ret_type, bound_sig.ret_type, self.tf.type_context(), is_wrapper_class)
        else:
            call = self.tf.coerce(call, cur_ann.ret_type, target_ann.ret_type, self.tf.type_context(), is_wrapper_class)
        if not isinstance(target_ann.ret_type, Void):
            return ReturnStmt(call)
        else:
            return ExpressionStmt(call)
    
    # Construct the arguments of a wrapper call expression. Insert coercions as
    # needed.
    Node[] call_args(self, FuncDef fdef, Callable target_ann, Callable cur_ann, bool is_dynamic, bool is_wrapper_class, Callable bound_sig=None):
        Node[] args = []
        # Add type variable arguments for a generic function.
        for i in range(len(target_ann.variables.items)):
            # Non-dynamic wrapper method in a wrapper class passes generic function
            # type arguments to the target function; otherwise use dynamic types.
            if is_wrapper_class and not is_dynamic:
                args.append(TypeExpr(RuntimeTypeVar(NameExpr(tvar_arg_name(-i - 1)))))
            else:
                args.append(TypeExpr(Any()))
        for i in range(len(fdef.args)):
            a = fdef.args[i]
            name = NameExpr(a.name())
            if bound_sig is None:
                args.append(self.tf.coerce(name, target_ann.arg_types[i],
                                           cur_ann.arg_types[i],
                                           self.tf.type_context(),
                                           is_wrapper_class))
            else:
                c = self.tf.coerce(name, bound_sig.arg_types[i],
                                   cur_ann.arg_types[i],
                                   self.tf.type_context(), is_wrapper_class)
                args.append(self.tf.coerce(c, target_ann.arg_types[i],
                                           bound_sig.arg_types[i],
                                           self.tf.type_context(),
                                           is_wrapper_class))
        return args
    
    str get_wrapper_suffix(self, FuncDef func_def, bool is_dynamic):
        if is_dynamic:
            return self.tf.dynamic_suffix()
        else:
            return self.tf.type_suffix(func_def)
