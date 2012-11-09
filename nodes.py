from lex import Token
from types import TypeVars, Typ
from strconv import StrConv
from visitor import NodeVisitor
from symtable import SymbolTable
from typeinfo import TypeInfo


# Variable kind constants
LDEF = 0
GDEF = 1
MDEF = 2
MODULE_REF = 3


# Supertype for node types that can be stored in a symbol table.
# TODO better name
interface AccessorNode: pass


class Node:
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
    
    T accept<T>(self, NodeVisitor<T> visitor):
        raise RuntimeError('Not implemented')


class MypyFile(Node, AccessorNode):
    str name           # Module name ('__main__' for initial file)
    str full_name          # Qualified module name
    str path           # Path to the file (nil if not known)
    list<Node> defs   # Global definitions and statements
    bool is_bom       # Is there a UTF-8 BOM at the start?
    SymbolTable names
    
    void __init__(self, list<Node> defs, bool is_bom=False):
        self.defs = defs
        self.line = 1  # Dummy line number
        self.is_bom = is_bom
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_mypy_file(self)


class Import(Node):
    list<tuple<str, str>> ids     # (module id, as id)
    
    void __init__(self, list<tuple<str, str>> ids):
        self.ids = ids
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_import(self)


class ImportFrom(Node):
    str id
    list<tuple<str, str>> names  
    
    void __init__(self, str id, list<tuple<str, str>> names):
        self.id = id
        self.names = names
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_import_from(self)


class ImportAll(Node):
    str id
    
    void __init__(self, str id):
        self.id = id
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_import_all(self)


# A logical node representing all the overload variants of an overloaded
# function. This node has no explicit representation in the source program.
# Overloaded variants must be consecutive in the source file.
class OverloadedFuncDef(FuncBase):
    list<FuncDef> items
    str full_name
    
    void __init__(self, list<FuncDef> items):
        self.items = items
        self.set_line(items[0].line)
    
    str name(self):
        return self.items[1].name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_overloaded_func_def(self)


class FuncBase(Node, AccessorNode):
    Annotation typ   # Type signature (Callable or Overloaded)
    TypeInfo info     # If method, reference to TypeInfo
    str name


class FuncItem(FuncBase):
    # Fixed argument names
    list<Var> args = []
    # Initialization expessions for fixed args; nil if no initialiser
    list<AssignmentStmt> init = []
    int min_args           # Minimum number of arguments
    int max_pos            # Maximum number of positional arguments, -1 if
    # no explicit limit
    Var var_arg            # If not nil, *x arg
    Var dict_var_arg        # If not nil, **x arg
    Block body
    bool is_implicit    # Implicit dynamic types?
    bool is_overload    # Is this an overload variant of function with
    # more than one overload variant?
    
    void __init__(self, list<Var> args, list<Node> init, Var var_arg, Var dict_var_arg, int max_pos, Block body, Annotation typ=None):
        self.args = args
        self.var_arg = var_arg
        self.dict_var_arg = dict_var_arg
        self.max_pos = max_pos
        self.body = body
        self.typ = typ
        self.is_implicit = typ is None
        self.is_overload = False
        
        list<AssignmentStmt> i2 = []
        self.min_args = 0
        for i in range(len(init)):
            if init[i] is not None:
                rvalue = init[i]
                lvalue = NameExpr(args[i].name).set_line(rvalue.line)
                assign = (AssignmentStmt)AssignmentStmt([lvalue], rvalue).set_line(rvalue.line)
                i2.append(assign)
            else:
                i2.append(None)
                if i < self.max_fixed_argc():
                    self.min_args = i + 1
        self.init = i2
    
    int max_fixed_argc(self):
        return len(self.args)
    
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
    
    list<Node> init_expressions(self):
        list<Node> res = []
        for i in self.init:
            if i is not None:
                res.append(i.rvalue)
            else:
                res.append(None)
        return res


class FuncDef(FuncItem):
    str full_name      # Name with module prefix
    
    void __init__(self, str name, list<Var> args, list<Node> init, Var var_arg, Var dict_var_arg, int max_pos, Block body, Annotation typ=None):
        super().__init__(args, init, var_arg, dict_var_arg, max_pos, body, typ)
        self.name = name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_func_def(self)
    
    bool is_constructor(self):
        return self.info is not None and self.name == '__init__'
    
    str get_name(self):
        return self.name


class Decorator(Node):
    Node func       # FuncDef or Decorator
    Node decorator
    
    void __init__(self, Node func, Node decorator):
        self.func = func
        self.decorator = decorator
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_decorator(self)


class Var(Node, AccessorNode):
    str name          # Name without module prefix
    str full_name      # Name with module prefix
    bool is_init    # Is is initialized?
    TypeInfo info     # Defining class (for member variables)
    Annotation typ   # Declared type, or nil if none
    bool is_self    # Is this the first argument to an ordinary method
    # (usually "self")?
    
    void __init__(self, str name):
        self.name = name
        self.is_init = False
        self.is_self = False
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_var(self)


