"""Abstract syntax tree node classes (i.e. parse tree)."""

import re

from lex import Token
from strconv import StrConv
from visitor import NodeVisitor
from util import dump_tagged, short_type


interface Context:
    # Supertype for objects that are valid as error message locations.
    int get_line(self)


import mtypes


# Variable kind constants
LDEF = 0
GDEF = 1
MDEF = 2
MODULE_REF = 3
TVAR = 4 # Constant for type variable nodes in symbol table


node_kinds = {
    LDEF: 'Ldef',
    GDEF: 'Gdef',
    MDEF: 'Mdef',
    MODULE_REF: 'ModuleRef',
    TVAR: 'Tvar'
}


# Nodes that can be stored in the symbol table.
# TODO better name
# TODO remove or combine with SymNode?
interface AccessorNode: pass


interface SymNode:
    # Nodes that can be stored in a symbol table.
    # TODO do not use methods for these
    str name(self)
    str full_name(self)


class Node(Context):
    """Common base class for all non-type parse tree nodes."""
    
    int line = -1
    any repr = None # Textual representation
    
    str __str__(self):
        return self.accept(StrConv())
    
    Node set_line(self, Token tok):
        self.line = tok.line
        return self
    
    Node set_line(self, int line):
        self.line = line
        return self

    int get_line(self):
        # TODO this should be just 'line'
        return self.line
    
    T accept<T>(self, NodeVisitor<T> visitor):
        raise RuntimeError('Not implemented')


class MypyFile(Node, AccessorNode, SymNode):
    """The abstract syntax tree of a single source file."""
    
    str _name         # Module name ('__main__' for initial file)
    str _full_name    # Qualified module name
    str path          # Path to the file (None if not known)
    Node[] defs       # Global definitions and statements
    bool is_bom       # Is there a UTF-8 BOM at the start?
    SymbolTable names
    
    void __init__(self, Node[] defs, bool is_bom=False):
        self.defs = defs
        self.line = 1  # Dummy line number
        self.is_bom = is_bom

    str name(self):
        return self._name

    str full_name(self):
        return self._full_name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_mypy_file(self)


class Import(Node):
    """import m [as n]"""    
    list<tuple<str, str>> ids     # (module id, as id)
    
    void __init__(self, list<tuple<str, str>> ids):
        self.ids = ids
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_import(self)


class ImportFrom(Node):
    """from m import x, ..."""
    str id
    tuple<str, str>[] names # Tuples (name, as name)
    
    void __init__(self, str id, tuple<str, str>[] names):
        self.id = id
        self.names = names
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_import_from(self)


class ImportAll(Node):
    """from m import *"""
    str id
    
    void __init__(self, str id):
        self.id = id
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_import_all(self)


class FuncBase(Node, AccessorNode):
    """Abstract base class for function-like nodes"""
    mtypes.Type type # Type signature (Callable or Overloaded)
    TypeInfo info    # If method, reference to TypeInfo
    str name(self):
        pass
    bool is_method(self):
        return bool(self.info)


class OverloadedFuncDef(FuncBase, SymNode):
    """A logical node representing all the variants of an overloaded function.

    This node has no explicit representation in the source program.
    Overloaded variants must be consecutive in the source file.
    """
    FuncDef[] items
    str _full_name
    
    void __init__(self, FuncDef[] items):
        self.items = items
        self.set_line(items[0].line)
    
    str name(self):
        return self.items[1].name()

    str full_name(self):
        return self._full_name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_overloaded_func_def(self)


