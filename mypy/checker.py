"""Mypy type checker."""

from typing import Undefined, Dict, List, cast, overload

from mypy.errors import Errors
from mypy.nodes import (
    SymbolTable, Node, MypyFile, VarDef, LDEF, Var,
    OverloadedFuncDef, FuncDef, FuncItem, FuncBase, TypeInfo,
    TypeDef, GDEF, Block, AssignmentStmt, NameExpr, MemberExpr, IndexExpr,
    TupleExpr, ListExpr, ParenExpr, ExpressionStmt, ReturnStmt, IfStmt,
    WhileStmt, OperatorAssignmentStmt, YieldStmt, WithStmt, AssertStmt,
    RaiseStmt, TryStmt, ForStmt, DelStmt, CallExpr, IntExpr, StrExpr,
    BytesExpr, UnicodeExpr, FloatExpr, OpExpr, UnaryExpr, CastExpr, SuperExpr,
    TypeApplication, DictExpr, SliceExpr, FuncExpr, TempNode, SymbolTableNode,
    Context, ListComprehension, ConditionalExpr, GeneratorExpr,
    Decorator, SetExpr, PassStmt, TypeVarExpr, UndefinedExpr, PrintStmt
)
from mypy.nodes import function_type, method_type
from mypy import nodes
from mypy.types import (
    Type, AnyType, Callable, Void, FunctionLike, Overloaded, TupleType,
    Instance, NoneTyp, UnboundType, ErrorType, TypeTranslator, BasicTypes,
    strip_type
)
from mypy.sametypes import is_same_type
from mypy.messages import MessageBuilder
import mypy.checkexpr
from mypy import messages
from mypy.subtypes import is_subtype, is_equivalent, map_instance_to_supertype
from mypy.semanal import self_type, set_callable_name, refers_to_fullname
from mypy.expandtype import expand_type_by_instance
from mypy.visitor import NodeVisitor
from mypy.join import join_types


