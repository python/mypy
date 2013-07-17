"""Transform program to include explicit coercions and wrappers.

The transform performs these main changes:

 - add explicit coercions to/from any (or more generally, between different
   levels of typing precision)
 - add wrapper methods and functions for calling statically typed functions
   in dynamically typed code
 - add wrapper methods for overrides with a different signature
 - add generic wrapper classes for coercions between generic types (e.g.
   from List[Any] to List[str])
"""

from typing import Undefined, Dict, List, Tuple, cast

from mypy.nodes import (
    Node, MypyFile, TypeInfo, TypeDef, VarDef, FuncDef, Var,
    ReturnStmt, AssignmentStmt, IfStmt, WhileStmt, MemberExpr, NameExpr, MDEF,
    CallExpr, SuperExpr, TypeExpr, CastExpr, OpExpr, CoerceExpr, GDEF,
    SymbolTableNode, IndexExpr, function_type
)
from mypy.traverser import TraverserVisitor
from mypy.types import Type, AnyType, Callable, TypeVarDef, Instance
from mypy.lex import Token
from mypy.transformtype import TypeTransformer
from mypy.transutil import (
    prepend_arg_type, is_simple_override, tvar_arg_name, dynamic_suffix,
    add_arg_type_after_self
)
from mypy.coerce import coerce
from mypy.rttypevars import translate_runtime_type_vars_in_context