class FuncItem(FuncBase):
    Var[] args      # Argument names
    int[] arg_kinds # Kinds of arguments (ARG_*)
    
    # Initialization expessions for fixed args; None if no initialiser
    AssignmentStmt[] init
    int min_args           # Minimum number of arguments
    int max_pos            # Maximum number of positional arguments, -1 if
                           # no explicit limit (*args not included)
    Block body
    bool is_implicit    # Implicit dynamic types?
    bool is_overload    # Is this an overload variant of function with
                        # more than one overload variant?
    
    void __init__(self, Var[] args, int[] arg_kinds, Node[] init,
                  Block body, mtypes.Type typ=None):
        self.args = args
        self.arg_kinds = arg_kinds
        self.max_pos = arg_kinds.count(ARG_POS) + arg_kinds.count(ARG_OPT)
        self.body = body
        self.type = typ
        self.is_implicit = typ is None
        self.is_overload = False
        
        AssignmentStmt[] i2 = []
        self.min_args = 0
        for i in range(len(init)):
            if init[i] is not None:
                rvalue = init[i]
                lvalue = NameExpr(args[i].name()).set_line(rvalue.line)
                assign = AssignmentStmt([lvalue], rvalue)
                assign.set_line(rvalue.line)
                i2.append(assign)
            else:
                i2.append(None)
                if i < self.max_fixed_argc():
                    self.min_args = i + 1
        self.init = i2
    
    int max_fixed_argc(self):
        return self.max_pos
    
    Node set_line(self, Token tok):
        super().set_line(tok)
        for n in self.args:
            n.line = self.line
        return self
    
    Node set_line(self, int tok):
        super().set_line(tok)
        for n in self.args:
            n.line = self.line
        return self
    
    Node[] init_expressions(self):
        Node[] res = []
        for i in self.init:
            if i is not None:
                res.append(i.rvalue)
            else:
                res.append(None)
        return res


class FuncDef(FuncItem, SymNode):
    str _full_name      # Name with module prefix
    
    void __init__(self,
                  str name,          # Function name
                  Var[] args,        # Argument names
                  int[] arg_kinds,   # Arguments kinds (nodes.ARG_*)
                  Node[] init,       # Initializers (each may be None)
                  Block body,
                  mtypes.Type typ=None):
        super().__init__(args, arg_kinds, init, body, typ)
        self._name = name

    str name(self):
        return self._name
    
    str full_name(self):
        return self._full_name

    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_func_def(self)
    
    bool is_constructor(self):
        return self.info is not None and self._name == '__init__'

    str get_name(self):
        """TODO merge with name()"""
        return self._name


class Decorator(Node):
    Node func       # FuncDef or Decorator
    Node decorator
    
    void __init__(self, Node func, Node decorator):
        self.func = func
        self.decorator = decorator
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_decorator(self)


class Var(Node, AccessorNode, SymNode):
    """A variable.

    It can refer to global/local variable or a data attribute.
    """
    str _name        # Name without module prefix
    str _full_name   # Name with module prefix
    bool is_init     # Is is initialized?
    TypeInfo info    # Defining class (for member variables)
    mtypes.Type type # Declared type, or None if none
    bool is_self     # Is this the first argument to an ordinary method
                     # (usually "self")?
    
    void __init__(self, str name, mtypes.Type type=None):
        self._name = name
        self.type = type
        self.is_init = False
        self.is_self = False

    str name(self):
        return self._name

    str full_name(self):
        return self._full_name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_var(self)


class TypeDef(Node):
    """Class or interface definition"""
    str name        # Name of the class without module prefix
    str full_name   # Fully qualified name of the class
    Block defs
    mtypes.TypeVars type_vars
    # Inherited types (Instance or UnboundType).
    mtypes.Type[] base_types
    TypeInfo info    # Related TypeInfo
    bool is_interface
    
    void __init__(self, str name, Block defs,
                  mtypes.TypeVars type_vars=None,
                  mtypes.Type[] base_types=None,
                  bool is_interface=False):
        if not base_types:
            base_types = []
        self.name = name
        self.defs = defs
        self.type_vars = type_vars
        self.base_types = base_types
        self.is_interface = is_interface
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_type_def(self)
    
    bool is_generic(self):
        return self.info.is_generic()


class VarDef(Node):
    """Variable definition with explicit types"""
    Var[] items
    int kind          # LDEF/GDEF/MDEF/...
    Node init         # Expression or None
    bool is_top_level # Is the definition at the top level (not within
                      # a function or a type)?
    bool is_init
    
    void __init__(self, Var[] items, bool is_top_level, Node init=None):
        self.items = items
        self.is_top_level = is_top_level
        self.init = init
        self.is_init = init is not None
    
    TypeInfo info(self):
        return self.items[0].info
    
    Node set_line(self, Token tok):
        super().set_line(tok)
        for n in self.items:
            n.line = self.line
        return self
    
    Node set_line(self, int tok):
        super().set_line(tok)
        for n in self.items:
            n.line = self.line
        return self
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_var_def(self)