class TypeDef(Node):
    str name        # Name of the class without module prefix
    str full_name    # Fully qualified name of the class
    Block defs
    TypeVars type_vars
    # Inherited types (Instance or UnboundType).
    list<Typ> base_types
    TypeInfo info    # Related TypeInfo
    bool is_interface
    
    void __init__(self, str name, Block defs, TypeVars type_vars=None, list<Typ> base_types=[], bool is_interface=False):
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
    list<tuple<Var, Typ>> items
    int kind          # Ldef/Gdef/Mdef
    Node init         # Expression or nil
    bool is_top_level # Is the definition at the top level (not within
    # a function or a type)?
    bool is_init
    
    void __init__(self, list<tuple<Var, Typ>> items, bool is_top_level, Node init=None):
        self.items = items
        self.is_top_level = is_top_level
        self.init = init
        self.is_init = init is not None
    
    TypeInfo info(self):
        return self.items[0][0].info
    
    Node set_line(self, Token tok):
        super().set_line(tok)
        for n, t in self.items:
            n.line = self.line
        return self
    
    Node set_line(self, int tok):
        super().set_line(tok)
        for n, t in self.items:
            n.line = self.line
        return self
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_var_def(self)


class GlobalDecl(Node):
    list<str> names
    
    void __init__(self, list<str> names):
        self.names = names
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_global_decl(self)


class Block(Node):
    list<Node> body
    
    void __init__(self, list<Node> body):
        self.body = body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_block(self)


# Statements


class ExpressionStmt(Node):
    Node expr
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_expression_stmt(self)


class AssignmentStmt(Node):
    list<Node> lvalues = []
    Node rvalue
    
    void __init__(self, list<Node> lvalues, Node rvalue):
        self.lvalues = lvalues
        self.rvalue = rvalue
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_assignment_stmt(self)


class OperatorAssignmentStmt(Node):
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
    list<Var> index = [] # Var nodes
    Node expr             # Iterated expression
    Block body
    Block else_body
    list<Annotation> types
    
    void __init__(self, list<Var> index, Node expr, Block body, Block else_body, list<Annotation> types=None):
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
    Node expr   # Expression or nil
    
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
    list<Node> expr
    list<Block> body
    Block else_body
    
    void __init__(self, list<Node> expr, list<Block> body, Block else_body):
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
    Block body                 # Try body
    list<Node> types = []     # Except type expressions
    list<Var> vars = []       # Except variable names
    list<Block> handlers = [] # Except bodies
    Block else_body
    Block finally_body
    
    void __init__(self, Block body, list<Var> vars, list<Node> types, list<Block> handlers, Block else_body, Block finally_body):
        self.body = body
        self.vars = vars
        self.types = types
        self.handlers = handlers
        self.else_body = else_body
        self.finally_body = finally_body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_try_stmt(self)


class WithStmt(Node):
    list<Node> expr
    list<Var> name
    Block body
    
    void __init__(self, list<Node> expr, list<Var> name, Block body):
        self.expr = expr
        self.name = name
        self.body = body
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_with_stmt(self)


# Expressions


# Integer literal
class IntExpr(Node):
    int value
    
    void __init__(self, int value):
        self.value = value
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_int_expr(self)


# String literal
class StrExpr(Node):
    str value
    
    void __init__(self, str value):
        self.value = value
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_str_expr(self)


# Float literal
class FloatExpr(Node):
    float value
    
    void __init__(self, float value):
        self.value = value
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_float_expr(self)


# Parenthesised expression
class ParenExpr(Node):
    Node expr
    
    void __init__(self, Node expr):
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_paren_expr(self)


# Abstract base class
class RefExpr(Node):
    int kind      # Ldef/Gdef/Mdef/... (nil if not available)
    Node node     # Var, FuncDef or TypeInfo that describes this


# Name expression optionally with a ::-based qualifier (may refer to a local,
# member or global definition)
class NameExpr(RefExpr):
    str name      # Name referred to (may be qualified)
    str full_name  # Fully qualified name (or name if not global)
    TypeInfo info # TypeInfo of class surrounding expression (may be nil)
    bool is_def # Does this define a new variable as a lvalue?
    
    void __init__(self, str name):
        self.name = name
        self.is_def = False
    
    def type_node(self):
        return (TypeInfo)self.node
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_name_expr(self)


# Member access expression x.y
class MemberExpr(RefExpr):
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
    
    void __init__(self, Node expr, str name):
        self.expr = expr
        self.name = name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_member_expr(self)


# Call expression
class CallExpr(Node):
    Node callee
    list<Node> args = []
    bool is_var_arg
    list<tuple<NameExpr, Node>> keyword_args
    Node dict_var_arg
    
    void __init__(self, Node callee, list<Node> args, bool is_var_arg=False, list<tuple<NameExpr, Node>> keyword_args=[], Node dict_var_arg=None):
        self.callee = callee
        self.args = args
        self.is_var_arg = is_var_arg
        self.keyword_args = keyword_args
        self.dict_var_arg = dict_var_arg
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_call_expr(self)