class TypeChecker(NodeVisitor[Type]):
    """Mypy type checker.

    Type check mypy source files that have been semantically analysed.
    """

    pyversion = 3                      # Target Python major version
    errors = Undefined(Errors)         # Error message reporting
    symtable = Undefined(SymbolTable)  # SymbolNode table for the whole program
    msg = Undefined(MessageBuilder)    # Utility for generating messages
    type_map = Undefined(Dict[Node, Type])  # Types of type checked nodes
    expr_checker = Undefined('mypy.checkexpr.ExpressionChecker')
    
    stack = Undefined(List[str]) # Stack of local variable definitions
                                 # None separates nested functions
    return_types = Undefined(List[Type])  # Stack of function return types
    type_context = Undefined(List[Type])  # Type context for type inference
    dynamic_funcs = Undefined(List[bool]) # Flags; true for dynamically typed
                                          # functions
    
    globals = Undefined(SymbolTable)
    class_tvars = Undefined(SymbolTable)
    locals = Undefined(SymbolTable)
    modules = Undefined(Dict[str, MypyFile])
    
    def __init__(self, errors: Errors, modules: Dict[str, MypyFile],
                 pyversion: int = 3) -> None:
        """Construct a type checker.

        Use errors to report type check errors. Assume symtable has been
        populated by the semantic analyzer.
        """
        self.expr_checker
        self.errors = errors
        self.modules = modules
        self.pyversion = pyversion
        self.msg = MessageBuilder(errors)
        self.type_map = {}
        self.expr_checker = mypy.checkexpr.ExpressionChecker(self, self.msg)
        self.stack = [None]
        self.return_types = []
        self.type_context = []
        self.dynamic_funcs = []
    
    def visit_file(self, file_node: MypyFile, path: str) -> None:  
        """Type check a mypy file with the given path."""
        self.errors.set_file(path)
        self.globals = file_node.names
        self.locals = None
        self.class_tvars = None
        
        for d in file_node.defs:
            self.accept(d)
    
    def accept(self, node: Node, type_context: Type = None) -> Type:
        """Type check a node in the given type context."""
        self.type_context.append(type_context)
        typ = node.accept(self)
        self.type_context.pop()
        self.store_type(node, typ)
        if self.is_dynamic_function():
            return AnyType()
        else:
            return typ
    
    #
    # Definitions
    #
    
    def visit_var_def(self, defn: VarDef) -> Type:
        """Type check a variable definition.

        It can be of any kind: local, member or global.
        """
        # Type check initializer.
        if defn.init:
            # There is an initializer.
            if defn.items[0].type:
                # Explicit types.
                if len(defn.items) == 1:
                    self.check_single_assignment(defn.items[0].type, None,
                                                 defn.init, defn.init)
                else:
                    # Multiple assignment.
                    lvt = List[Type]()
                    for v in defn.items:
                        lvt.append(v.type)
                    self.check_multi_assignment(
                        lvt, [None] * len(lvt),
                        defn.init, defn.init)
            else:
                init_type = self.accept(defn.init)
                if defn.kind == LDEF and not defn.is_top_level:
                    # Infer local variable type if there is an initializer
                    # except if the# definition is at the top level (outside a
                    # function).
                    self.infer_local_variable_type(defn.items, init_type, defn)
        else:
            # No initializer
            if (defn.kind == LDEF and not defn.items[0].type and
                    not defn.is_top_level and not self.is_dynamic_function()):
                self.fail(messages.NEED_ANNOTATION_FOR_VAR, defn)
    
    def infer_local_variable_type(self, x, y, z):
        # TODO
        raise RuntimeError('Not implemented')
    
    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> Type:
        num_abstract = 0
        for fdef in defn.items:
            self.check_func_item(fdef.func)
            if fdef.func.is_abstract:
                num_abstract += 1
        if num_abstract not in (0, len(defn.items)):
            self.fail(messages.INCONSISTENT_ABSTRACT_OVERLOAD, defn)
        if defn.info:
            self.check_method_override(defn)
    
    def visit_func_def(self, defn: FuncDef) -> Type:
        """Type check a function definition."""
        self.check_func_item(defn)
        if defn.info:
            self.check_method_override(defn)
        if defn.original_def:
            if not is_same_type(function_type(defn),
                                function_type(defn.original_def)):
                self.msg.incompatible_conditional_function_def(defn)
    
    def check_func_item(self, defn: FuncItem,
                        type_override: Callable = None) -> Type:
        # We may be checking a function definition or an anonymous function. In
        # the first case, set up another reference with the precise type.
        fdef = None # type: FuncDef
        if isinstance(defn, FuncDef):
            fdef = cast(FuncDef, defn)
        
        self.dynamic_funcs.append(defn.type is None and not type_override)
        
        if fdef:
            self.errors.push_function(fdef.name())
        
        typ = function_type(defn)
        if type_override:
            typ = type_override
        if isinstance(typ, Callable):
            self.check_func_def(defn, typ)
        else:
            raise RuntimeError('Not supported')
        
        if fdef:
            self.errors.pop_function()
        
        self.dynamic_funcs.pop()
    
    def check_func_def(self, defn: FuncItem, typ: Type) -> None:
        """Check a function definition."""
        # We may be checking a function definition or an anonymous function. In
        # the first case, set up another reference with the precise type.
        if isinstance(defn, FuncDef):
            fdef = cast(FuncDef, defn)
        else:
            fdef = None
        
        self.enter()
        
        if fdef:
            # The cast below will work since non-method create will cause
            # semantic analysis to fail, and type checking won't be done.
            if (fdef.info and fdef.name() == '__init__' and
                    not isinstance(cast(Callable, typ).ret_type, Void) and
                    not self.dynamic_funcs[-1]):
                self.fail(messages.INIT_MUST_NOT_HAVE_RETURN_TYPE, defn.type)
        
        # Push return type.
        self.return_types.append(cast(Callable, typ).ret_type)
        
        # Store argument types.
        ctype = cast(Callable, typ)
        nargs = len(defn.args)
        for i in range(len(ctype.arg_types)):
            arg_type = ctype.arg_types[i]
            if ctype.arg_kinds[i] == nodes.ARG_STAR:
                arg_type = self.named_generic_type('builtins.list', [arg_type])
            elif ctype.arg_kinds[i] == nodes.ARG_STAR2:
                arg_type = self.named_generic_type('builtins.dict',
                                                   [self.str_type(), arg_type])
            defn.args[i].type = arg_type
        
        # Type check initialization expressions.
        for j in range(len(defn.init)):
            if defn.init[j]:
                self.accept(defn.init[j])
        
        # Type check body.
        self.accept(defn.body)
        
        # Pop return type.
        self.return_types.pop()
        
        self.leave()
    
    def check_method_override(self, defn: FuncBase) -> None:
        """Check if function definition is compatible with base classes."""
        # Check against definitions in base classes.
        for base in defn.info.mro[1:]:
            self.check_method_or_accessor_override_for_base(defn, base)
    
    def check_method_or_accessor_override_for_base(self, defn: FuncBase,
                                                   base: TypeInfo) -> None:
        """Check if method definition is compatible with a base class."""
        if base:
            if defn.name() != '__init__':
                # Check method override (__init__ is special).
                base_attr = base.names.get(defn.name())
                if base_attr:
                    # The name of the method is defined in the base class.
                    
                    # Construct the type of the overriding method.
                    typ = method_type(defn)
                    # Map the overridden method type to subtype context so that
                    # it can be checked for compatibility.
                    original_type = base_attr.type()
                    if original_type is None and isinstance(base_attr.node,
                                                            FuncDef):
                        original_type = function_type(cast(FuncDef,
                                                           base_attr.node))
                    if isinstance(original_type, FunctionLike):
                        original_type = map_type_from_supertype(
                            method_type(cast(FunctionLike, original_type)),
                            defn.info, base)
                        # Check that the types are compatible.
                        # TODO overloaded signatures
                        self.check_override(cast(FunctionLike, typ),
                                            cast(FunctionLike, original_type),
                                            defn.name(),
                                            base.name(),
                                            defn)
                    else:
                        self.msg.signature_incompatible_with_supertype(
                            defn.name(), base.name(), defn)
    
    def check_override(self, override: FunctionLike, original: FunctionLike,
                       name: str, supertype: str, node: Context) -> None:
        """Check a method override with given signatures.

        Arguments:
          override:  The signature of the overriding method.
          original:  The signature of the original supertype method.
          name:      The name of the subtype. This and the next argument are
                     only used for generating error messages.
          supertype: The name of the supertype.
        """
        if (isinstance(override, Overloaded) or
                isinstance(original, Overloaded) or
                len(cast(Callable, override).arg_types) !=
                    len(cast(Callable, original).arg_types) or
                cast(Callable, override).min_args !=
                    cast(Callable, original).min_args):
            if not is_subtype(override, original):
                self.msg.signature_incompatible_with_supertype(
                    name, supertype, node)
            return
        else:
            # Give more detailed messages for the common case of both
            # signatures having the same number of arguments and no
            # intersection types.
            
            coverride = cast(Callable, override)
            coriginal = cast(Callable, original)
            
            for i in range(len(coverride.arg_types)):
                if not is_equivalent(coriginal.arg_types[i],
                                     coverride.arg_types[i]):
                    self.msg.argument_incompatible_with_supertype(
                        i + 1, name, supertype, node)
            
            if not is_subtype(coverride.ret_type, coriginal.ret_type):
                self.msg.return_type_incompatible_with_supertype(
                    name, supertype, node)
    
    def visit_type_def(self, defn: TypeDef) -> Type:
        """Type check a class definition."""
        typ = defn.info
        self.errors.push_type(defn.name)
        self.accept(defn.defs)
        self.errors.pop_type()
    
    #
    # Statements
    #
    
    def visit_block(self, b: Block) -> Type:
        for s in b.body:
            self.accept(s)
    
    def visit_assignment_stmt(self, s: AssignmentStmt) -> Type:
        """Type check an assignment statement.

        Handle all kinds of assignment statements (simple, indexed, multiple).
        """
        self.check_assignments(self.expand_lvalues(s.lvalues[-1]), s.rvalue)
        if len(s.lvalues) > 1:
            # Chained assignment (e.g. x = y = ...).
            # Make sure that rvalue type will not be reinferred.
            rvalue = self.temp_node(self.type_map[s.rvalue], s)
            for lv in s.lvalues[:-1]:
                self.check_assignments(self.expand_lvalues(lv), rvalue)

    def check_assignments(self, lvalues: List[Node],
                          rvalue: Node) -> None:        
        # Collect lvalue types. Index lvalues require special consideration,
        # since we cannot typecheck them until we know the rvalue type.
        # For each lvalue, one of lvalue_types[i] or index_lvalues[i] is not
        # None.
        lvalue_types = [] # type: List[Type]       # Each may be None
        index_lvalues = [] # type: List[IndexExpr] # Each may be None
        inferred = [] # type: List[Var]
        is_inferred = False
        
        for lv in lvalues:
            if self.is_definition(lv):
                is_inferred = True
                if isinstance(lv, NameExpr):
                    n = cast(NameExpr, lv)
                    inferred.append(cast(Var, n.node))
                else:
                    m = cast(MemberExpr, lv)
                    self.accept(m.expr)
                    inferred.append(m.def_var)
                lvalue_types.append(None)
                index_lvalues.append(None)
            elif isinstance(lv, IndexExpr):
                ilv = cast(IndexExpr, lv)
                lvalue_types.append(None)
                index_lvalues.append(ilv)
                inferred.append(None)
            elif isinstance(lv, MemberExpr):
                mlv = cast(MemberExpr, lv)
                lvalue_types.append(
                    self.expr_checker.analyse_ordinary_member_access(mlv,
                                                                     True))
                self.store_type(mlv, lvalue_types[-1])
                index_lvalues.append(None)
                inferred.append(None)
            else:
                lvalue_types.append(self.accept(lv))
                index_lvalues.append(None)
                inferred.append(None)
        
        if len(lvalues) == 1:
            # Single lvalue.
            self.check_single_assignment(lvalue_types[0],
                                         index_lvalues[0], rvalue, rvalue)
        else:
            self.check_multi_assignment(lvalue_types, index_lvalues,
                                        rvalue, rvalue)
        if is_inferred:
            self.infer_variable_type(inferred, lvalues, self.accept(rvalue),
                                     rvalue)
    
    def is_definition(self, s):
        return ((isinstance(s, NameExpr) or isinstance(s, MemberExpr)) and
                s.is_def)
    
    def expand_lvalues(self, n: Node) -> List[Node]:
        if isinstance(n, TupleExpr):
            return self.expr_checker.unwrap_list(cast(TupleExpr, n).items)
        elif isinstance(n, ListExpr):
            return self.expr_checker.unwrap_list(cast(ListExpr, n).items)
        elif isinstance(n, ParenExpr):
            return self.expand_lvalues(cast(ParenExpr, n).expr)
        else:
            return [n]
    
    def infer_variable_type(self, names: List[Var], lvalues: List[Node],
                            init_type: Type, context: Context) -> None:
        """Infer the type of initialized variables from initializer type."""
        if isinstance(init_type, Void):
            self.check_not_void(init_type, context)
        elif not self.is_valid_inferred_type(init_type):
            # We cannot use the type of the initialization expression for type
            # inference (it's not specific enough).
            self.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
        else:
            # Infer type of the target.
            
            # Make the type more general (strip away function names etc.).
            init_type = strip_type(init_type)
            
            if len(names) > 1:
                if isinstance(init_type, TupleType):
                    tinit_type = cast(TupleType, init_type)
                    # Initializer with a tuple type.
                    if len(tinit_type.items) == len(names):
                        for i in range(len(names)):
                            self.set_inferred_type(names[i], lvalues[i],
                                                   tinit_type.items[i])
                    else:
                        self.msg.incompatible_value_count_in_assignment(
                            len(names), len(tinit_type.items), context)
                elif (isinstance(init_type, Instance) and
                        cast(Instance, init_type).type.fullname() ==
                            'builtins.list'):
                    # Initializer with an array type.
                    item_type = cast(Instance, init_type).args[0]
                    for i in range(len(names)):
                        self.set_inferred_type(names[i], lvalues[i], item_type)
                elif isinstance(init_type, AnyType):
                    for i in range(len(names)):
                        self.set_inferred_type(names[i], lvalues[i], AnyType())
                else:
                    self.fail(messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT,
                              context)
            else:
                for v in names:
                    self.set_inferred_type(v, lvalues[0], init_type)

    def set_inferred_type(self, var: Var, lvalue: Node, type: Type) -> None:
        """Store inferred variable type.

        Store the type to both the variable node and the expression node that
        refers to the variable (lvalue). If var is None, do nothing.
        """
        if var:
            var.type = type
            self.store_type(lvalue, type)
    
    def is_valid_inferred_type(self, typ: Type) -> bool:
        """Is an inferred type invalid?

        Examples include the None type or a type with a None component.
        """
        if is_same_type(typ, NoneTyp()):
            return False
        elif isinstance(typ, Instance):
            for arg in cast(Instance, typ).args:
                if not self.is_valid_inferred_type(arg):
                    return False
        elif isinstance(typ, TupleType):
            for item in cast(TupleType, typ).items:
                if not self.is_valid_inferred_type(item):
                    return False
        return True
    
    def check_multi_assignment(self, lvalue_types: List[Type],
                               index_lvalues: List[IndexExpr],
                               rvalue: Node,
                               context: Context,
                               msg: str = None) -> None:
        if not msg:
            msg = messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT
        # First handle case where rvalue is of form Undefined, ...
        rvalue_type = get_undefined_tuple(rvalue)
        undefined_rvalue = True
        if not rvalue_type:
            # Infer the type of an ordinary rvalue expression.
            rvalue_type = self.accept(rvalue) # TODO maybe elsewhere; redundant
            undefined_rvalue = False
        # Try to expand rvalue to lvalue(s).
        if isinstance(rvalue_type, AnyType):
            pass
        elif isinstance(rvalue_type, TupleType):
            # Rvalue with tuple type.
            trvalue = cast(TupleType, rvalue_type)
            items = [] # type: List[Type]
            for i in range(len(lvalue_types)):
                if lvalue_types[i]:
                    items.append(lvalue_types[i])
                elif i < len(trvalue.items):
                    # TODO Figure out more precise type context, probably
                    #      based on the type signature of the _set method.
                    items.append(trvalue.items[i])
            if not undefined_rvalue:
                # Infer rvalue again, now in the correct type context.
                trvalue = cast(TupleType, self.accept(rvalue,
                                                      TupleType(items)))
            if len(trvalue.items) != len(lvalue_types):
                self.msg.incompatible_value_count_in_assignment(
                    len(lvalue_types), len(trvalue.items), context)
            else:
                # The number of values is compatible. Check their types.
                for j in range(len(lvalue_types)):
                    self.check_single_assignment(
                        lvalue_types[j], index_lvalues[j],
                        self.temp_node(trvalue.items[j]), context, msg)
        elif (isinstance(rvalue_type, Instance) and
               cast(Instance, rvalue_type).type.fullname() == 'builtins.list'):
            # Rvalue with list type.
            item_type = cast(Instance, rvalue_type).args[0]
            for k in range(len(lvalue_types)):
                self.check_single_assignment(lvalue_types[k],
                                             index_lvalues[k],
                                             self.temp_node(item_type),
                                             context, msg)
        else:
            self.fail(msg, context)
    
    def check_single_assignment(self,
            lvalue_type: Type, index_lvalue: IndexExpr,
            rvalue: Node, context: Context,
            msg: str = messages.INCOMPATIBLE_TYPES_IN_ASSIGNMENT) -> None:
        """Type check an assignment.

        If lvalue_type is None, the index_lvalue argument must be the
        index expr for indexed assignment (__setitem__).
        Otherwise, lvalue_type is used as the type of the lvalue.
        """
        if lvalue_type:
            if refers_to_fullname(rvalue, 'typing.Undefined'):
                # The rvalue is just 'Undefined'; this is always valid.
                # Infer the type of 'Undefined' from the lvalue type.
                self.store_type(rvalue, lvalue_type)
                return
            rvalue_type = self.accept(rvalue, lvalue_type)
            self.check_subtype(rvalue_type, lvalue_type, context, msg)
        elif index_lvalue:
            self.check_indexed_assignment(index_lvalue, rvalue, context)
    
    def check_indexed_assignment(self, lvalue: IndexExpr,
                                 rvalue: Node, context: Context) -> None:
        """Type check indexed assignment base[index] = rvalue.

        The lvalue argument is the base[index] expression.
        """
        basetype = self.accept(lvalue.base)
        method_type = self.expr_checker.analyse_external_member_access(
            '__setitem__', basetype, context)
        lvalue.method_type = method_type
        self.expr_checker.check_call(method_type, [lvalue.index, rvalue],
                                     [nodes.ARG_POS, nodes.ARG_POS],
                                     context)
    
    def visit_expression_stmt(self, s: ExpressionStmt) -> Type:
        self.accept(s.expr)
    
    def visit_return_stmt(self, s: ReturnStmt) -> Type:
        """Type check a return statement."""
        if self.is_within_function():
            if s.expr:
                # Return with a value.
                typ = self.accept(s.expr, self.return_types[-1])
                # Returning a value of type dynamic is always fine.
                if not isinstance(typ, AnyType):
                    if isinstance(self.return_types[-1], Void):
                        self.fail(messages.NO_RETURN_VALUE_EXPECTED, s)
                    else:
                        self.check_subtype(
                            typ, self.return_types[-1], s,
                            messages.INCOMPATIBLE_RETURN_VALUE_TYPE)
            else:
                # Return without a value.
                if (not isinstance(self.return_types[-1], Void) and
                        not self.is_dynamic_function()):
                    self.fail(messages.RETURN_VALUE_EXPECTED, s)
    
    def visit_yield_stmt(self, s: YieldStmt) -> Type:
        return_type = self.return_types[-1]
        if isinstance(return_type, Instance):
            inst = cast(Instance, return_type)
            if inst.type.fullname() != 'typing.Iterator':
                self.fail(messages.INVALID_RETURN_TYPE_FOR_YIELD, s)
                return None
            expected_item_type = inst.args[0]
        elif isinstance(return_type, AnyType):
            expected_item_type = AnyType()
        else:
            self.fail(messages.INVALID_RETURN_TYPE_FOR_YIELD, s)
            return None
        actual_item_type = self.accept(s.expr, expected_item_type)
        self.check_subtype(actual_item_type, expected_item_type, s)
    
    def visit_if_stmt(self, s: IfStmt) -> Type:
        """Type check an if statement."""
        for e in s.expr:
            t = self.accept(e)
            self.check_not_void(t, e)
        for b in s.body:
            self.accept(b)
        if s.else_body:
            self.accept(s.else_body)
    
    def visit_while_stmt(self, s: WhileStmt) -> Type:
        """Type check a while statement."""
        t = self.accept(s.expr)
        self.check_not_void(t, s)
        self.accept(s.body)
        if s.else_body:
            self.accept(s.else_body)
    
    def visit_operator_assignment_stmt(self,
                                       s: OperatorAssignmentStmt) -> Type:
        """Type check an operator assignment statement, e.g. x += 1."""
        lvalue_type = self.accept(s.lvalue)
        rvalue_type, method_type = self.expr_checker.check_op(
            nodes.op_methods[s.op], lvalue_type, s.rvalue, s)
        
        if isinstance(s.lvalue, IndexExpr):
            lv = cast(IndexExpr, s.lvalue)
            self.check_single_assignment(None, lv, s.rvalue, s.rvalue)
        else:
            if not is_subtype(rvalue_type, lvalue_type):
                self.msg.incompatible_operator_assignment(s.op, s)
    
    def visit_assert_stmt(self, s: AssertStmt) -> Type:
        self.accept(s.expr)
    
    def visit_raise_stmt(self, s: RaiseStmt) -> Type:
        """Type check a raise statement."""
        if s.expr:
            typ = self.accept(s.expr)
            self.check_subtype(typ,
                               self.named_type('builtins.BaseException'), s,
                               messages.INVALID_EXCEPTION_TYPE)
    
    def visit_try_stmt(self, s: TryStmt) -> Type:
        """Type check a try statement."""
        self.accept(s.body)
        for i in range(len(s.handlers)):
            if s.types[i]:
                t = self.exception_type(s.types[i])
                if s.vars[i]:
                    self.check_assignments([s.vars[i]],
                                           self.temp_node(t, s.vars[i]))
            self.accept(s.handlers[i])
        if s.finally_body:
            self.accept(s.finally_body)
        if s.else_body:
            self.accept(s.else_body)
    
    def exception_type(self, n: Node) -> Type:
        if isinstance(n, ParenExpr):
            # Multiple exception types (...).
            unwrapped = self.expr_checker.unwrap(n)
            if isinstance(unwrapped, TupleExpr):
                tupleexpr = cast(TupleExpr, unwrapped)
                t = None # type: Type
                for n in tupleexpr.items:
                    tt = self.exception_type(n)
                    if t:
                        t = join_types(t, tt, self.basic_types())
                    else:
                        t = tt
                return t
        else:
            # A single exception type; should evaluate to a type object type.
            type = self.accept(n)
            return self.check_exception_type(type, n)
        self.fail('Unsupported exception', n)
        return AnyType()

    @overload
    def check_exception_type(self, type: FunctionLike,
                             context: Context) -> Type:
        item = type.items()[0]
        ret = item.ret_type
        if (is_subtype(ret, self.named_type('builtins.BaseException'))
                and item.is_type_obj()):
            return ret
        else:
            self.fail(messages.INVALID_EXCEPTION_TYPE, context)
            return AnyType()        

    @overload
    def check_exception_type(self, type: AnyType, context: Context) -> Type:
        return AnyType()

    @overload
    def check_exception_type(self, type: Type, context: Context) -> Type:
        self.fail(messages.INVALID_EXCEPTION_TYPE, context)
        return AnyType()

    def visit_for_stmt(self, s: ForStmt) -> Type:
        """Type check a for statement."""
        item_type = self.analyse_iterable_item_type(s.expr)
        self.analyse_index_variables(s.index, s.is_annotated(), item_type, s)
        self.accept(s.body)

    def analyse_iterable_item_type(self, expr: Node) -> Type:
        """Analyse iterable expression and return iterator item type."""
        iterable = self.accept(expr)
        
        self.check_not_void(iterable, expr)
        if isinstance(iterable, TupleType):
            tuple = cast(TupleType, iterable)
            joined = NoneTyp() # type: Type
            for item in tuple.items:
                joined = join_types(joined, item, self.basic_types())
            if isinstance(joined, ErrorType):
                self.fail(messages.CANNOT_INFER_ITEM_TYPE, expr)
                joined = AnyType()
            return joined
        else:
            # Non-tuple iterable.
            self.check_subtype(iterable,
                               self.named_generic_type('builtins.Iterable',
                                                       [AnyType()]),
                               expr, messages.ITERABLE_EXPECTED)

            echk = self.expr_checker
            method = echk.analyse_external_member_access('__iter__', iterable,
                                                         expr)
            iterator = echk.check_call(method, [], [], expr)[0]
            if self.pyversion >= 3:
                nextmethod = '__next__'
            else:
                nextmethod = 'next'
            method = echk.analyse_external_member_access(nextmethod, iterator,
                                                         expr)
            return echk.check_call(method, [], [], expr)[0]

    def analyse_index_variables(self, index: List[NameExpr],
                                is_annotated: bool,
                                item_type: Type, context: Context) -> None:
        """Type check or infer for loop or list comprehension index vars."""
        if not is_annotated:
            # Create a temporary copy of variables with Node item type.
            # TODO this is ugly
            node_index = [] # type: List[Node]
            for i in index:
                node_index.append(i)
            self.check_assignments(node_index,
                                   self.temp_node(item_type, context))
        elif len(index) == 1:
            v = cast(Var, index[0].node)
            if v.type:
                self.check_single_assignment(v.type, None,
                                           self.temp_node(item_type), context,
                                           messages.INCOMPATIBLE_TYPES_IN_FOR)
        else:
            t = [] # type: List[Type]
            for ii in index:
                v = cast(Var, ii.node)
                if v.type:
                    t.append(v.type)
                else:
                    t.append(AnyType())
            self.check_multi_assignment(t, [None] * len(index),
                                        self.temp_node(item_type), context,
                                        messages.INCOMPATIBLE_TYPES_IN_FOR)
    
    def visit_del_stmt(self, s: DelStmt) -> Type:
        if isinstance(s.expr, IndexExpr):
            e = cast(IndexExpr, s.expr)  # Cast
            m = MemberExpr(e.base, '__delitem__')
            m.line = s.line
            c = CallExpr(m, [e.index], [nodes.ARG_POS], [None])
            c.line = s.line
            return c.accept(self)
        else:
            return None # this case is handled in semantical analysis
    
    def visit_decorator(self, e: Decorator) -> Type:
        e.func.accept(self)
        sig = function_type(e.func) # type: Type
        # Process decorators from the inside out.
        for i in range(len(e.decorators)):
            n = len(e.decorators) - 1 - i
            dec = self.accept(e.decorators[n])
            temp = self.temp_node(sig)
            sig, t2 = self.expr_checker.check_call(dec, [temp],
                                                   [nodes.ARG_POS], e)
        sig = set_callable_name(sig, e.func)
        e.var.type = sig
        e.var.is_ready = True

    def visit_with_stmt(self, s: WithStmt) -> Type:
        echk = self.expr_checker
        for expr, name in zip(s.expr, s.name):
            ctx = self.accept(expr)
            enter = echk.analyse_external_member_access('__enter__', ctx, expr)
            obj = echk.check_call(enter, [], [], expr)[0]
            if name:
                self.check_assignments([name], self.temp_node(obj, expr))
            exit = echk.analyse_external_member_access('__exit__', ctx, expr)
            arg = self.temp_node(AnyType(), expr)
            echk.check_call(exit, [arg] * 3, [nodes.ARG_POS] * 3, expr)
        self.accept(s.body)

    def visit_print_stmt(self, s: PrintStmt) -> Type:
        for arg in s.args:
            self.accept(arg)            
    
    #
    # Expressions
    #
    
    def visit_name_expr(self, e: NameExpr) -> Type:
        return self.expr_checker.visit_name_expr(e)
    
    def visit_paren_expr(self, e: ParenExpr) -> Type:
        return self.expr_checker.visit_paren_expr(e)
    
    def visit_call_expr(self, e: CallExpr) -> Type:
        return self.expr_checker.visit_call_expr(e)
    
    def visit_member_expr(self, e: MemberExpr) -> Type:
        return self.expr_checker.visit_member_expr(e)
    
    def visit_int_expr(self, e: IntExpr) -> Type:
        return self.expr_checker.visit_int_expr(e)
    
    def visit_str_expr(self, e: StrExpr) -> Type:
        return self.expr_checker.visit_str_expr(e)
    
    def visit_bytes_expr(self, e: BytesExpr) -> Type:
        return self.expr_checker.visit_bytes_expr(e)
    
    def visit_unicode_expr(self, e: UnicodeExpr) -> Type:
        return self.expr_checker.visit_unicode_expr(e)
    
    def visit_float_expr(self, e: FloatExpr) -> Type:
        return self.expr_checker.visit_float_expr(e)
    
    def visit_op_expr(self, e: OpExpr) -> Type:
        return self.expr_checker.visit_op_expr(e)
    
    def visit_unary_expr(self, e: UnaryExpr) -> Type:
        return self.expr_checker.visit_unary_expr(e)
    
    def visit_index_expr(self, e: IndexExpr) -> Type:
        return self.expr_checker.visit_index_expr(e)
    
    def visit_cast_expr(self, e: CastExpr) -> Type:
        return self.expr_checker.visit_cast_expr(e)
    
    def visit_super_expr(self, e: SuperExpr) -> Type:
        return self.expr_checker.visit_super_expr(e)
    
    def visit_type_application(self, e: TypeApplication) -> Type:
        return self.expr_checker.visit_type_application(e)

    def visit_type_var_expr(self, e: TypeVarExpr) -> Type:
        # TODO Perhaps return a special type used for type variables only?
        return AnyType()
    
    def visit_list_expr(self, e: ListExpr) -> Type:
        return self.expr_checker.visit_list_expr(e)
    
    def visit_set_expr(self, e: SetExpr) -> Type:
        return self.expr_checker.visit_set_expr(e)
    
    def visit_tuple_expr(self, e: TupleExpr) -> Type:
        return self.expr_checker.visit_tuple_expr(e)
    
    def visit_dict_expr(self, e: DictExpr) -> Type:
        return self.expr_checker.visit_dict_expr(e)
    
    def visit_slice_expr(self, e: SliceExpr) -> Type:
        return self.expr_checker.visit_slice_expr(e)
    
    def visit_func_expr(self, e: FuncExpr) -> Type:
        return self.expr_checker.visit_func_expr(e)
    
    def visit_list_comprehension(self, e: ListComprehension) -> Type:
        return self.expr_checker.visit_list_comprehension(e)

    def visit_generator_expr(self, e: GeneratorExpr) -> Type:
        return self.expr_checker.visit_generator_expr(e)

    def visit_undefined_expr(self, e: UndefinedExpr) -> Type:
        return self.expr_checker.visit_undefined_expr(e)

    def visit_temp_node(self, e: TempNode) -> Type:
        return e.type

    #
    # Currently unsupported features
    #

    def visit_conditional_expr(self, e: ConditionalExpr) -> Type:
        return self.msg.not_implemented('conditional expression', e)
    
    #
    # Helpers
    #
    
    def check_subtype(self, subtype: Type, supertype: Type, context: Context,
                       msg: str = messages.INCOMPATIBLE_TYPES) -> None:
        """Generate an error if the subtype is not compatible with
        supertype."""
        if not is_subtype(subtype, supertype):
            if isinstance(subtype, Void):
                self.msg.does_not_return_value(subtype, context)
            else:
                self.fail(msg, context)
    
    def named_type(self, name: str) -> Instance:
        """Return an instance type with type given by the name and no
        type arguments. For example, named_type('builtins.object')
        produces the object type.
        """
        # Assume that the name refers to a type.
        sym = self.lookup_qualified(name)
        return Instance(cast(TypeInfo, sym.node), [])
    
    def named_type_if_exists(self, name: str) -> Type:
        """Return named instance type, or UnboundType if the type was
        not defined.
        
        This is used to simplify test cases by avoiding the need to
        define basic types not needed in specific test cases (tuple
        etc.).
        """
        try:
            # Assume that the name refers to a type.
            sym = self.lookup_qualified(name)
            return Instance(cast(TypeInfo, sym.node), [])
        except KeyError:
            return UnboundType(name)
    
    def named_generic_type(self, name: str, args: List[Type]) -> Instance:
        """Return an instance with the given name and type
        arguments. Assume that the number of arguments is correct.
        """
        # Assume that the name refers to a compatible generic type.
        sym = self.lookup_qualified(name)
        return Instance(cast(TypeInfo, sym.node), args)
    
    def type_type(self) -> Instance:
        """Return instance type 'type'."""
        return self.named_type('builtins.type')
    
    def object_type(self) -> Instance:
        """Return instance type 'object'."""
        return self.named_type('builtins.object')
    
    def bool_type(self) -> Instance:
        """Return instance type 'bool'."""
        return self.named_type('builtins.bool')
    
    def str_type(self) -> Instance:
        """Return instance type 'str'."""
        return self.named_type('builtins.str')
    
    def tuple_type(self) -> Type:
        """Return instance type 'tuple'."""
        # We need the tuple for analysing member access. We want to be able to
        # do this even if tuple type is not available (useful in test cases),
        # so we return an unbound type if there is no tuple type.
        return self.named_type_if_exists('builtins.tuple')
    
    def check_type_equivalency(self, t1: Type, t2: Type, node: Context,
                               msg: str = messages.INCOMPATIBLE_TYPES) -> None:
        """Generate an error if the types are not equivalent. The
        dynamic type is equivalent with all types.
        """
        if not is_equivalent(t1, t2):
            self.fail(msg, node)
    
    def store_type(self, node: Node, typ: Type) -> None:
        """Store the type of a node in the type map."""
        self.type_map[node] = typ
    
    def is_dynamic_function(self) -> bool:
        return len(self.dynamic_funcs) > 0 and self.dynamic_funcs[-1]
    
    def lookup(self, name: str, kind: int) -> SymbolTableNode:
        """Look up a definition from the symbol table with the given name.
        TODO remove kind argument
        """
        if self.locals is not None and name in self.locals:
            return self.locals[name]
        elif self.class_tvars is not None and name in self.class_tvars:
            return self.class_tvars[name]
        elif name in self.globals:
            return self.globals[name]
        else:
            b = self.globals.get('__builtins__', None)
            if b:
                table = cast(MypyFile, b.node).names
                if name in table:
                    return table[name]
            raise KeyError('Failed lookup: {}'.format(name))
    
    def lookup_qualified(self, name: str) -> SymbolTableNode:
        if '.' not in name:
            return self.lookup(name, GDEF) # FIX kind
        else:
            parts = name.split('.')
            n = self.modules[parts[0]]
            for i in range(1, len(parts) - 1):
                n = cast(MypyFile, ((n.names.get(parts[i], None).node)))
            return n.names[parts[-1]]
    
    def enter(self) -> None:
        self.locals = SymbolTable()
    
    def leave(self) -> None:
        self.locals = None
    
    def basic_types(self) -> BasicTypes:
        """Return a BasicTypes instance that contains primitive types that are
        needed for certain type operations (joins, for example).
        """
        return BasicTypes(self.object_type(), self.type_type(),
                          self.named_type_if_exists('builtins.tuple'),
                          self.named_type_if_exists('builtins.function'))
    
    def is_within_function(self) -> bool:
        """Are we currently type checking within a function?

        I.e. not at class body or at the top level.
        """
        return self.return_types != []
    
    def check_not_void(self, typ: Type, context: Context) -> None:
        """Generate an error if the type is Void."""
        if isinstance(typ, Void):
            self.msg.does_not_return_value(typ, context)
    
    def temp_node(self, t: Type, context: Context = None) -> Node:
        """Create a temporary node with the given, fixed type."""
        temp = TempNode(t)
        if context:
            temp.set_line(context.get_line())
        return temp
    
    def fail(self, msg: str, context: Context) -> None:
        """Produce an error message."""
        self.msg.fail(msg, context)


def map_type_from_supertype(typ: Type, sub_info: TypeInfo,
                            super_info: TypeInfo) -> Type:
    """Map type variables in a type defined in a supertype context to be valid
    in the subtype context. Assume that the result is unique; if more than
    one type is possible, return one of the alternatives.
    
    For example, assume
    
      class D(Generic[S]) ...
      class C(D[E[T]], Generic[T]) ...
    
    Now S in the context of D would be mapped to E[T] in the context of C.
    """
    # Create the type of self in subtype, of form t[a1, ...].
    inst_type = self_type(sub_info)
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


def get_undefined_tuple(rvalue: Node) -> Type:
    """Get tuple type corresponding to a tuple of Undefined values.

    The type is Tuple[Any, ...]. If rvalue is not of the right form, return
    None.
    """
    if isinstance(rvalue, TupleExpr):
        tuple_expr = cast(TupleExpr, rvalue)
        for item in tuple_expr.items:
            if not refers_to_fullname(item, 'typing.Undefined'):
                break
        else:
            return TupleType([AnyType()] * len(tuple_expr.items))
    return None
