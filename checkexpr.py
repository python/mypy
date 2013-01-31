"""Expression type checker. This file is conceptually part of TypeChecker."""

from mtypes import (
    Type, Any, Callable, Overloaded, NoneTyp, Void, TypeVarDef, TypeVars,
    TupleType, Instance, TypeVar, TypeTranslator, ErasedType
)
from nodes import (
    NameExpr, RefExpr, Var, FuncDef, OverloadedFuncDef, TypeInfo, CallExpr,
    Node, MemberExpr, IntExpr, StrExpr, BytesExpr, FloatExpr, OpExpr,
    UnaryExpr, IndexExpr, CastExpr, TypeApplication, ListExpr, TupleExpr,
    DictExpr, FuncExpr, SuperExpr, ParenExpr, SliceExpr, Context,
    ListComprehension, GeneratorExpr
)
from nodes import function_type, method_type
import nodes
import checker
import mtypes
from sametypes import is_same_type
from replacetvars import replace_func_type_vars, replace_type_vars
from messages import MessageBuilder
import messages
from infer import infer_type_arguments, infer_function_type_arguments
import join
from expandtype import expand_type, expand_caller_var_args
from subtypes import is_subtype
import erasetype
from checkmember import analyse_member_access
from semanal import self_type
from constraints import get_actual_type