# Index expression x[y]
class IndexExpr(Node):
    Node base
    Node index
    
    void __init__(self, Node base, Node index):
        self.base = base
        self.index = index
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_index_expr(self)


# Unary operation
class UnaryExpr(Node):
    str op
    Node expr
    
    void __init__(self, str op, Node expr):
        self.op = op
        self.expr = expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_unary_expr(self)


# Binary operation (other than . or [], which have specific nodes)
class OpExpr(Node):
    str op
    Node left
    Node right
    
    void __init__(self, str op, Node left, Node right):
        self.op = op
        self.left = left
        self.right = right
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_op_expr(self)


# Slice expression (e.g. "x:y", "x:", "::2" or ":"); only valid as index in
# index expressions.
class SliceExpr(Node):
    Node begin_index  # May be nil
    Node end_index    # May be nil
    Node stride      # May be nil
    
    void __init__(self, Node begin_index, Node end_index, Node stride):
        self.begin_index = begin_index
        self.end_index = end_index
        self.stride = stride
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_slice_expr(self)


class CastExpr(Node):
    Node expr
    Typ typ
    
    void __init__(self, Node expr, Typ typ):
        self.expr = expr
        self.typ = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_cast_expr(self)


class SuperExpr(Node):
    str name
    TypeInfo info # Type that contains this super expression
    
    void __init__(self, str name):
        self.name = name
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_super_expr(self)


# Anonymous function expression
class FuncExpr(FuncItem):
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_func_expr(self)


# List literal expression [...] or <type> [...]
class ListExpr(Node):
    list<Node> items = []
    Typ typ # nil if implicit type
    
    void __init__(self, list<Node> items, Typ typ=None):
        self.items = items
        self.typ = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_list_expr(self)


# Dictionary literal expression {key:value, ...} or <kt, vt> {...}.
class DictExpr(Node):
    list<tuple<Node, Node>> items
    Typ key_type    # nil if implicit type
    Typ value_type  # nil if implicit type
    
    void __init__(self, list<tuple<Node, Node>> items):
        self.items = items
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_dict_expr(self)


# Tuple literal expression (..., ...)
class TupleExpr(Node):
    list<Node> items
    list<Typ> types
    
    void __init__(self, list<Node> items, list<Typ> types=None):
        self.items = items
        self.types = types
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_tuple_expr(self)


# Set literal expression {value, ...}.
class SetExpr(Node):
    list<Node> items
    
    void __init__(self, list<Node> items):
        self.items = items
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_set_expr(self)


# Generator expression ... for ... in ... [ if ... ].
class GeneratorExpr(Node):
    Node left_expr
    Node right_expr
    Node condition   # May be nil
    list<Var> index
    list<Annotation> types
    
    void __init__(self, Node left_expr, list<Var> index, list<Annotation> types, Node right_expr, Node condition):
        self.left_expr = left_expr
        self.right_expr = right_expr
        self.condition = condition
        self.index = index
        self.types = types
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_generator_expr(self)


class ListComprehension(Node):
    GeneratorExpr generator
    
    void __init__(self, GeneratorExpr generator):
        self.generator = generator
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_list_comprehension(self)


class ConditionalExpr(Node):
    Node cond
    Node if_expr
    Node else_expr
    
    void __init__(self, Node cond, Node if_expr, Node else_expr):
        self.cond = cond
        self.if_expr = if_expr
        self.else_expr = else_expr
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_conditional_expr(self)


class Annotation(Node):
    Typ typ
    
    void __init__(self, Typ typ, int line=-1):
        self.typ = typ
        self.line = line
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_annotation(self)


class TypeApplication(Node):
    any expr   # Node
    any types  # Array<Typ>
    
    def __init__(self, expr, types):
        self.expr = expr
        self.types = types
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_type_application(self)


# Implicit coercion expression (used only when compiling/transforming;
# inserted after type checking).
class CoerceExpr(Node):
    Node expr
    Typ target_type
    Typ source_type
    bool is_wrapper_class
    
    void __init__(self, Node expr, Typ target_type, Typ source_type, bool is_wrapper_class):
        self.expr = expr
        self.target_type = target_type
        self.source_type = source_type
        self.is_wrapper_class = is_wrapper_class
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_coerce_expr(self)


class JavaCast(Node):
    Node expr
    Typ target
    
    void __init__(self, Node expr, Typ target):
        self.expr = expr
        self.target = target
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_java_cast(self)


# Expression that evaluates to a runtime representation of a type. This is
# used only for runtime type checking. This node is always generated only
# after type checking.
class TypeExpr(Node):
    Typ typ
    
    void __init__(self, Typ typ):
        self.typ = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_type_expr(self)


# This node is not present in the original program; it is just an artifact
# of the type checker implementation. It only represents an opaque node with
# some fixed type.
class TempNode(Node):
    Typ typ
    
    void __init__(self, Typ typ):
        self.typ = typ
    
    T accept<T>(self, NodeVisitor<T> visitor):
        return visitor.visit_temp_node(self)