class DyncheckTransformVisitor(TraverserVisitor):
    """Translate a parse tree to use runtime representation of generics.

    Translate generic type variables to ordinary variables and all make
    all non-trivial coercions explicit. Also generate generic wrapper classes
    for coercions between generic types and wrapper methods for overrides
    and for more efficient access from dynamically typed code.
    
    This visitor modifies the parse tree in-place.
    """

    type_map = Undefined(Dict[Node, Type])
    modules = Undefined(Dict[str, MypyFile])
    is_pretty = False
    type_tf = Undefined(TypeTransformer)
    
    # Stack of function return types
    return_types = Undefined(List[Type])
    # Stack of dynamically typed function flags
    dynamic_funcs = Undefined(List[bool])
    
    # Associate a Node with its start end line numbers.
    line_map = Undefined(Dict[Node, Tuple[int, int]])
    
    is_java = False
    
    # The current type context (or None if not within a type).
    _type_context = None # type: TypeInfo
    
    def type_context(self) -> TypeInfo:
        return self._type_context
    
    def __init__(self, type_map: Dict[Node, Type],
                 modules: Dict[str, MypyFile], is_pretty: bool,
                 is_java: bool = False) -> None:
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
    
    def visit_mypy_file(self, o: MypyFile) -> None:
        """Transform an file."""
        res = [] # type: List[Node]
        for d in o.defs:
            if isinstance(d, TypeDef):
                self._type_context = d.info
                res.extend(self.type_tf.transform_type_def(d))
                self._type_context = None
            else:
                d.accept(self)
                res.append(d)
        o.defs = res
    
    def visit_var_def(self, o: VarDef) -> None:
        """Transform a variable definition in-place.

        This is not suitable for member variable definitions; they are
        transformed in TypeTransformer.
        """
        super().visit_var_def(o)
        
        if o.init is not None:
            if o.items[0].type:
                t = o.items[0].type
            else:
                t = AnyType()
            o.init = self.coerce(o.init, t, self.get_type(o.init),
                                 self.type_context())
    
    def visit_func_def(self, fdef: FuncDef) -> None:
        """Transform a global function definition in-place.

        This is not suitable for methods; they are transformed in
        FuncTransformer.
        """
        self.prepend_generic_function_tvar_args(fdef)
        self.transform_function_body(fdef)
    
    def transform_function_body(self, fdef: FuncDef) -> None:
        """Transform the body of a function."""
        self.dynamic_funcs.append(fdef.is_implicit)
        # FIX overloads
        self.return_types.append(cast(Callable, function_type(fdef)).ret_type)
        super().visit_func_def(fdef)
        self.return_types.pop()
        self.dynamic_funcs.pop()
    
    def prepend_generic_function_tvar_args(self, fdef: FuncDef) -> None:
        """Add implicit function type variable arguments if fdef is generic."""
        sig = cast(Callable, function_type(fdef))
        tvars = sig.variables
        if not fdef.type:
            fdef.type = sig
        
        tv = [] # type: List[Var]
        ntvars = len(tvars)
        if fdef.is_method():
            # For methods, add type variable arguments after the self arg.
            for n in range(ntvars):
                tv.append(Var(tvar_arg_name(-1 - n)))
                fdef.type = add_arg_type_after_self(cast(Callable, fdef.type),
                                                    AnyType())
            fdef.args = [fdef.args[0]] + tv + fdef.args[1:]
        else:
            # For ordinary functions, prepend type variable arguments.
            for n in range(ntvars):
                tv.append(Var(tvar_arg_name(-1 - n)))
                fdef.type = prepend_arg_type(cast(Callable, fdef.type),
                                             AnyType())
            fdef.args = tv + fdef.args
        fdef.init = List[AssignmentStmt]([None]) * ntvars + fdef.init
    
    #
    # Transform statements
    #    
    
    def transform_block(self, block: List[Node]) -> None:
        for stmt in block:
            stmt.accept(self)
    
    def visit_return_stmt(self, s: ReturnStmt) -> None:
        super().visit_return_stmt(s)
        s.expr = self.coerce(s.expr, self.return_types[-1],
                             self.get_type(s.expr), self.type_context())
    
    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        super().visit_assignment_stmt(s)
        if isinstance(s.lvalues[0], IndexExpr):
            index = cast(IndexExpr, s.lvalues[0])
            method_type = index.method_type
            if self.dynamic_funcs[-1] or isinstance(method_type, AnyType):
                lvalue_type = AnyType() # type: Type
            else:
                method_callable = cast(Callable, method_type)
                # TODO arg_types[1] may not be reliable
                lvalue_type = method_callable.arg_types[1]
        else:
            lvalue_type = self.get_type(s.lvalues[0])
            
        s.rvalue = self.coerce2(s.rvalue, lvalue_type, self.get_type(s.rvalue),
                                self.type_context())
    
    #
    # Transform expressions
    #
    
    def visit_member_expr(self, e: MemberExpr) -> None:
        super().visit_member_expr(e)
        
        typ = self.get_type(e.expr)
        
        if self.dynamic_funcs[-1]:
            e.expr = self.coerce_to_dynamic(e.expr, typ, self.type_context())
            typ = AnyType()
        
        if isinstance(typ, Instance):
            # Reference to a statically-typed method variant with the suffix
            # derived from the base object type.
            suffix = self.get_member_reference_suffix(e.name, typ.type)
        else:
            # Reference to a dynamically-typed method variant.
            suffix = self.dynamic_suffix()
        e.name += suffix
    
    def visit_name_expr(self, e: NameExpr) -> None:
        super().visit_name_expr(e)
        if e.kind == MDEF and isinstance(e.node, FuncDef):
            # Translate reference to a method.
            suffix = self.get_member_reference_suffix(e.name, e.info)
            e.name += suffix
            # Update representation to have the correct name.
            prefix = e.repr.components[0].pre
    
    def get_member_reference_suffix(self, name: str, info: TypeInfo) -> str:
        if info.has_method(name):
            fdef = cast(FuncDef, info.get_method(name))
            return self.type_suffix(fdef)
        else:
            return ''
    
    def visit_call_expr(self, e: CallExpr) -> None:
        if e.analyzed:
            # This is not an ordinary call.
            e.analyzed.accept(self)
            return
        
        super().visit_call_expr(e)
        
        # Do no coercions if this is a call to debugging facilities.
        if self.is_debugging_call_expr(e):
            return

        # Get the type of the callable (type variables in the context of the
        # enclosing class).
        ctype = self.get_type(e.callee)

        # Add coercions for the arguments.
        for i in range(len(e.args)):
            arg_type = AnyType() # type: Type
            if isinstance(ctype, Callable):
                arg_type = ctype.arg_types[i]
            e.args[i] = self.coerce2(e.args[i], arg_type,
                                     self.get_type(e.args[i]),
                                     self.type_context())
        
        # Prepend type argument values to the call as needed.
        if isinstance(ctype, Callable) and cast(Callable,
                                                ctype).bound_vars != []:
            bound_vars = (cast(Callable, ctype)).bound_vars

            # If this is a constructor call (target is the constructor
            # of a generic type or superclass __init__), include also
            # instance type variables.  Otherwise filter them away --
            # include only generic function type variables.
            if (not (cast(Callable, ctype)).is_type_obj() and
                    not (isinstance(e.callee, SuperExpr) and
                         (cast(SuperExpr, e.callee)).name == '__init__')):
                # Filter instance type variables; only include function tvars.
                bound_vars = [(id, t) for id, t in bound_vars if id < 0]
            
            args = [] # type: List[Node]
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
    
    def visit_cast_expr(self, e: CastExpr) -> None:
        super().visit_cast_expr(e)
        if isinstance(self.get_type(e), AnyType):
            e.expr = self.coerce(e.expr, AnyType(), self.get_type(e.expr),
                                 self.type_context())
    
    def visit_op_expr(self, e: OpExpr) -> None:
        super().visit_op_expr(e)
        if e.op in ['and', 'or']:
            target = self.get_type(e)
            e.left = self.coerce(e.left, target,
                                 self.get_type(e.left), self.type_context())
            e.right = self.coerce(e.right, target,
                                  self.get_type(e.right), self.type_context())
        else:
            method_type = e.method_type
            if self.dynamic_funcs[-1] or isinstance(method_type, AnyType):
                e.left = self.coerce_to_dynamic(e.left, self.get_type(e.left),
                                                self.type_context())
                e.right = self.coerce(e.right, AnyType(),
                                      self.get_type(e.right),
                                      self.type_context())
            elif method_type:
                method_callable = cast(Callable, method_type)
                operand = e.right
                # For 'in', the order of operands is reversed.
                if e.op == 'in':
                    operand = e.left
                # TODO arg_types[0] may not be reliable
                operand = self.coerce(operand, method_callable.arg_types[0],
                                      self.get_type(operand),
                                      self.type_context())
                if e.op == 'in':
                    e.left = operand
                else:
                    e.right = operand

    def visit_index_expr(self, e: IndexExpr) -> None:
        if e.analyzed:
            # Actually a type application, not indexing.
            e.analyzed.accept(self)
            return
        super().visit_index_expr(e)
        method_type = e.method_type
        if self.dynamic_funcs[-1] or isinstance(method_type, AnyType):
            e.base = self.coerce_to_dynamic(e.base, self.get_type(e.base),
                                            self.type_context())
            e.index = self.coerce_to_dynamic(e.index, self.get_type(e.index),
                                             self.type_context())
        else:
            method_callable = cast(Callable, method_type)
            e.index = self.coerce(e.index, method_callable.arg_types[0],
                                  self.get_type(e.index), self.type_context())
    
    #
    # Helpers
    #    
    
    def get_type(self, node: Node) -> Type:
        """Return the type of a node as reported by the type checker."""
        return self.type_map[node]
    
    def set_type(self, node: Node, typ: Type) -> None:
        self.type_map[node] = typ
    
    def type_suffix(self, fdef: FuncDef, info: TypeInfo = None) -> str:
        """Return the suffix for a mangled name.

        This includes an optional type suffix for a function or method.
        """
        if not info:
            info = fdef.info
        # If info is None, we have a global function => no suffix. Also if the
        # method is not an override, we need no suffix.
        if not info or (not info.bases or
                        not info.bases[0].type.has_method(fdef.name())):
            return ''
        elif is_simple_override(fdef, info):
            return self.type_suffix(fdef, info.bases[0].type)
        elif self.is_pretty:
            return '`' + info.name()
        else:
            return '__' + info.name()
    
    def dynamic_suffix(self) -> str:
        """Return the suffix of the dynamic wrapper of a method or class."""
        return dynamic_suffix(self.is_pretty)
    
    def wrapper_class_suffix(self) -> str:
        """Return the suffix of a generic wrapper class."""
        return '**'
    
    def coerce(self, expr: Node, target_type: Type, source_type: Type,
               context: TypeInfo, is_wrapper_class: bool = False) -> Node:
        return coerce(expr, target_type, source_type, context,
                      is_wrapper_class, self.is_java)
    
    def coerce2(self, expr: Node, target_type: Type, source_type: Type,
                context: TypeInfo, is_wrapper_class: bool = False) -> Node:
        """Create coercion from source_type to target_type.

        Also include middle coercion do 'Any' if transforming a dynamically
        typed function.
        """
        if self.dynamic_funcs[-1]:
            return self.coerce(self.coerce(expr, AnyType(), source_type,
                                           context, is_wrapper_class),
                               target_type, AnyType(), context,
                               is_wrapper_class)
        else:
            return self.coerce(expr, target_type, source_type, context,
                               is_wrapper_class)
    
    def coerce_to_dynamic(self, expr: Node, source_type: Type,
                          context: TypeInfo) -> Node:
        if isinstance(source_type, AnyType):
            return expr
        source_type = translate_runtime_type_vars_in_context(
            source_type, context, self.is_java)
        return CoerceExpr(expr, AnyType(), source_type, False)
    
    def add_line_mapping(self, orig_node: Node, new_node: Node) -> None:
        """Add a line mapping for a wrapper.

        The node new_node has logically the same line numbers as
        orig_node. The nodes should be FuncDef/TypeDef nodes.
        """
        if orig_node.repr:
            start_line = orig_node.line
            end_line = start_line # TODO use real end line
            self.line_map[new_node] = (start_line, end_line)
    
    def named_type(self, name: str) -> Instance:
        # TODO combine with checker
        # Assume that the name refers to a type.
        sym = self.lookup(name, GDEF)
        return Instance(cast(TypeInfo, sym.node), [])
    
    def lookup(self, fullname: str, kind: int) -> SymbolTableNode:
        # TODO combine with checker
        # TODO remove kind argument
        parts = fullname.split('.')
        n = self.modules[parts[0]]
        for i in range(1, len(parts) - 1):
            n = cast(MypyFile, ((n.names.get(parts[i], None).node)))
        return n.names[parts[-1]]
    
    def object_member_name(self) -> str:
        if self.is_java:
            return '__o_{}'.format(self.type_context().name())
        else:
            return '__o'