class ExpressionChecker:
    """Expression type checker.

    This clas works closely together with checker.TypeChecker.
    """
    # Some services are provided by a TypeChecker instance.
    checker.TypeChecker chk
    # This is shared with TypeChecker, but stored also here for convenience.
    MessageBuilder msg    
    
    void __init__(self,
                  checker.TypeChecker chk,
                  MessageBuilder msg):
        """Construct an expression type checker."""
        self.chk = chk
        self.msg = msg
    
    Type visit_name_expr(self, NameExpr e):
        """Type check a name expression (of any kind: local, member or
        global)."""
        return self.analyse_ref_expr(e)
    
    Type analyse_ref_expr(self, RefExpr e):
        Type result
        node = e.node
        if isinstance(node, Var):
            # Variable or constant reference.
            v = (Var)node
            if not v.type:
                # Implicit dynamic type.
                result = Any()
            else:
                # Local or global variable.
                result = v.type
        elif isinstance(node, FuncDef):
            # Reference to a global function.
            f = (FuncDef)node
            result = function_type(f)
        elif isinstance(node, OverloadedFuncDef):
            o = (OverloadedFuncDef)node
            result = o.type
        elif isinstance(node, TypeInfo):
            # Reference to a type object.
            result = type_object_type((TypeInfo)node, self.chk.type_type)
        else:
            # Unknown reference; use dynamic type implicitly to avoid
            # generating extra type errors.
            result = Any()
        return result
    
    Type analyse_direct_member_access(self, str name, TypeInfo info,
                                     bool is_lvalue, Context context):
        """Analyse direct member access via a name expression
        (implicit self). This can access private definitions.
        """
        raise RuntimeError('Not implemented')
    
    Type visit_call_expr(self, CallExpr e):
        """Type check a call expression."""
        self.accept(e.callee)
        # Access callee type directly, since accept may return the any type
        # even if the type is known (in a dynamically typed function). This
        # way we get a more precise callee in dynamically typed functions.
        callee_type = self.chk.type_map[e.callee]
        return self.check_call_expr_with_callee_type(callee_type, e)
    
    Type check_call_expr_with_callee_type(self, Type callee_type, CallExpr e):
        """Type check call expression. The given callee type overrides
        the type of the callee expression.
        """
        return self.check_call(callee_type, e.args, e.arg_kinds, e,
                               e.arg_names, callable_node=e.callee)
    
    Type check_call(self, Type callee, Node[] args, int[] arg_kinds,
                   Context context, str[] arg_names=None,
                   Node callable_node=None):
        """Type check a call.

        Also infer type arguments if the callee is a generic function.

        Arguments:
          callee: type of the called value
          args: actual argument expressions
          arg_kinds: contains nodes.ARG_* constant for each argument in args
            describing whether the argument is positional, *arg, etc.
          arg_names: names of arguments (optional)
          callable_node: associate the inferred callable type to this node,
            if specified
        """
        is_var_arg = nodes.ARG_STAR in arg_kinds
        if isinstance(callee, Callable):
            callable = (Callable)callee
            
            formal_to_actual = map_actuals_to_formals(
                arg_kinds, arg_names,
                callable.arg_kinds, callable.arg_names,
                lambda i: self.accept(args[i]))
            
            if callable.is_generic():
                callable = self.infer_function_type_arguments_using_context(
                    callable)
                callable = self.infer_function_type_arguments(
                    callable, args, arg_kinds, formal_to_actual, context)
            
            arg_types = self.infer_arg_types_in_context2(
                callable, args, arg_kinds, formal_to_actual)

            self.check_argument_count(callable, arg_types, arg_kinds,
                                      arg_names, formal_to_actual, context)
            
            self.check_argument_types(arg_types, arg_kinds, callable,
                                      formal_to_actual, context)
            if callable_node:
                # Store the inferred callable type.
                self.chk.store_type(callable_node, callable)
            return callable.ret_type
        elif isinstance(callee, Overloaded):
            # Type check arguments in empty context. They will be checked again
            # later in a context derived from the signature; these types are
            # only used to pick a signature variant.
            self.msg.disable_errors()
            arg_types = self.infer_arg_types_in_context(None, args)
            self.msg.enable_errors()
            
            target = self.overload_call_target(arg_types, is_var_arg,
                                               (Overloaded)callee, context)
            return self.check_call(target, args, arg_kinds, context, arg_names)
        elif isinstance(callee, Any) or self.chk.is_dynamic_function():
            self.infer_arg_types_in_context(None, args)
            return Any()
        else:
            return self.msg.not_callable(callee, context)
    
    Type[] infer_arg_types_in_context(self, Callable callee,
                                     Node[] args):
        """Infer argument expression types using a callable type as context.

        For example, if callee argument 2 has type int[], infer the argument
        expression with int[] type context.
        """
        Type[] res = []
        
        fixed = len(args)
        if callee:
            fixed = min(fixed, callee.max_fixed_args())
        
        for i in range(fixed):
            arg = args[i]#FIX refactor
            Type ctx = None
            if callee and i < len(callee.arg_types):
                ctx = callee.arg_types[i]
            res.append(self.accept(arg, ctx))
        
        for j in range(fixed, len(args)):
            if callee and callee.is_var_arg:
                res.append(self.accept(args[j], callee.arg_types[-1]))
            else:
                res.append(self.accept(args[j]))
        
        return res
    
    Type[] infer_arg_types_in_context2(self, Callable callee,
                                      Node[] args,
                                      int[] arg_kinds,
                                      int[][] formal_to_actual):
        """Infer argument expression types using a callable type as context.

        For example, if callee argument 2 has type int[], infer the argument
        exprsession with int[] type context.

        Returns the inferred types of *actual arguments*.
        """
        Type[] res = <Type> [None] * len(args)

        for i, actuals in enumerate(formal_to_actual):
            for ai in actuals:
                if arg_kinds[ai] != nodes.ARG_STAR:
                    res[ai] = self.accept(args[ai], callee.arg_types[i])

        # Fill in the rest of the argument types.
        for i, t in enumerate(res):
            if not t:
                res[i] = self.accept(args[i])
        return res
    
    Callable infer_function_type_arguments_using_context(self,
                                                         Callable callable):
        """Unify callable return type to type context to infer type vars.

        For example, if the return type is set<t> where 't' is a type variable
        of callable, and if the context is set<int>, return callable modified
        by substituting 't' with 'int'.
        """
        ctx = self.chk.type_context[-1]
        if not ctx:
            return callable
        # The return type may have references to function type variables that
        # we are inferring right now. We must consider them as indeterminate
        # and they are not potential results; thus we replace them with the
        # None type. On the other hand, class type variables are valid results.
        erased_ctx = replace_func_type_vars(ctx, ErasedType())
        args = infer_type_arguments(callable.type_var_ids(), callable.ret_type,
                                    erased_ctx, self.chk.basic_types())
        # Only substite non-None and non-erased types.
        new_args = <Type> []
        for arg in args:
            if isinstance(arg, NoneTyp) or has_erased_component(arg):
                new_args.append(None)
            else:
                new_args.append(arg)
        return (Callable)self.apply_generic_arguments(callable, new_args, None)
    
    Callable infer_function_type_arguments(self, Callable callee_type,
                                           Node[] args,
                                           int[] arg_kinds,
                                           int[][] formal_to_actual,
                                           Context context):
        """Infer the type arguments for a generic callee type.

        Infer based on the types of arguments.

        Return a derived callable type that has the arguments applied (and
        stored as implicit type arguments).
        """
        if not self.chk.is_dynamic_function():
            # Disable type errors during type inference. There may be errors
            # due to partial available context information at this time, but
            # these errors can be safely ignored as the arguments will be
            # inferred again later.
            self.msg.disable_errors()
            
            arg_types = self.infer_arg_types_in_context2(
                callee_type, args, arg_kinds, formal_to_actual)
        
            self.msg.enable_errors()

            arg_pass_nums = self.get_arg_infer_passes(
                callee_type.arg_types, formal_to_actual, len(args))

            pass1_args = <Type> []
            for i, arg in enumerate(arg_types):
                if arg_pass_nums[i] > 1:
                    pass1_args.append(None)
                else:
                    pass1_args.append(arg)
            
            Type[] inferred_args = infer_function_type_arguments(
                callee_type, pass1_args, arg_kinds, formal_to_actual,
                self.chk.basic_types())

            if 2 in arg_pass_nums:
                # Second pass of type inference.
                (callee_type,
                 inferred_args) = self.infer_function_type_arguments_pass2(
                    callee_type, args, arg_kinds, formal_to_actual,
                    inferred_args, context)
        else:
            # In dynamically typed functions use implicit 'any' types for
            # type variables.
            inferred_args = <Type> [Any()] * len(callee_type.variables.items)
        return self.apply_inferred_arguments(callee_type, inferred_args,
                                             context)

    tuple<Callable, Type[]> infer_function_type_arguments_pass2(
                                 self, Callable callee_type,
                                 Node[] args,
                                 int[] arg_kinds,
                                 int[][] formal_to_actual,
                                 Type[] inferred_args,
                                 Context context):
        """Perform second pass of generic function type argument inference.

        The second pass is needed for arguments with types such as func<s(t)>,
        where both s and t are type variables, when the actual argument is a
        lambda with inferred types.  The idea is to infer the type variable t
        in the first pass (based on the types of other arguments).  This lets
        us infer the argument and return type of the lambda expression and
        thus also the type variable s in this second pass.

        Return (the callee with type vars applied, inferred actual arg types).
        """
        # None or erased types in inferred types mean that there was not enough
        # information to infer the argument. Replace them with None values so
        # that they are not applied yet below.
        for i, arg in enumerate(inferred_args):
            if isinstance(arg, NoneTyp) or isinstance(arg, ErasedType):
                inferred_args[i] = None

        callee_type = (Callable)self.apply_generic_arguments(
            callee_type, inferred_args, context)
        arg_types = self.infer_arg_types_in_context2(
            callee_type, args, arg_kinds, formal_to_actual)

        inferred_args = infer_function_type_arguments(
            callee_type, arg_types, arg_kinds, formal_to_actual,
            self.chk.basic_types())

        return callee_type, inferred_args

    int[] get_arg_infer_passes(self, Type[] arg_types,
                               int[][] formal_to_actual,
                               int num_actuals):
        """Return pass numbers for args for two-pass argument type inference.

        For each actual, the pass number is either 1 (first pass) or 2 (second
        pass).

        Two-pass argument type inference primarily lets us infer lambdas
        better.
        """
        res = [1] * num_actuals
        for i, arg in enumerate(arg_types):
            if arg.accept(ArgInferSecondPassQuery()):
                for j in formal_to_actual[i]:
                    res[j] = 2
        return res
    
    Callable apply_inferred_arguments(self, Callable callee_type,
                                      Type[] inferred_args,
                                      Context context):
        """Apply inferred values of type arguments to a generic function.

        If implicit_type_vars are given, they correspond to the ids of
        the implicit instance type variables; they are stored as the
        prefix of inferred_args.  Inferred_args contains first the
        values of implicit instance type vars (if any), and then
        values of function type variables, concatenated together.
        """
        # Report error if some of the variables could not be solved. In that
        # case assume that all variables have type dynamic to avoid extra
        # bogus error messages.
        for i in range(len(inferred_args)):
            inferred_type = inferred_args[i]
            if not inferred_type:
                # Could not infer a non-trivial type for a type variable.
                self.msg.could_not_infer_type_arguments(
                    callee_type, i + 1, context)
                inferred_args = <Type> [Any()] * len(inferred_args)
        
        # Apply the inferred types to the function type. In this case the
        # return type must be Callable, since we give the right number of type
        # arguments.
        return (Callable)self.apply_generic_arguments(callee_type,
                                                      inferred_args, None)

    void check_argument_count(self, Callable callee, Type[] actual_types,
                              int[] actual_kinds,  str[] actual_names,
                              int[][] formal_to_actual, Context context):
        """Check that the number of arguments to a function are valid.

        Also check that there are no duplicate values for arguments.
        """
        formal_kinds = callee.arg_kinds

        # Collect list of all actual arguments matched to formal arguments.
        all_actuals = <int> []
        for actuals in formal_to_actual:
            all_actuals.extend(actuals)

        is_error = False # Keep track of errors to avoid duplicate errors.
        for i, kind in enumerate(actual_kinds):
            if i not in all_actuals and (
                    kind != nodes.ARG_STAR or
                    not is_empty_tuple(actual_types[i])):
                # Extra actual: not matched by a formal argument.
                if kind != nodes.ARG_NAMED:
                    self.msg.too_many_arguments(callee, context)
                else:
                    self.msg.unexpected_keyword_argument(
                        callee, actual_names[i], context)
                    is_error = True
            elif kind == nodes.ARG_STAR and (
                    nodes.ARG_STAR not in formal_kinds):
                actual_type = actual_types[i]
                if isinstance(actual_type, TupleType):
                    tuplet = (TupleType)actual_type
                    if all_actuals.count(i) < len(tuplet.items):
                        # Too many tuple items as some did not match.
                        self.msg.too_many_arguments(callee, context)
                # *args can be applied even if the function takes a fixed
                # number of positional arguments. This may succeed at runtime.

        for i, kind in enumerate(formal_kinds):
            if kind == nodes.ARG_POS and (not formal_to_actual[i] and
                                          not is_error):
                # No actual for a mandatory positional formal.
                self.msg.too_few_arguments(callee, context)
            elif kind in [nodes.ARG_POS, nodes.ARG_OPT,
                          nodes.ARG_NAMED] and is_duplicate_mapping(
                                                    formal_to_actual[i],
                                                    actual_kinds):
                self.msg.duplicate_argument_value(callee, i, context)
            elif (kind == nodes.ARG_NAMED and formal_to_actual[i] and
                  actual_kinds[formal_to_actual[i][0]] != nodes.ARG_NAMED):
                # Positional argument when expecting a keyword argument.
                self.msg.too_many_positional_arguments(callee, context)
    
    void check_argument_types(self, Type[] arg_types, int[] arg_kinds,
                               Callable callee, int[][] formal_to_actual,
                               Context context):
        """Check argument types against a callable type.

        Report errors if the argument types are not compatible.
        """
        # Keep track of consumed tuple *arg items.
        tuple_counter = [0]
        for i, actuals in enumerate(formal_to_actual):
            for actual in actuals:
                arg_type = arg_types[actual]
                # Check that a *arg is valid as varargs.
                if (arg_kinds[actual] == nodes.ARG_STAR and
                        not self.is_valid_var_arg(arg_type)):
                    self.msg.invalid_var_arg(arg_type, context)
                if (arg_kinds[actual] == nodes.ARG_STAR2 and
                        not self.is_valid_keyword_var_arg(arg_type)):
                    self.msg.invalid_keyword_var_arg(arg_type, context)
                # Get the type of an inidividual actual argument (for *args
                # and **args this is the item type, not the collection type).
                actual_type = get_actual_type(arg_type, arg_kinds[actual],
                                              tuple_counter)
                self.check_arg(actual_type, arg_type,
                               callee.arg_types[i],
                               actual + 1, callee, context)
                
                # There may be some remaining tuple varargs items that haven't
                # been checked yet. Handle them.
                if (callee.arg_kinds[i] == nodes.ARG_STAR and
                        arg_kinds[actual] == nodes.ARG_STAR and
                        isinstance(arg_types[actual], TupleType)):
                    tuplet = (TupleType)arg_types[actual]
                    while tuple_counter[0] < len(tuplet.items):
                        actual_type = get_actual_type(arg_type,
                                                      arg_kinds[actual],
                                                      tuple_counter)
                        self.check_arg(actual_type, arg_type,
                                       callee.arg_types[i],
                                       actual + 1, callee, context)
    
    
    void check_arg(self, Type caller_type, Type original_caller_type,
                   Type callee_type, int n, Callable callee, Context context):
        """Check the type of a single argument in a call."""
        if isinstance(caller_type, Void):
            self.msg.does_not_return_value(caller_type, context)
        elif not is_subtype(caller_type, callee_type):
            self.msg.incompatible_argument(n, callee, original_caller_type,
                                           context)
    
    Type overload_call_target(self, Type[] arg_types, bool is_var_arg,
                             Overloaded overload, Context context):
        """Infer the correct overload item to call with given argument types.

        The return value may be Callable or any (if an unique item
        could not be determined). If is_var_arg is True, the caller
        uses varargs.
        """
        # TODO for overlapping signatures we should try to get a more precise
        #      result than 'any'
        Type match = None # Callable, Any or None
        for typ in overload.items():
            if self.matches_signature(arg_types, is_var_arg, typ):
                if match and (isinstance(match, Any) or
                              not is_same_type(((Callable)match).ret_type,
                                               typ.ret_type)):
                    # Ambiguous return type. Either the function overload is
                    # overlapping (which results in an error elsewhere) or the
                    # caller has provided some dynamic argument types; in
                    # either case can only infer the type to be any, as it is
                    # not an error to use any types in calls.
                    # TODO overlapping overloads should be possible in some
                    #      cases
                    match = Any()
                else:
                    match = typ
        if not match:
            self.msg.no_variant_matches_arguments(overload, context)
            return Any()
        else:
            return match
    
    bool matches_signature(self, Type[] arg_types, bool is_var_arg,
                           Callable callee):
        """Determine whether argument types match the signature.

        If is_var_arg is True, the caller uses varargs.
        """
        if not is_valid_argc(len(arg_types), False, callee):
            return False
        
        if is_var_arg:
            if not self.is_valid_var_arg(arg_types[-1]):
                return False
            arg_types, rest = expand_caller_var_args(arg_types,
                                                     callee.max_fixed_args())

        # Fixed function arguments.
        func_fixed = callee.max_fixed_args()
        for i in range(min(len(arg_types), func_fixed)):
            if not is_subtype(self.erase(arg_types[i]),
                              self.erase(
                                  callee.arg_types[i])):
                return False
        # Function varargs.
        if callee.is_var_arg:
            for i in range(func_fixed, len(arg_types)):
                if not is_subtype(self.erase(arg_types[i]),
                                  self.erase(callee.arg_types[func_fixed])):
                    return False
        return True
    
    Type apply_generic_arguments(self, Callable callable, Type[] types,
                                Context context):
        """Apply generic type arguments to a callable type.

        For example, applying [int] to 'def <T> (T) -> T' results in
        'def [int] (int) -> int'. Here '[int]' is an implicit bound type
        variable.
        
        Note that each type can be None; in this case, it will not be applied.
        """
        tvars = callable.variables.items        
        if len(tvars) != len(types):
            self.msg.incompatible_type_application(len(tvars), len(types),
                                                   context)
            return Any()
        
        # Create a map from type variable id to target type.
        id_to_type = <int, Type> {}
        for i, tv in enumerate(tvars):
            if types[i]:
                id_to_type[tv.id] = types[i]

        # Apply arguments to argument types.
        arg_types = [expand_type(at, id_to_type) for at in callable.arg_types]
        
        bound_vars = [(tv.id, id_to_type[tv.id])
                      for tv in tvars
                      if tv.id in id_to_type]

        # The callable may retain some type vars if only some were applied.
        remaining_tvars = [tv for tv in tvars if tv.id not in id_to_type]
        
        return Callable(arg_types,
                        callable.arg_kinds,
                        callable.arg_names,
                        expand_type(callable.ret_type, id_to_type),
                        callable.is_type_obj(),
                        callable.name,
                        TypeVars(remaining_tvars),
                        callable.bound_vars + bound_vars,
                        callable.line, callable.repr)
    
    Type apply_generic_arguments2(self, Overloaded overload, Type[] types,
                                Context context):
        items = <Callable> []
        for item in overload.items():
            applied = self.apply_generic_arguments(item, types, context)
            if isinstance(applied, Callable):
                items.append((Callable)applied)
            else:
                # There was an error.
                return Any()
        return Overloaded(items)
    
    Type visit_member_expr(self, MemberExpr e):
        """Visit member expression (of form e.id)."""
        return self.analyse_ordinary_member_access(e, False)
    
    Type analyse_ordinary_member_access(self, MemberExpr e, bool is_lvalue):
        """Analyse member expression or member lvalue."""
        if e.kind is not None:
            # This is a reference to a module attribute.
            return self.analyse_ref_expr(e)
        else:
            # This is a reference to a non-module attribute.
            return analyse_member_access(e.name, self.accept(e.expr), e,
                                         is_lvalue, False,
                                         self.chk.tuple_type(), self.msg)
    
    Type analyse_external_member_access(self, str member, Type base_type,
                                       Context context):
        """Analyse member access that is external, i.e. it cannot
        refer to private definitions. Return the result type.
        """
        # TODO remove; no private definitions in mypy
        return analyse_member_access(member, base_type, context, False, False,
                                     self.chk.tuple_type(), self.msg)
    
    Type visit_int_expr(self, IntExpr e):
        """Type check an integer literal (trivial)."""
        return self.named_type('builtins.int')
    
    Type visit_str_expr(self, StrExpr e):
        """Type check a string literal (trivial)."""
        return self.named_type('builtins.str')
    
    Type visit_bytes_expr(self, BytesExpr e):
        """Type check a bytes literal (trivial)."""
        return self.named_type('builtins.bytes')
    
    Type visit_float_expr(self, FloatExpr e):
        """Type check a float literal (trivial)."""
        return self.named_type('builtins.float')
    
    Type visit_op_expr(self, OpExpr e):
        """Type check a binary operator expression."""
        if e.op == 'and' or e.op == 'or':
            return self.check_boolean_op(e, e)
        left_type = self.accept(e.left)
        right_type = self.accept(e.right) # TODO only evaluate if needed
        if e.op == 'in' or e.op == 'not in':
            result, method_type = self.check_op('__contains__', right_type,
                                                e.left, e)
            if e.op == 'in':
                return result
            else:
                return self.chk.bool_type()
        elif e.op in checker.op_methods:
            method = checker.op_methods[e.op]
            result, method_type = self.check_op(method, left_type, e.right, e)
            e.method_type = method_type
            return result
        elif e.op == 'is' or e.op == 'is not':
            return self.chk.bool_type()
        else:
            raise RuntimeError('Unknown operator {}'.format(e.op))
    
    tuple<Type, Type> check_op(self, str method, Type base_type, Node arg,
                               Context context):
        """Type check a binary operation which maps to a method call.

        Return tuple (result type, inferred operatro method type).
        """
        if self.has_non_method(base_type, method):
            self.msg.method_expected_as_operator_implementation(
                base_type, method, context)
        method_type = self.analyse_external_member_access(
            method, base_type, context)
        return (self.check_call(method_type, [arg], [nodes.ARG_POS], context),
                method_type)
    
    Type check_boolean_op(self, OpExpr e, Context context):
        """Type check a boolean operation ('and' or 'or')."""

        # A boolean operation can evaluate to either of the operands.
        
        # We use the current type context to guide the type inference of of
        # the left operand. We also use the left operand type to guide the type
        # inference of the right operand so that expressions such as
        # '[1] or []' are inferred correctly.
        ctx = self.chk.type_context[-1]
        left_type = self.accept(e.left, ctx)
        right_type = self.accept(e.right, left_type)
        
        self.check_not_void(left_type, context)
        self.check_not_void(right_type, context)

        return join.join_types(left_type, right_type,
                               self.chk.basic_types())
    
    Type visit_unary_expr(self, UnaryExpr e):
        """Type check an unary operation ('not', '-' or '~')."""
        operand_type = self.accept(e.expr)
        op = e.op
        if op == 'not':
            self.check_not_void(operand_type, e)
            return self.chk.bool_type()
        elif op == '-':
            method_type = self.analyse_external_member_access('__neg__',
                                                              operand_type, e)
            return self.check_call(method_type, [], [], e)
        elif op == '~':
            method_type = self.analyse_external_member_access('__invert__',
                                                              operand_type, e)
            return self.check_call(method_type, [], [], e)
    
    Type visit_index_expr(self, IndexExpr e):
        """Type check an index expression (base[index])."""
        left_type = self.accept(e.base)
        if isinstance(left_type, TupleType):
            # Special case for tuples. They support indexing only by integer
            # literals.
            index = self.unwrap(e.index)
            if isinstance(index, IntExpr):
                n = ((IntExpr)index).value
                tuple_type = (TupleType)left_type
                if n < len(tuple_type.items):
                    return tuple_type.items[n]
                else:
                    self.chk.fail(messages.TUPLE_INDEX_OUT_OF_RANGE, e)
                    return Any()
            else:
                self.chk.fail(messages.TUPLE_INDEX_MUST_BE_AN_INT_LITERAL, e)
                return Any()
        else:
            result, method_type = self.check_op('__getitem__', left_type,
                                                e.index, e)
            return result
    
    Type visit_cast_expr(self, CastExpr expr):
        """Type check a cast expression."""
        source_type = self.accept(expr.expr)
        target_type = expr.type
        if isinstance(target_type, Any):
            return Any()
        else:
            if not self.is_valid_cast(source_type, target_type):
                self.msg.invalid_cast(target_type, source_type, expr)
            return target_type
    
    bool is_valid_cast(self, Type source_type, Type target_type):
        """Is a cast from source_type to target_type valid (i.e. can succeed at
        runtime)?
        """
        return (is_subtype(target_type, source_type) or
                is_subtype(source_type, target_type) or
                (isinstance(target_type, Instance) and
                     ((Instance)target_type).type.is_interface) or
                (isinstance(source_type, Instance) and
                     ((Instance)source_type).type.is_interface))
    
    Type visit_type_application(self, TypeApplication tapp):
        """Type check a type application (expr<...>)."""
        expr_type = self.accept(tapp.expr)
        if isinstance(expr_type, Callable):
            new_type = self.apply_generic_arguments((Callable)expr_type,
                                                    tapp.types, tapp)
        elif isinstance(expr_type, Overloaded):
            overload = (Overloaded)expr_type
            # Only target items with the right number of generic type args.
            items = [c for c in overload.items()
                     if len(c.variables.items) == len(tapp.types)]
            new_type = self.apply_generic_arguments2(Overloaded(items),
                                                     tapp.types, tapp)
        else:
            self.chk.fail(messages.INVALID_TYPE_APPLICATION_TARGET_TYPE, tapp)
            new_type = Any()
        self.chk.type_map[tapp.expr] = new_type
        return new_type
    
    Type visit_list_expr(self, ListExpr e):
        """Type check a list expression [...] or <t> [...]."""
        Callable constructor
        if e.type:
            # A list expression with an explicit item type; translate into type
            # checking a function call.
            constructor = Callable([e.type],
                                   [nodes.ARG_STAR],
                                   [None],
                                   self.chk.named_generic_type('builtins.list',
                                                               [e.type]),
                                   False,
                                   '<list>')
        else:
            # A list expression without an explicit type; translate into type
            # checking a generic function call.
            tv = TypeVar('T', -1)
            constructor = Callable([tv],
                                   [nodes.ARG_STAR],
                                   [None],
                                   self.chk.named_generic_type('builtins.list',
                                                               [tv]),
                                   False,
                                   '<list>',
                                   TypeVars([TypeVarDef('T', -1)]))
        return self.check_call(constructor,
                               e.items,
                               [nodes.ARG_POS] * len(e.items), e)
    
    Type visit_tuple_expr(self, TupleExpr e):    
        """Type check a tuple expression."""
        if e.types is None:
            TupleType ctx = None
            # Try to determine type context for type inference.
            if isinstance(self.chk.type_context[-1], TupleType):
                t = (TupleType)self.chk.type_context[-1]
                if len(t.items) == len(e.items):
                    ctx = t
            # Infer item types.
            Type[] items = []
            for i in range(len(e.items)):
                item = e.items[i]
                Type tt
                if not ctx:
                    tt = self.accept(item)
                else:
                    tt = self.accept(item, ctx.items[i])
                self.check_not_void(tt, e)
                items.append(tt)
            return TupleType(items)
        else:
            # Explicit item types, i.e. expression of form <t, ...> (e, ...).
            for j in range(len(e.types)):
                item = e.items[j]
                itemtype = self.accept(item)
                self.chk.check_subtype(itemtype, e.types[j], item,
                                       messages.INCOMPATIBLE_TUPLE_ITEM_TYPE)
            return TupleType(e.types)
    
    Type visit_dict_expr(self, DictExpr e):
        if not e.key_type:
            # A dict expression without an explicit type; translate into type
            # checking a generic function call.
            tv1 = TypeVar('KT', -1)
            tv2 = TypeVar('VT', -2)
            Callable constructor
            # The callable type represents a function like this:
            #
            #   dict<kt, vt> make_dict<kt, vt>(tuple<kt, vt> *v): ...
            constructor = Callable([TupleType([tv1, tv2])],
                                   [nodes.ARG_STAR],
                                   [None],
                                   self.chk.named_generic_type('builtins.dict',
                                                               [tv1, tv2]),
                                   False,
                                   '<list>',
                                   TypeVars([TypeVarDef('KT', -1),
                                             TypeVarDef('VT', -2)]))
            # Synthesize function arguments.
            Node[] args = []
            for key, value in e.items:
                args.append(TupleExpr([key, value]))
            return self.check_call(constructor,
                                   args,
                                   [nodes.ARG_POS] * len(args), e)
        else:
            for key_, value_ in e.items:
                kt = self.accept(key_)
                vt = self.accept(value_)
                self.chk.check_subtype(kt, e.key_type, key_,
                                       messages.INCOMPATIBLE_KEY_TYPE)
                self.chk.check_subtype(vt, e.value_type, value_,
                                       messages.INCOMPATIBLE_VALUE_TYPE)
            return self.chk.named_generic_type('builtins.dict', [e.key_type,
                                                                 e.value_type])
    
    Type visit_func_expr(self, FuncExpr e):
        """Type check lambda expression."""
        inferred_type = self.infer_lambda_type(e)
        self.chk.check_func_item(e, type_override=inferred_type)
        ret_type = self.chk.type_map[e.expr()]
        if inferred_type:
            return replace_callable_return_type(inferred_type, ret_type)
        elif e.type:
            return replace_callable_return_type((Callable)e.type, ret_type)
        else:
            # Use default type for lambda.
            # TODO infer return type?
            return function_type(e)

    Callable infer_lambda_type(self, FuncExpr e):
        """Try to infer lambda expression type using context.

        Return None if could not infer type.
        """
        ctx = self.chk.type_context[-1]
        if not ctx or not isinstance(ctx, Callable):
            return None
        
        # The context may have function type variables in it. We replace them
        # since these are the type variables we are ultimately trying to infer;
        # they must be considered as indeterminate. We use ErasedType since it
        # does not affect type inference results (it is for purposes like this
        # only).
        ctx = replace_func_type_vars(ctx, ErasedType())
        
        callable_ctx = (Callable)ctx
        
        if callable_ctx.arg_kinds != e.arg_kinds:
            # Incompatible context; cannot use it to infer types.
            self.chk.fail(messages.CANNOT_INFER_LAMBDA_TYPE, e)
            return None
        
        if not e.type:
            return callable_ctx
        else:
            # The lambda already has a type; only infer the return type.
            return replace_callable_return_type((Callable)e.type,
                                                callable_ctx.ret_type)
    
    Type visit_super_expr(self, SuperExpr e):
        """Type check a super expression (non-lvalue)."""
        t = self.analyse_super(e, False)
        return t
    
    Type analyse_super(self, SuperExpr e, bool is_lvalue):
        """Type check a super expression."""
        if e.info and e.info.base:
            return analyse_member_access(e.name, self_type(e.info), e,
                                         is_lvalue, True,
                                         self.chk.tuple_type(), self.msg,
                                         e.info.base)
        else:
            # Invalid super. This has been reported by the semantic analyser.
            return Any()
    
    Type visit_paren_expr(self, ParenExpr e):
        """Type check a parenthesised expression."""
        return self.accept(e.expr, self.chk.type_context[-1])
    
    Type visit_slice_expr(self, SliceExpr e):
        for index in [e.begin_index, e.end_index, e.stride]:
            if index:
                t = self.accept(index)
                self.chk.check_subtype(t, self.named_type('builtins.int'),
                                       index, messages.INVALID_SLICE_INDEX)
        return self.named_type('builtins.slice')

    Type visit_list_comprehension(self, ListComprehension e):
        return self.check_generator_or_comprehension(
            e.generator, 'builtins.list', '<list-comprehension>')

    Type visit_generator_expr(self, GeneratorExpr e):
        return self.check_generator_or_comprehension(e, 'builtins.Iterator',
                                                     '<generator>')
    
    Type check_generator_or_comprehension(self, GeneratorExpr gen,
                                         str type_name, str id_for_messages):
        """Type check a generator expression or a list comprehension."""
        
        item_type = self.chk.analyse_iterable_item_type(gen.right_expr)
        self.chk.analyse_index_variables(gen.index, False, item_type, gen)

        if gen.condition:
            self.accept(gen.condition)
        
        # Infer the type of the list comprehension by using a synthetic generic
        # callable type.
        tv = TypeVar('T', -1)
        constructor = Callable([tv],
                               [nodes.ARG_POS],
                               [None],
                               self.chk.named_generic_type(type_name, [tv]),
                               False,
                               id_for_messages,
                               TypeVars([TypeVarDef('T', -1)]))
        return self.check_call(constructor,
                               [gen.left_expr], [nodes.ARG_POS], gen)
    
    #
    # Helpers
    #
    
    Type accept(self, Node node, Type context=None):
        """Type check a node. Alias for TypeChecker.accept."""
        return self.chk.accept(node, context)
    
    void check_not_void(self, Type typ, Context context):
        """Generate an error if type is Void."""
        self.chk.check_not_void(typ, context)
    
    bool is_boolean(self, Type typ):
        """Is type compatible with bool?"""
        return is_subtype(typ, self.chk.bool_type())
    
    Instance named_type(self, str name):
        """Return an instance type with type given by the name and no type
        arguments. Alias for TypeChecker.named_type.
        """
        return self.chk.named_type(name)
    
    bool is_valid_var_arg(self, Type typ):
        """Is a type valid as a *args argument?"""
        return (isinstance(typ, TupleType) or self.is_list_instance(typ) or
                    isinstance(typ, Any))
    
    bool is_valid_keyword_var_arg(self, Type typ):    
        """Is a type valid as a **kwargs argument?"""
        return is_subtype(typ, self.chk.named_generic_type(
            'builtins.dict', [self.named_type('builtins.str'), Any()]))
    
    bool is_list_instance(self, Type t):
        """Is the argument an instance type ...[]?"""
        return (isinstance(t, Instance) and
                ((Instance)t).type.full_name() == 'builtins.list')
    
    bool has_non_method(self, Type typ, str member):
        """Does a type have a member variable or an accessor with the given
        name?"""
        if isinstance(typ, Instance):
            itype = (Instance)typ
            return (not itype.type.has_method(member) and
                        itype.type.has_readable_member(member))
        else:
            return False
    
    Node unwrap(self, Node e):
        """Unwrap parentheses from an expression node."""
        if isinstance(e, ParenExpr):
            return self.unwrap(((ParenExpr)e).expr)
        else:
            return e
    
    Node[] unwrap_list(self, Node[] a):
        """Unwrap parentheses from an expression node."""
        Node[] r = []
        for n in a:
            r.append(self.unwrap(n))
        return r

    Type erase(self, Type type):
        """Replace type variable types in type with any."""
        return erasetype.erase_type(type, self.chk.basic_types())


