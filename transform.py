"""Transform program to include explicit coercions and wrappers.

The transform performs these main changes:

 - add explicit coercions to/from any (or more generally, between different
   levels of typing precision)
 - add wrapper methods and functions for calling statically typed functions
   in dynamically typed code
 - add wrapper methods for overrides with a different signature
 - add generic wrapper classes for coercions between generic types (e.g.
   from any[] to str[])
"""

from nodes import (
    Node, MypyFile, TypeInfo, TypeDef, VarDef, FuncDef, Annotation, Var,
    ReturnStmt, AssignmentStmt, IfStmt, WhileStmt, MemberExpr, NameExpr, MDEF,
    CallExpr, SuperExpr, TypeExpr, CastExpr, OpExpr, CoerceExpr, GDEF,
    SymbolTableNode
)
from traverser import TraverserVisitor
from mtypes import Type, Any, Callable, TypeVarDef, Instance
from checker import function_type
from lex import Token
from transformtype import TypeTransformer
from transutil import (
    prepend_arg_type, is_simple_override, tvar_arg_name, dynamic_suffix,
    add_arg_type_after_self
)
from coerce import coerce
from rttypevars import translate_runtime_type_vars_in_context


class DyncheckTransformVisitor(TraverserVisitor):
    """Translate a parse tree to use runtime representation of generics.

    Translate generic type variables to ordinary variables and all make
    all non-trivial coercions explicit. Also generate generic wrapper classes
    for coercions between generic types and wrapper methods for overrides
    and for more efficient access from dynamically typed code.
    
    This visitor modifies the parse tree in-place.
    """

    dict<Node, Type> type_map
    dict<str, MypyFile> modules
    bool is_pretty
    TypeTransformer type_tf
    
    # Stack of function return types
    Type[] return_types
    # Stack of dynamically typed function flags
    bool[] dynamic_funcs
    
    # Associate a Node with its start end line numbers.
    dict<Node, tuple<int, int>> line_map
    
    bool is_java
    
    # The current type context (or None if not within a type).
    TypeInfo _type_context = None
    
    TypeInfo type_context(self):
        return self._type_context
    
    void __init__(self, dict<Node, Type> type_map, dict<str, MypyFile> modules,
                  bool is_pretty, bool is_java=False):
        self.type_tf = TypeTransformer(self)
        self.return_types = []
        self.dynamic_funcs = [False]
        self.line_map = {}
        self.type_map = type_map
        self.modules = modules
        self.is_pretty = is_pretty
        self.is_java = is_java
    
    #
    # Transform definitions
    #
    
    void visit_mypy_file(self, MypyFile o):
        """Transform an file."""
        res = <Node> []
        for d in o.defs:
            if isinstance(d, TypeDef):
                self._type_context = ((TypeDef)d).info
                res.extend(self.type_tf.transform_type_def((TypeDef)d))
                self._type_context = None
            else:
                d.accept(self)
                res.append(d)
        o.defs = res
    
    void visit_var_def(self, VarDef o):
        """Transform a variable definition in-place.

        This is not suitable for member variable definitions; they are
        transformed in TypeTransformer.
        """
        super().visit_var_def(o)
        
        if o.init is not None:
            if o.items[0][0].type:
                t = o.items[0][0].type.type
            else:
                t = Any()
            o.init = self.coerce(o.init, t, self.get_type(o.init),
                                 self.type_context())
    
    void visit_func_def(self, FuncDef fdef):
        """Transform a global function definition in-place.

        This is not suitable for methods; they are transformed in
        FuncTransformer.
        """
        self.prepend_generic_function_tvar_args(fdef)
        self.transform_function_body(fdef)
    
    void transform_function_body(self, FuncDef fdef):
        """Transform the body of a function."""
        self.dynamic_funcs.append(fdef.is_implicit)
        # FIX overloads
        self.return_types.append(((Callable)function_type(fdef)).ret_type)
        super().visit_func_def(fdef)
        self.return_types.pop()
        self.dynamic_funcs.pop()
    
    void prepend_generic_function_tvar_args(self, FuncDef fdef):
        """Add implicit function type variable arguments if fdef is generic."""
        sig = (Callable)function_type(fdef)
        TypeVarDef[] tvars = sig.variables.items
        if not fdef.type:
            fdef.type = Annotation(sig)
        typ = fdef.type
        
        tv = <Var> []
        ntvars = len(tvars)
        if fdef.is_method():
            # For methods, add type variable arguments after the self arg.
            for n in range(ntvars):
                tv.append(Var(tvar_arg_name(-1 - n)))
                typ.type = add_arg_type_after_self((Callable)typ.type, Any())
            fdef.args = [fdef.args[0]] + tv + fdef.args[1:]
        else:
            # For ordinary functions, prepend type variable arguments.
            for n in range(ntvars):
                tv.append(Var(tvar_arg_name(-1 - n)))
                typ.type = prepend_arg_type((Callable)typ.type, Any())
            fdef.args = tv + fdef.args
        fdef.init = <AssignmentStmt> [None] * ntvars + fdef.init
    
    #
    # Transform statements
    #    
    
    void transform_block(self, Node[] block):
        for stmt in block:
            stmt.accept(self)
    
    void visit_return_stmt(self, ReturnStmt s):
        super().visit_return_stmt(s)
        s.expr = self.coerce(s.expr, self.return_types[-1],
                             self.get_type(s.expr), self.type_context())
    
    void visit_assignment_stmt(self, AssignmentStmt s):
        super().visit_assignment_stmt(s)
        s.rvalue = self.coerce2(s.rvalue, self.get_type(s.lvalues[0]),
                                self.get_type(s.rvalue), self.type_context())
    
    #
    # Transform expressions
    #
    
    void visit_member_expr(self, MemberExpr e):
        super().visit_member_expr(e)
        
        typ = self.get_type(e.expr)
        
        if self.dynamic_funcs[-1]:
            e.expr = self.coerce_to_dynamic(e.expr, typ, self.type_context())
            typ = Any()
        
        if isinstance(typ, Instance):
            # Reference to a statically-typed method variant with the suffix
            # derived from the base object type.
            suffix = self.get_member_reference_suffix(e.name,
                                                      ((Instance)typ).type)
        else:
            # Reference to a dynamically-typed method variant.
            suffix = self.dynamic_suffix()
        e.name += suffix
    
    void visit_name_expr(self, NameExpr e):
        super().visit_name_expr(e)
        if e.kind == MDEF and isinstance(e.node, FuncDef):
            # Translate reference to a method.
            suffix = self.get_member_reference_suffix(e.name, e.info)
            e.name += suffix
            # Update representation to have the correct name.
            prefix = e.repr.components[0].pre
    
    str get_member_reference_suffix(self, str name, TypeInfo info):
        if info.has_method(name):
            fdef = (FuncDef)info.get_method(name)
            return self.type_suffix(fdef)
        else:
            return ''
    
    void visit_call_expr(self, CallExpr e):
        super().visit_call_expr(e)
        
        # Do no coercions if this is a call to debugging facilities.
        if self.is_debugging_call_expr(e):
            return 
        
        # Get the type of the callable (type variables in the context of the
        # enclosing class).
        ctype = self.get_type(e.callee)

        # Add coercions for the arguments.
        for i in range(len(e.args)):
            Type arg_type = Any()
            if isinstance(ctype, Callable):
                arg_type = ((Callable)ctype).arg_types[i]
            e.args[i] = self.coerce2(e.args[i], arg_type,
                                     self.get_type(e.args[i]),
                                     self.type_context())
        
        # Prepend type argument values to the call as needed.
        if isinstance(ctype, Callable) and ((Callable)ctype).bound_vars != []:
            bound_vars = ((Callable)ctype).bound_vars

            # If this is a constructor call (target is the constructor
            # of a generic type or superclass __init__), include also
            # instance type variables.  Otherwise filter them away --
            # include only generic function type variables.
            if (not ((Callable)ctype).is_type_obj() and
                    not (isinstance(e.callee, SuperExpr) and
                         ((SuperExpr)e.callee).name == '__init__')):
                # Filter instance type variables; only include function tvars.
                bound_vars = [(id, t) for id, t in bound_vars if id < 0]
            
            args = <Node> []
            for i in range(len(bound_vars)):
                # Compile type variables to runtime type variable expressions.
                tv = translate_runtime_type_vars_in_context(
                    bound_vars[i][1],
                    self.type_context(),
                    self.is_java)
                args.append(TypeExpr(tv))
            e.args = args + e.args
    
    def is_debugging_call_expr(self, e):
        return isinstance(e.callee, NameExpr) and e.callee.name in ['__print']
    
    void visit_cast_expr(self, CastExpr e):
        super().visit_cast_expr(e)
        if isinstance(self.get_type(e), Any):
            e.expr = self.coerce(e.expr, Any(), self.get_type(e.expr),
                                 self.type_context())
    
    void visit_op_expr(self, OpExpr e):
        super().visit_op_expr(e)
        if e.op in ['and', 'or']:
            target = self.get_type(e)
            e.left = self.coerce(e.left, target,
                                 self.get_type(e.left), self.type_context())
            e.right = self.coerce(e.right, target,
                                  self.get_type(e.right), self.type_context())
        else:
            if self.dynamic_funcs[-1]:
                e.left = self.coerce_to_dynamic(e.left, self.get_type(e.left),
                                                self.type_context())
                e.right = self.coerce(e.right, Any(), self.get_type(e.right),
                                      self.type_context())
            elif e.op == '+':
                e.left = self.coerce(e.left, self.named_type('builtins.int'),
                                     self.get_type(e.left),
                                     self.type_context())
                e.right = self.coerce(e.right, self.named_type('builtins.int'),
                                      self.get_type(e.right),
                                      self.type_context())
    
    #
    # Helpers
    #    
    
    Type get_type(self, Node node):
        """Return the type of a node as reported by the type checker."""
        return self.type_map[node]
    
    void set_type(self, Node node, Type typ):
        self.type_map[node] = typ
    
    str type_suffix(self, FuncDef fdef, TypeInfo info=None):
        """Return the suffix for a mangled name.

        This includes an optional type suffix for a function or method.
        """
        if not info:
            info = fdef.info
        # If info is None, we have a global function => no suffix. Also if the
        # method is not an override, we need no suffix.
        if not info or not info.base or not info.base.has_method(fdef.name()):
            return ''
        elif is_simple_override(fdef, info):
            return self.type_suffix(fdef, info.base)
        elif self.is_pretty:
            return '`' + info.name()
        else:
            return '__' + info.name()
    
    str dynamic_suffix(self):
        """Return the suffix of the dynamic wrapper of a method or class."""
        return dynamic_suffix(self.is_pretty)
    
    str wrapper_class_suffix(self):
        """Return the suffix of a generic wrapper class."""
        return '**'
    
    Node coerce(self, Node expr, Type target_type, Type source_type,
                TypeInfo context, bool is_wrapper_class=False):
        return coerce(expr, target_type, source_type, context,
                      is_wrapper_class, self.is_java)
    
    Node coerce2(self, Node expr, Type target_type, Type source_type,
                 TypeInfo context, bool is_wrapper_class=False):
        """Create coercion from source_type to target_type.

        Also include middle coercion do 'any' if transforming a dynamically
        typed function.
        """
        if self.dynamic_funcs[-1]:
            return self.coerce(self.coerce(expr, Any(), source_type, context,
                                           is_wrapper_class),
                               target_type, Any(), context, is_wrapper_class)
        else:
            return self.coerce(expr, target_type, source_type, context,
                               is_wrapper_class)
    
    Node coerce_to_dynamic(self, Node expr, Type source_type, TypeInfo context):
        if isinstance(source_type, Any):
            return expr
        source_type = translate_runtime_type_vars_in_context(
            source_type, context, self.is_java)
        return CoerceExpr(expr, Any(), source_type, False)
    
    void add_line_mapping(self, Node orig_node, Node new_node):
        """Add a line mapping for a wrapper.

        The node new_node has logically the same line numbers as
        orig_node. The nodes should be FuncDef/TypeDef nodes.
        """
        if orig_node.repr:
            start_line = orig_node.line
            end_line = start_line # TODO use real end line
            self.line_map[new_node] = (start_line, end_line)
    
    Instance named_type(self, str name):
        # TODO combine with checker
        # Assume that the name refers to a type.
        sym = self.lookup(name, GDEF)
        return Instance((TypeInfo)sym.node, [])
    
    SymbolTableNode lookup(self, str full_name, int kind):
        # TODO combine with checker
        # TODO remove kind argument
        parts = full_name.split('.')
        n = self.modules[parts[0]]
        for i in range(1, len(parts) - 1):
            n = (MypyFile)((n.names.get(parts[i], None).node))
        return n.names[parts[-1]]
    
    str object_member_name(self):
        if self.is_java:
            return '__o_{}'.format(self.type_context().name())
        else:
            return '__o'