class GlobalDecl(Node):
    """Declaration global x, y, ..."""
    str[] names
    
    void __init__(self, str[] names):
        self.names = names
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_global_decl(self)


class Block(Node):
    Node[] body
    
    void __init__(self, Node[] body):
        self.body = body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_block(self)


# Statements


class ExpressionStmt(Node):
    """An expression as a statament, such as print(s)."""
    Node expr
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_expression_stmt(self)


class AssignmentStmt(Node):
    """Assignment statement

    The same node is used for single assignment, multiple assignment
    (e.g. x, y = z) and chained assignment (e.g. x = y = z) and assignments
    that define new names.

    An lvalue can be NameExpr, TupleExpr, ListExpr, MemberExpr, IndexExpr or
    ParenExpr.
    """
    Node[] lvalues
    Node rvalue
    
    void __init__(self, Node[] lvalues, Node rvalue):
        self.lvalues = lvalues
        self.rvalue = rvalue
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_assignment_stmt(self)


class OperatorAssignmentStmt(Node):
    """Operator assignment statement such as x += 1"""
    str op
    Node lvalue
    Node rvalue
    
    void __init__(self, str op, Node lvalue, Node rvalue):
        self.op = op
        self.lvalue = lvalue
        self.rvalue = rvalue
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_operator_assignment_stmt(self)


class WhileStmt(Node):
    Node expr
    Block body
    Block else_body
    
    void __init__(self, Node expr, Block body, Block else_body):
        self.expr = expr
        self.body = body
        self.else_body = else_body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_while_stmt(self)


class ForStmt(Node):
    NameExpr[] index   # Index variables
    mtypes.Type[] types    # Index variable types (each may be None)
    Node expr              # Expression to iterate
    Block body
    Block else_body
    
    void __init__(self, NameExpr[] index, Node expr, Block body,
                  Block else_body, mtypes.Type[] types=None):
        self.index = index
        self.expr = expr
        self.body = body
        self.else_body = else_body
        self.types = types
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_for_stmt(self)
    
    bool is_annotated(self):
        ann = False
        for t in self.types:
            if t is not None:
                ann = True
        return ann


class ReturnStmt(Node):
    Node expr   # Expression or None
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_return_stmt(self)


class AssertStmt(Node):
    Node expr
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_assert_stmt(self)


class YieldStmt(Node):
    Node expr
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_yield_stmt(self)


class DelStmt(Node):
    Node expr
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_del_stmt(self)


class BreakStmt(Node):
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_break_stmt(self)


class ContinueStmt(Node):
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_continue_stmt(self)


class PassStmt(Node):
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_pass_stmt(self)


class IfStmt(Node):
    Node[] expr
    Block[] body
    Block else_body
    
    void __init__(self, Node[] expr, Block[] body, Block else_body):
        self.expr = expr
        self.body = body
        self.else_body = else_body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_if_stmt(self)


class RaiseStmt(Node):
    Node expr
    Node from_expr
    
    void __init__(self, Node expr, Node from_expr=None):
        self.expr = expr
        self.from_expr = from_expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_raise_stmt(self)


class TryStmt(Node):
    Block body                # Try body
    Node[] types          # Except type expressions
    Var[] vars            # Except variable names
    Block[] handlers      # Except bodies
    Block else_body
    Block finally_body
    
    void __init__(self, Block body, Var[] vars, Node[] types,
                  Block[] handlers, Block else_body, Block finally_body):
        self.body = body
        self.vars = vars
        self.types = types
        self.handlers = handlers
        self.else_body = else_body
        self.finally_body = finally_body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_try_stmt(self)


class WithStmt(Node):
    Node[] expr
    Var[] name
    Block body
    
    void __init__(self, Node[] expr, Var[] name, Block body):
        self.expr = expr
        self.name = name
        self.body = body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_with_stmt(self)


# Expressions


class IntExpr(Node):
    """Integer literal"""
    int value
    
    void __init__(self, int value):
        self.value = value
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_int_expr(self)


class StrExpr(Node):
    """String literal"""
    str value
    
    void __init__(self, str value):
        self.value = value
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_str_expr(self)


class BytesExpr(Node):
    """Bytes literal"""
    str value # TODO use bytes
    
    void __init__(self, str value):
        self.value = value
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_bytes_expr(self)