bool is_valid_argc(int nargs, bool is_var_arg, Callable callable):
    """Return a boolean indicating whether a call expression has a
    (potentially) compatible number of arguments for calling a function.
    Varargs at caller are not checked.
    """
    if is_var_arg:
        if callable.is_var_arg:
            return True
        else:
            return nargs - 1 <= callable.max_fixed_args()
    elif callable.is_var_arg:
        return nargs >= callable.min_args
    else:
        # Neither has varargs.
        return nargs <= len(callable.arg_types) and nargs >= callable.min_args


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


int[][] map_actuals_to_formals(int[] caller_kinds,
                               str[] caller_names,
                               int[] callee_kinds,
                               str[] callee_names,
                               func<Type(int)> caller_arg_type):
    """Calculate mapping between actual (caller) args and formals.

    The result contains a list of caller argument indexes mapping to to each
    callee argument index, indexed by callee index.

    The caller_arg_type argument should evaluate to the type of the actual
    argument type with the given index.
    """
    ncallee = len(callee_kinds)
    map = <int[]> [None] * ncallee
    for i in range(ncallee):
        map[i] = []
    j = 0
    for i, kind in enumerate(caller_kinds):
        if kind == nodes.ARG_POS:
            if j < ncallee:
                if callee_kinds[j] in [nodes.ARG_POS, nodes.ARG_OPT,
                                       nodes.ARG_NAMED]:
                    map[j].append(i)
                    j += 1
                elif callee_kinds[j] == nodes.ARG_STAR:
                    map[j].append(i)
        elif kind == nodes.ARG_STAR:
            # We need to to know the actual type to map varargs.
            argt = caller_arg_type(i)
            if isinstance(argt, TupleType):
                # A tuple actual maps to a fixed number of formals.
                tuplet = (TupleType)argt
                for k in range(len(tuplet.items)):
                    if j < ncallee:
                        if callee_kinds[j] != nodes.ARG_STAR2:
                            map[j].append(i)
                        else:
                            raise NotImplementedError()
                        j += 1
            else:
                # Assume that it is an iterable (if it isn't, there will be
                # an error later).
                while j < ncallee:
                    if callee_kinds[j] == nodes.ARG_NAMED:
                        break
                    elif callee_kinds[j] != nodes.ARG_STAR2:
                        map[j].append(i)
                    else:
                        raise NotImplementedError()
                    j += 1
        elif kind == nodes.ARG_NAMED:
            name = caller_names[i]
            if name in callee_names:
                map[callee_names.index(name)].append(i)
            elif nodes.ARG_STAR2 in callee_kinds:
                map[callee_kinds.index(nodes.ARG_STAR2)].append(i)
        else:
            assert kind == nodes.ARG_STAR2
            for j in range(ncallee):
                # TODO tuple varargs complicate this
                no_certain_match = (
                    not map[j] or caller_kinds[map[j][0]] == nodes.ARG_STAR)
                if ((callee_names[j] and no_certain_match)
                        or callee_kinds[j] == nodes.ARG_STAR2):
                    map[j].append(i)
    return map


