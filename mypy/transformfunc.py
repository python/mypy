"""Transform functions for runtime type checking."""

from mypy.nodes import (
    FuncDef, Var, Node, Block, TypeInfo, NameExpr, MemberExpr,
    CallExpr, ReturnStmt, ExpressionStmt, TypeExpr, function_type, VarDef
)
from mypy import nodes
from mypy.checker import map_type_from_supertype
from mypy.types import Callable, AnyType, Void, RuntimeTypeVar, Type
from mypy.replacetvars import replace_type_vars
import mypy.transform
from mypy.transutil import (
    is_simple_override, tvar_arg_name, self_expr, dynamic_sig, is_generic,
    add_arg_type_after_self, translate_type_vars_to_bound_vars,
    translate_function_type_vars_to_dynamic, replace_ret_type,
    translate_type_vars_to_wrapper_vars,
    translate_type_vars_to_wrapped_object_vars
)
from mypy.erasetype import erase_generic_types
from typing import Undefined, List, Tuple, cast


# TODO
#  - overloads
#  - generate semantic analysis info during transform (e.g.
#    transformMethodImplementation, Var constructors, NameExpr)


class FuncTransformer:
    """Transform methods for runtime type checking.
    
    This is used by DyncheckTransformVisitor and TypeTransformer is logically
    forms a single unit with these classes.
    """
    # Used for common transformation operations.
    tf = Undefined # type: mypy.transform.DyncheckTransformVisitor
    
    def __init__(self, tf: 'mypy.transform.DyncheckTransformVisitor') -> None:
        self.tf = tf
    
    def transform_method(self, fdef: FuncDef) -> List[FuncDef]:
        """Transform a method.

        The result is one or more methods.
        """
        # Transform the body of the method.
        self.tf.transform_function_body(fdef)
        
        res = Undefined # type: List[FuncDef]
        
        if fdef.is_constructor():
            # The method is a constructor. Constructors are transformed to one
            # method.
            res = [self.transform_method_implementation(fdef, fdef.name())]
        else:
            # Normal methods are transformed to 1-3 variants. The
            # first is the main implementation of the method, and the
            # second is the dynamically-typed wrapper. The third
            # variant is for method overrides, and represents the
            # overridden supertype method.
            
            res = [self.transform_method_implementation(
                fdef, fdef.name() + self.tf.type_suffix(fdef))]
            
            if fdef.info.bases and fdef.info.mro[1].has_method(fdef.name()):
                # Override.
                # TODO do not assume single inheritance
                
                # Is is an override with a different signature? For
                # trivial overrides we can inherit wrappers.
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
    
    def transform_method_implementation(self, fdef: FuncDef, name: str) -> FuncDef:
        """Transform the implementation of a method (i.e. unwrapped)."""
        args = fdef.args
        arg_kinds = fdef.arg_kinds
        
        typ = function_type(fdef) # type: Type
        init = fdef.init_expressions()
        
        if fdef.name() == '__init__' and is_generic(fdef):
            args, arg_kinds, init, typ = self.add_constructor_tvar_args(
                fdef, typ, args, arg_kinds, init)
        
        fdef2 = FuncDef(name, args, arg_kinds, init, fdef.body, typ)
        fdef2.info = fdef.info
        
        self.tf.prepend_generic_function_tvar_args(fdef2)
        
        return fdef2
    
    def \
                     add_constructor_tvar_args(
                             self, fdef: FuncDef, typ: Type,
                             args: List[Var], arg_kinds: List[int], 
                             init: List[Node]) -> Tuple[List[Var], List[int], List[Node], Type]:
        """Add type variable arguments for __init__ of a generic type.

        Return tuple (new args, new kinds, new inits).
        """
        tv = [] # type: List[Var]
        ntvars = len(fdef.info.type_vars)
        for n in range(ntvars):
            tv.append(Var(tvar_arg_name(n + 1)))
            typ = add_arg_type_after_self(cast(Callable, typ), AnyType())
        args = [args[0]] + tv + args[1:]
        arg_kinds = [arg_kinds[0]] + [nodes.ARG_POS] * ntvars + arg_kinds[1:]
        init = List[Node]([None]) * ntvars + init
        return (args, arg_kinds, init, typ)
    
    def override_method_wrapper(self, fdef: FuncDef) -> FuncDef:
        """Construct a method wrapper for an overridden method."""
        orig_fdef = fdef.info.mro[1].get_method(fdef.name())
        return self.method_wrapper(cast(FuncDef, orig_fdef), fdef, False, False)
    
    def dynamic_method_wrapper(self, fdef: FuncDef) -> FuncDef:
        """Construct a dynamically typed method wrapper."""
        return self.method_wrapper(fdef, fdef, True, False)
    
    def generic_method_wrappers(self, fdef: FuncDef) -> List[Node]:
        """Construct wrapper class methods for a method of a generic class."""
        return [self.generic_static_method_wrapper(fdef),
                self.generic_dynamic_method_wrapper(fdef)]
    
    def generic_static_method_wrapper(self, fdef: FuncDef) -> FuncDef:
        """Construct statically typed wrapper class method."""
        return self.method_wrapper(fdef, fdef, False, True)
    
    def generic_dynamic_method_wrapper(self, fdef: FuncDef) -> FuncDef:
        """Construct dynamically-typed wrapper class method."""
        return self.method_wrapper(fdef, fdef, True, True)
    
    def method_wrapper(self, act_as_func_def: FuncDef,
                           target_func_def: FuncDef, is_dynamic: bool,
                           is_wrapper_class: bool) -> FuncDef:
        """Construct a method wrapper.

        It acts as a specific method (with the same signature), coerces
        arguments, calls the target method and finally coerces the return
        value.
        """
        is_override = act_as_func_def.info != target_func_def.info
        
        # Determine suffixes.
        target_suffix = self.tf.type_suffix(target_func_def)
        wrapper_suffix = self.get_wrapper_suffix(act_as_func_def, is_dynamic)
        
        # Determine function signatures.
        target_sig = self.get_target_sig(act_as_func_def, target_func_def,
                                         is_dynamic, is_wrapper_class)
        wrapper_sig = self.get_wrapper_sig(act_as_func_def, is_dynamic)
        call_sig = self.get_call_sig(act_as_func_def, target_func_def.info,
                                     is_dynamic, is_wrapper_class, is_override)
        
        if is_wrapper_class:
            bound_sig = cast(Callable, translate_type_vars_to_bound_vars(target_sig))
        else:
            bound_sig = None
        
        call_stmt = self.call_wrapper(act_as_func_def, is_dynamic,
                                      is_wrapper_class, target_sig, call_sig,
                                      target_suffix, bound_sig)
        
        wrapper_args = self.get_wrapper_args(act_as_func_def, is_dynamic)    
        wrapper_func_def = FuncDef(act_as_func_def.name() + wrapper_suffix,
                                   wrapper_args,
                                   act_as_func_def.arg_kinds, [None] * len(wrapper_args),
                                   Block([call_stmt]),
                                   wrapper_sig)
        
        self.tf.add_line_mapping(target_func_def, wrapper_func_def)
        
        if is_wrapper_class and not is_dynamic:
            self.tf.prepend_generic_function_tvar_args(wrapper_func_def)
        
        return wrapper_func_def
    
    def get_target_sig(self, act_as_func_def: FuncDef,
                            target_func_def: FuncDef,
                            is_dynamic: bool, is_wrapper_class: bool) -> Callable:
        """Return the target method signature for a method wrapper."""
        sig = cast(Callable, function_type(target_func_def))
        if is_wrapper_class:
            if sig.is_generic() and is_dynamic:
                sig = cast(Callable, translate_function_type_vars_to_dynamic(sig))
            return cast(Callable, translate_type_vars_to_wrapped_object_vars(sig))
        elif is_dynamic:
            if sig.is_generic():
                return cast(Callable, translate_function_type_vars_to_dynamic(sig))
            else:
                return sig
        else:
            return sig
    
    def get_wrapper_sig(self, act_as_func_def: FuncDef, is_dynamic: bool) -> Callable:
        """Return the signature of the wrapper method.

        The wrapper method signature has an additional type variable
        argument (with type 'Any'), and all type variables have been
        erased.
        """
        sig = cast(Callable, function_type(act_as_func_def))
        if is_dynamic:
            return dynamic_sig(sig)
        elif is_generic(act_as_func_def):
            return cast(Callable, erase_generic_types(sig)) # FIX REFACTOR?
        else:
            return sig
    
    def get_call_sig(self, act_as_func_def: FuncDef,
                          current_class: TypeInfo, is_dynamic: bool,
                          is_wrapper_class: bool, is_override: bool) -> Callable:
        """Return the source signature in a wrapped call.
        
        It has type variables replaced with 'Any', but as an
        exception, type variables are intact in the return type in
        generic wrapper classes. The exception allows omitting an
        extra return value coercion, as the target return type and the
        source return type will be the same.
        """
        sig = cast(Callable, function_type(act_as_func_def))
        if is_dynamic:
            return dynamic_sig(sig)
        elif is_generic(act_as_func_def):
            call_sig = sig
            # If this is an override wrapper, keep type variables
            # intact. Otherwise replace them with dynamic to get
            # desired coercions that check argument types.
            if not is_override or is_wrapper_class:
                call_sig = (cast(Callable, replace_type_vars(call_sig, False)))
            else:
                call_sig = cast(Callable, map_type_from_supertype(
                    call_sig, current_class, act_as_func_def.info))
            if is_wrapper_class:
                # Replace return type with the original return within
                # wrapper classes to get rid of an unnecessary
                # coercion. There will still be a coercion due to the
                # extra coercion generated for generic wrapper
                # classes. However, function generic type variables
                # still need to be replaced, as the wrapper does not
                # affect them.
                ret = sig.ret_type
                if is_dynamic:
                    ret = translate_function_type_vars_to_dynamic(ret)
                call_sig = replace_ret_type(
                    call_sig, translate_type_vars_to_wrapper_vars(ret))
            return call_sig
        else:
            return sig
    
    def get_wrapper_args(self, act_as_func_def: FuncDef, is_dynamic: bool) -> List[Var]:
        """Return the formal arguments of a wrapper method.

        These may include the type variable argument.
        """
        args = [] # type: List[Var]
        for a in act_as_func_def.args:
            args.append(Var(a.name()))
        return args
    
    def call_wrapper(self, fdef: FuncDef, is_dynamic: bool,
                      is_wrapper_class: bool, target_ann: Callable,
                      cur_ann: Callable, target_suffix: str, bound_sig: Callable) -> Node:
        """Return the body of wrapper method.

        The body contains only a call to the wrapped method and a
        return statement (if the call returns a value). Arguments are coerced
        to the target signature.
        """        
        args = self.call_args(fdef.args, target_ann, cur_ann, is_dynamic,
                              is_wrapper_class, bound_sig,
                              ismethod=fdef.is_method())
        selfarg = args[0]
        args = args[1:]
        
        member = fdef.name() + target_suffix
        if not is_wrapper_class:
            callee = MemberExpr(selfarg, member)
        else:
            callee = MemberExpr(
                MemberExpr(self_expr(), self.tf.object_member_name()), member)
        
        call = CallExpr(callee,
                             args,
                             [nodes.ARG_POS] * len(args), [None] * len(args)) # type: Node
        if bound_sig:
            call = self.tf.coerce(call, bound_sig.ret_type,
                                  target_ann.ret_type, self.tf.type_context(),
                                  is_wrapper_class)
            call = self.tf.coerce(call, cur_ann.ret_type, bound_sig.ret_type,
                                  self.tf.type_context(), is_wrapper_class)
        else:
            call = self.tf.coerce(call, cur_ann.ret_type, target_ann.ret_type,
                                  self.tf.type_context(), is_wrapper_class)
        if not isinstance(target_ann.ret_type, Void):
            return ReturnStmt(call)
        else:
            return ExpressionStmt(call)
    
    def call_args(self, vars: List[Var], target_ann: Callable, cur_ann: Callable,
                     is_dynamic: bool, is_wrapper_class: bool,
                     bound_sig: Callable = None, ismethod: bool = False) -> List[Node]:
        """Construct the arguments of a wrapper call expression.

        Insert coercions as needed.
        """
        args = [] # type: List[Node]
        # Add ordinary arguments, including self (for methods).
        for i in range(len(vars)):
            a = vars[i]
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
        # Add type variable arguments for a generic function.
        for i in range(len(target_ann.variables.items)):
            # Non-dynamic wrapper method in a wrapper class passes
            # generic function type arguments to the target function;
            # otherwise use dynamic types.
            index = i
            if ismethod:
                index += 1
            if is_wrapper_class and not is_dynamic:
                args.insert(index,
                    TypeExpr(RuntimeTypeVar(NameExpr(tvar_arg_name(-i - 1)))))
            else:
                args.insert(index, TypeExpr(AnyType()))
        return args
    
    def get_wrapper_suffix(self, func_def: FuncDef, is_dynamic: bool) -> str:
        if is_dynamic:
            return self.tf.dynamic_suffix()
        else:
            return self.tf.type_suffix(func_def)