class FloatExpr(Node):
    """Float literal"""
    float value
    
    void __init__(self, float value):
        self.value = value
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_float_expr(self)


class ParenExpr(Node):
    """Parenthesised expression"""
    Node expr
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_paren_expr(self)


class RefExpr(Node):
    """Abstract base class for name-like constructs"""
    int kind      # Ldef/Gdef/Mdef/... (None if not available)
    Node node     # Var, FuncDef or TypeInfo that describes this


class NameExpr(RefExpr):
    """Name expression

    This refers to a local name, global name or a module.
    """
    str name      # Name referred to (may be qualified)
    str full_name # Fully qualified name (or name if not global)
    TypeInfo info # TypeInfo of class surrounding expression (may be None)
    bool is_def   # Does this define a new variable as a lvalue?
    
    void __init__(self, str name):
        self.name = name
        self.is_def = False
    
    def type_node(self):
        return (TypeInfo)self.node
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_name_expr(self)


class MemberExpr(RefExpr):
    """Member access expression x.y"""
    Node expr
    str name
    # Full name if referring to a name in module.
    str full_name
    # True if first assignment to member via self in __init__ (and if not
    # defined in class body). After semantic analysis, this does not take base
    # classes into consideration at all; the type checker deals with these.
    bool is_def = False
    # The variable node related to a definition.
    Var def_var = None
    # Is this direct assignment to a data member (bypassing accessors)?
    bool direct
    
    void __init__(self, Node expr, str name, bool direct=False):
        self.expr = expr
        self.name = name
        self.direct = direct
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_member_expr(self)


# Kinds of arguments
ARG_POS = 0   # Positional argument
ARG_OPT = 1   # Positional, optional argument (functions only, not calls)
ARG_STAR = 2  # *arg argument
ARG_NAMED = 3 # Keyword argument x=y in call, or keyword-only function arg
ARG_STAR2 = 4 # **arg argument


class CallExpr(Node):
    """Call expression"""
    Node callee
    Node[] args
    int[] arg_kinds # ARG_ constants
    str[] arg_names # None if not a keyword argument
    
    void __init__(self, Node callee, Node[] args, int[] arg_kinds,
                  str[] arg_names=None):
        if not arg_names:
            arg_names = <str> [None] * len(args)
        self.callee = callee
        self.args = args
        self.arg_kinds = arg_kinds
        self.arg_names = arg_names
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_call_expr(self)


class IndexExpr(Node):
    """Index expression x[y]"""
    Node base
    Node index
    mtypes.Type method_type  # Inferred __getitem__ method type
    
    void __init__(self, Node base, Node index):
        self.base = base
        self.index = index
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_index_expr(self)


class UnaryExpr(Node):
    """Unary operation"""
    str op
    Node expr
    mtypes.Type method_type  # Inferred operator method type
    
    void __init__(self, str op, Node expr):
        self.op = op
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_unary_expr(self)


class OpExpr(Node):
    """Binary operation (other than . or [], which have specific nodes)"""
    str op
    Node left
    Node right
    # Inferred type for the operator method type (when relevant; None for
    # 'is').
    mtypes.Type method_type
    
    void __init__(self, str op, Node left, Node right):
        self.op = op
        self.left = left
        self.right = right
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_op_expr(self)


class SliceExpr(Node):
    """Slice expression (e.g. 'x:y', 'x:', '::2' or ':').

    This is only valid as index in index expressions.
    """
    Node begin_index  # May be None
    Node end_index    # May be None
    Node stride       # May be None
    
    void __init__(self, Node begin_index, Node end_index, Node stride):
        self.begin_index = begin_index
        self.end_index = end_index
        self.stride = stride
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_slice_expr(self)


class CastExpr(Node):
    """Cast expression (type)expr"""
    Node expr
    mtypes.Type type
    
    void __init__(self, Node expr, mtypes.Type typ):
        self.expr = expr
        self.type = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_cast_expr(self)


class SuperExpr(Node):
    """Expression super().name"""
    str name
    TypeInfo info # Type that contains this super expression
    
    void __init__(self, str name):
        self.name = name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_super_expr(self)


class FuncExpr(FuncItem):
    """Lambda expression"""
    
    Node expr(self):
        """Return the expression (the body) of the lambda."""
        ret = (ReturnStmt)self.body.body[0]
        return ret.expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_func_expr(self)