bool is_empty_tuple(Type t):
    return isinstance(t, TupleType) and not ((TupleType)t).items


bool is_duplicate_mapping(int[] mapping, int[] actual_kinds):
    # Multiple actuals can map to the same formal only if they both come from
    # varargs (*args and **kwargs); in this case at runtime it is possible that
    # there are no duplicates. We need to allow this, as the convention
    # f(..., *args, **kwargs) is common enough.
    return len(mapping) > 1 and not (
        len(mapping) == 2 and
        actual_kinds[mapping[0]] == nodes.ARG_STAR and
        actual_kinds[mapping[1]] == nodes.ARG_STAR2)


Callable replace_callable_return_type(Callable c, Type new_ret_type):
    """Return a copy of a callable type with a different return type."""
    return Callable(c.arg_types,
                    c.arg_kinds,
                    c.arg_names,
                    new_ret_type,
                    c.is_type_obj(),
                    c.name,
                    c.variables,
                    c.bound_vars,
                    c.line)


class ArgInferSecondPassQuery(mtypes.TypeQuery):
    """Query whether an argument type should be inferred in the second pass.

    The result is True if the type has a type variable in a callable return
    type anywhere. For example, the result for func<t()> is True if t is a
    type variable.
    """    
    void __init__(self):
        super().__init__(False, mtypes.ANY_TYPE_STRATEGY)

    bool visit_callable(self, Callable t):
        return self.query_types(t.arg_types) or t.accept(HasTypeVarQuery())


class HasTypeVarQuery(mtypes.TypeQuery):
    """Visitor for querying whether a type has a type variable component."""
    void __init__(self):
        super().__init__(False, mtypes.ANY_TYPE_STRATEGY)

    bool visit_type_var(self, TypeVar t):
        return True


bool has_erased_component(Type t):
    return t is not None and t.accept(HasErasedComponentsQuery())


class HasErasedComponentsQuery(mtypes.TypeQuery):
    """Visitor for querying whether a type has an erased component."""
    void __init__(self):
        super().__init__(False, mtypes.ANY_TYPE_STRATEGY)

    bool visit_erased_type(self, ErasedType t):
        return True


Type type_object_type(TypeInfo info, func<Type()> type_type):
    """Return the type of a type object.

    For a generic type G with type variables T and S the type is of form

      def <T, S>(...) as G<T, S>,

    where ... are argument types for the __init__ method.
    """
    if info.is_interface:
        return type_type()
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