class ListExpr(Node):
    """List literal expression [...] or <type> [...]"""
    Node[] items 
    mtypes.Type type # None if implicit type
    
    void __init__(self, Node[] items, mtypes.Type typ=None):
        self.items = items
        self.type = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_list_expr(self)


class DictExpr(Node):
    """Dictionary literal expression {key:value, ...} or <kt, vt> {...}."""
    list<tuple<Node, Node>> items
    mtypes.Type key_type    # None if implicit type
    mtypes.Type value_type  # None if implicit type
    
    void __init__(self, list<tuple<Node, Node>> items):
        self.items = items
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_dict_expr(self)


class TupleExpr(Node):
    """Tuple literal expression (..., ...)"""
    Node[] items
    mtypes.Type[] types
    
    void __init__(self, Node[] items, mtypes.Type[] types=None):
        self.items = items
        self.types = types
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_tuple_expr(self)


class SetExpr(Node):
    """Set literal expression {value, ...}."""
    Node[] items
    
    void __init__(self, Node[] items):
        self.items = items
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_set_expr(self)


class GeneratorExpr(Node):
    """Generator expression ... for ... in ... [ if ... ]."""
    Node left_expr
    Node right_expr
    Node condition   # May be None
    NameExpr[] index
    mtypes.Type[] types
    
    void __init__(self, Node left_expr, NameExpr[] index,
                  mtypes.Type[] types, Node right_expr, Node condition):
        self.left_expr = left_expr
        self.right_expr = right_expr
        self.condition = condition
        self.index = index
        self.types = types
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_generator_expr(self)


class ListComprehension(Node):
    """List comprehension (e.g. [x + 1 for x in a])"""
    GeneratorExpr generator
    
    void __init__(self, GeneratorExpr generator):
        self.generator = generator
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_list_comprehension(self)


class ConditionalExpr(Node):
    """Conditional expression (e.g. x if y else z)"""
    Node cond
    Node if_expr
    Node else_expr
    
    void __init__(self, Node cond, Node if_expr, Node else_expr):
        self.cond = cond
        self.if_expr = if_expr
        self.else_expr = else_expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_conditional_expr(self)


class TypeApplication(Node):
    """Type application expr<type, ...>"""
    any expr   # Node
    any types  # mtypes.Type[]
    
    def __init__(self, expr, types):
        self.expr = expr
        self.types = types
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_type_application(self)


class CoerceExpr(Node):
    """Implicit coercion expression (used only when compiling/transforming;
    inserted after type checking).
    """
    Node expr
    mtypes.Type target_type
    mtypes.Type source_type
    bool is_wrapper_class
    
    void __init__(self, Node expr, mtypes.Type target_type,
                  mtypes.Type source_type, bool is_wrapper_class):
        self.expr = expr
        self.target_type = target_type
        self.source_type = source_type
        self.is_wrapper_class = is_wrapper_class
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_coerce_expr(self)


class JavaCast(Node):
    # TODO obsolete; remove
    Node expr
    mtypes.Type target
    
    void __init__(self, Node expr, mtypes.Type target):
        self.expr = expr
        self.target = target
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_java_cast(self)


class TypeExpr(Node):
    """Expression that evaluates to a runtime representation of a type.

    This is used only for runtime type checking. This node is always generated
    only after type checking.
    """
    mtypes.Type type
    
    void __init__(self, mtypes.Type typ):
        self.type = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_type_expr(self)


class TempNode(Node):
    """Temporary dummy node used during type checking.

    This node is not present in the original program; it is just an artifact
    of the type checker implementation. It only represents an opaque node with
    some fixed type.
    """
    mtypes.Type type
    
    void __init__(self, mtypes.Type typ):
        self.type = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_temp_node(self)


class TypeInfo(Node, AccessorNode, SymNode):
    """Class representing the type structure of a single class.

    The corresponding TypeDef instance represents the parse tree of
    the class.
    """
    str _full_name     # Fully qualified name
    bool is_interface  # Is this a interface type?
    TypeDef defn       # Corresponding TypeDef
    TypeInfo base = None   # Superclass or None (not interface)
    set<TypeInfo> subtypes # Direct subclasses
    
    dict<str, Var> vars    # Member variables; also slots
    dict<str, FuncBase> methods
    
    # TypeInfos of base interfaces
    TypeInfo[] interfaces
    
    # Information related to type annotations.
    
    # Generic type variable names
    str[] type_vars
    
    # Type variable bounds (each may be None)
    # TODO implement these
    mtypes.Type[] bounds
    
    # Inherited generic types (Instance or UnboundType or None). The first base
    # is the superclass, and the rest are interfaces.
    # TODO comment may not be accurate; also why generics should be special?
    mtypes.Type[] bases
    
    void __init__(self, dict<str, Var> vars, dict<str, FuncBase> methods,
                  TypeDef defn):
        """Construct a TypeInfo."""
        self.subtypes = set()
        self.vars = {}
        self.methods = {}
        self.interfaces = []
        self.type_vars = []
        self.bounds = []
        self.bases = []
        self._full_name = defn.full_name
        self.is_interface = defn.is_interface
        self.vars = vars
        self.methods = methods
        self.defn = defn
        if defn.type_vars:
            for vd in defn.type_vars.items:
                self.type_vars.append(vd.name)
    
    str name(self):
        """Short name."""
        return self.defn.name

    str full_name(self):
        return self._full_name
    
    bool is_generic(self):
        """Is the type generic (i.e. does it have type variables)?"""
        return self.type_vars is not None and len(self.type_vars) > 0
    
    void set_type_bounds(self, mtypes.TypeVarDef[] a):
        for vd in a:
            self.bounds.append(vd.bound)
    
    # IDEA: Refactor the has* methods to be more consistent and document
    #       them.
    
    bool has_readable_member(self, str name):
        return self.has_var(name) or self.has_method(name)
    
    bool has_writable_member(self, str name):
        return self.has_var(name)
    
    bool has_var(self, str name):
        return self.get_var(name) is not None
    
    bool has_method(self, str name):
        return name in self.methods or (self.base is not None
                                        and self.base.has_method(name))
    
    Var get_var(self, str name):
        if name in self.vars:
            return self.vars[name]
        elif self.base:
            return self.base.get_var(name)
        else:
            return None
    
    AccessorNode get_var_or_getter(self, str name):
        # TODO getter
        if name in self.vars:
            return self.vars[name]
        elif self.base:
            return self.base.get_var_or_getter(name)
        else:
            return None
    
    AccessorNode get_var_or_setter(self, str name):
        # TODO setter
        if name in self.vars:
            return self.vars[name]
        elif self.base:
            return self.base.get_var_or_setter(name)
        else:
            return None
    
    FuncBase get_method(self, str name):
        if name in self.methods:
            return self.methods[name]
        elif self.base:
            # Lookup via base type.
            result = self.base.get_method(name)
            if result:
                return result
        # Finally lookup via all implemented interfaces.
        for iface in self.interfaces:
            result = iface.get_method(name)
            if result:
                return result
        # Give up; could not find it.
        return None
    
    void set_base(self, TypeInfo base):
        """Set the base class."""
        self.base = base
        base.subtypes.add(self)
    
    bool has_base(self, str full_name):
        """Return True if type has a base type with the specified name.

        This can be either via extension or via implementation.
        """
        if self.full_name() == full_name or (self.base is not None and
                                             self.base.has_base(full_name)):
            return True
        for iface in self.interfaces:
            if iface.full_name() == full_name or iface.has_base(full_name):
                return True
        return False
    
    set<TypeInfo> all_subtypes(self):
        """Return TypeInfos of all subtypes, including this type, as a set."""
        set = set([self])
        for subt in self.subtypes:
            for t in subt.all_subtypes():
                set.add(t)
        return set
    
    void add_interface(self, TypeInfo base):
        """Add a base interface."""
        self.interfaces.append(base)
    
    TypeInfo[] all_directly_implemented_interfaces(self):
        """Return a list of interfaces that the type implements.

        This includes interfaces that are directly implemented by the type and
        that are implemented by base types.
        """
        # Interfaces never implement interfaces.
        if self.is_interface:
            return []
        TypeInfo[] a = []
        for i in range(len(self.interfaces)):
            iface = self.interfaces[i]
            if iface not in a:
                a.append(iface)
            ifa = iface
            while ifa.base is not None:
                ifa = ifa.base
                if ifa not in a:
                    a.append(ifa)
        return a
    
    TypeInfo[] directly_implemented_interfaces(self):
        """Return a directly implemented interfaces.

        Omit inherited interfaces.
        """
        return self.interfaces[:]
    
    str __str__(self):
        """Return a string representation of the type.

        This includes the most important information about the type.
        """
        str[] interfaces = []
        for i in self.interfaces:
            interfaces.append(i.full_name())
        str base = None
        if self.base is not None:
            base = 'Base({})'.format(self.base.full_name())
        str iface = None
        if self.is_interface:
            iface = 'Interface'
        return dump_tagged(['Name({})'.format(self.full_name()),
                            iface,
                            base,
                            ('Interfaces', interfaces),
                            ('Vars', sorted(self.vars.keys())),
                            ('Methods', sorted(self.methods.keys()))],
                           'TypeInfo')


class SymbolTable(dict<str, SymbolTableNode>):
    str __str__(self):
        str[] a = []
        for key, value in self.items():
            # Filter out the implicit import of builtins.
            if isinstance(value, SymbolTableNode):
                if (value.full_name() != 'builtins' and
                        not value.full_name().endswith('.__name__')):
                    a.append('  ' + str(key) + ' : ' + str(value))
            else:
                a.append('  <invalid item>')
        a = sorted(a)
        a.insert(0, 'SymbolTable(')
        a[-1] += ')'
        return '\n'.join(a)


class SymbolTableNode:
    int kind      # Ldef/Gdef/Mdef/Tvar/...
    SymNode node  # Parse tree node of definition (FuncDef/Var/
                  # TypeInfo), None for Tvar
    int tvar_id   # Type variable id (for Tvars only)
    str mod_id    # Module id (e.g. "foo.bar") or None
    
    mtypes.Type type_override  # If None, fall back to type of node
    
    void __init__(self, int kind, SymNode node, str mod_id=None,
                  mtypes.Type typ=None, int tvar_id=0):
        self.kind = kind
        self.node = node
        self.type_override = typ
        self.mod_id = mod_id
        self.tvar_id = tvar_id
    
    str full_name(self):
        if self.node is not None:
            return self.node.full_name()
        else:
            return None
    
    mtypes.Type type(self):
        # IDEA: Get rid of the any type.
        any node = self.node
        if self.type_override is not None:
            return self.type_override
        elif ((isinstance(node, Var) or isinstance(node, FuncDef))
              and node.type is not None):
            return node.type.type
        else:
            return None
    
    str __str__(self):
        s = '{}/{}'.format(node_kinds[self.kind], short_type(self.node))
        if self.mod_id is not None:
            s += ' ({})'.format(self.mod_id)
        # Include declared type of variables and functions.
        if self.type() is not None:
            s += ' : {}'.format(self.type())
        return s


str clean_up(str s):
    return re.sub('.*::', '', s)
        

mtypes.FunctionLike function_type(FuncBase func):
    if func.type:
        return (mtypes.FunctionLike)func.type
    else:
        # Implicit type signature with dynamic types.
        # Overloaded functions always have a signature, so func must be an
        # ordinary function.
        fdef = (FuncDef)func        
        name = func.name()
        if name:
            name = '"{}"'.format(name)
        names = <str> []
        for arg in fdef.args:
            names.append(arg.name())
        return mtypes.Callable(<mtypes.Type> [mtypes.Any()] * len(fdef.args),
                               fdef.arg_kinds,
                               names,
                               mtypes.Any(),
                               False,
                               name)


mtypes.FunctionLike method_type(FuncBase func):
    """Return the signature of a method (omit self)."""
    t = function_type(func)
    if isinstance(t, mtypes.Callable):
        return method_callable((mtypes.Callable)t)
    else:
        o = (mtypes.Overloaded)t
        mtypes.Callable[] it = []
        for c in o.items():
            it.append(method_callable(c))
        return mtypes.Overloaded(it)


mtypes.Callable method_callable(mtypes.Callable c):
    return mtypes.Callable(c.arg_types[1:],
                           c.arg_kinds[1:],
                           c.arg_names[1:],
                           c.ret_type,
                           c.is_type_obj(),
                           c.name,
                           c.variables,
                           c.bound_vars)
