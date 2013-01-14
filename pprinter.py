from output import TypeOutputVisitor
from nodes import (
    Node, VarDef, TypeDef, FuncDef, MypyFile, CoerceExpr, TypeExpr
)
from visitor import NodeVisitor
from mtypes import Void, TypeVisitor, Callable, Instance, Typ
from maptypevar import num_slots
from transutil import tvar_arg_name
import coerce


class PrettyPrintVisitor(NodeVisitor):
    """Convert transformed parse trees into formatted source code.

    Use automatic formatting (i.e. omit original formatting).
    """

    void __init__(self):
        super().__init__()
        self.result = <str> []
        self.indent = 0

    str output(self):
        return ''.join(self.result)
    
    #
    # Definitions
    #

    void visit_mypy_file(self, MypyFile file):
        for d in file.defs:
            d.accept(self)
    
    void visit_type_def(self, TypeDef tdef):
        self.string('class ')
        self.string(tdef.name)
        if tdef.base_types:
            b = <str> []
            for bt in tdef.base_types:
                if ((Instance)bt).typ.full_name() != 'builtins.object':
                    b.append(str(bt))
            if b:
                self.string('({})'.format(', '.join(b)))
        self.string(':\n')
        for d in tdef.defs.body:
            d.accept(self)
        self.dedent()
    
    void visit_func_def(self, FuncDef fdef):
        # FIX varargs, default args, keyword args etc.
        ftyp = (Callable)fdef.typ.typ
        self.typ(ftyp.ret_type)
        self.string(' ')
        self.string(fdef.name())
        self.string('(')
        for i in range(len(fdef.args)):
            a = fdef.args[i]
            if i < len(ftyp.arg_types):
                self.typ(ftyp.arg_types[i])
                self.string(' ')
            else:
                self.string('xxx ')
            self.string(a.name())
            if i < len(fdef.args) - 1:
                self.string(', ')
        self.string(')')
        fdef.body.accept(self)
    
    void visit_var_def(self, VarDef vdef):
        if vdef.items[0][0].name() != '__name__':
            self.typ(vdef.items[0][1])
            self.string(' ')
            self.string(vdef.items[0][0].name())
            if vdef.init:
                self.string(' = ')
                self.node(vdef.init)
            self.string('\n')
    
    #
    # Statements
    #

    def visit_block(self, b):
        self.string(':\n')
        for s in b.body:
            s.accept(self)
        self.dedent()

    def visit_pass_stmt(self, o):
        self.string('pass\n')
    
    def visit_return_stmt(self, o):
        self.string('return ')
        if o.expr:
            self.node(o.expr)
        self.string('\n')
    
    def visit_expression_stmt(self, o):
        self.node(o.expr)
        self.string('\n')
    
    def visit_assignment_stmt(self, o):
        self.node(o.lvalues[0]) # FIX multiple lvalues
        self.string(' = ')
        self.node(o.rvalue)
        self.string('\n')

    def visit_if_stmt(self, o):
        self.string('if ')
        self.node(o.expr[0])
        self.node(o.body[0])
        for e, b in zip(o.expr[1:], o.body[1:]):
            self.string('elif ')
            self.node(e)
            self.node(b)
        if o.else_body:
            self.string('else')
            self.node(o.else_body)

    def visit_while_stmt(self, o):
        self.string('while ')
        self.node(o.expr)
        self.node(o.body)
        if o.else_body:
            self.string('else')
            self.node(o.else_body)
    
    #
    # Expressions
    #
    
    def visit_call_expr(self, o):
        self.node(o.callee)
        self.string('(')
        self.omit_next_space = True
        for i in range(len(o.args)):
            self.node(o.args[i])
            if i < len(o.args) - 1:
                self.string(', ')
        self.string(')')
    
    def visit_member_expr(self, o):
        self.node(o.expr)
        self.string('.' + o.name)
        if o.direct:
            self.string('!')
    
    def visit_name_expr(self, o):
        self.string(o.name)
    
    void visit_coerce_expr(self, CoerceExpr o):
        self.string('{')
        self.full_type(o.target_type)
        if coerce.is_special_primitive(o.source_type):
            self.string(' <= ')
            self.typ(o.source_type)
        self.string(' ')
        self.node(o.expr)
        self.string('}')
    
    void visit_type_expr(self, TypeExpr o):
        # Type expressions are only generated during transformation, so we must
        # use automatic formatting.
        self.string('<')
        self.full_type(o.typ)
        self.string('>')
    
    def visit_index_expr(self, o):
        self.node(o.base)
        self.string('[')
        self.node(o.index)
        self.string(']')
    
    def visit_int_expr(self, o):
        self.string(str(o.value))
    
    def visit_str_expr(self, o):
        self.string(repr(o.value))

    def visit_op_expr(self, o):
        self.node(o.left)
        self.string(' %s ' % o.op)
        self.node(o.right)

    def visit_unary_expr(self, o):
        self.string(o.op)
        if o.op == 'not':
            self.string(' ')
        self.node(o.expr)

    def visit_paren_expr(self, o):
        self.string('(')
        self.node(o.expr)
        self.string(')')
    
    def visit_super_expr(self, o):
        self.string('super().')
        self.string(o.name)

    def visit_cast_expr(self, o):
        self.string('(')
        self.typ(o.typ)
        self.string(')')
        self.node(o.expr)

    def visit_type_application(self, o):
        # Type arguments are erased in transformation.
        self.node(o.expr)
    
    #
    # Helpers
    #

    void string(self, str s):
        if not s:
            return
        if self.last_output_char() == '\n':
            self.result.append(' ' * self.indent)
        self.result.append(s)
        if s.endswith(':\n'):
            self.indent += 4

    void dedent(self):
        self.indent -= 4

    void node(self, Node n):
        n.accept(self)

    str last_output_char(self):
        if self.result:
            return self.result[-1][-1]
        return ''
    
    def typ(self, t):
        """Pretty-print a type with erased type arguments."""
        if t:
            v = TypeErasedPrettyPrintVisitor()
            self.string(t.accept(v))
    
    def full_type(self, t):
        """Pretty-print a type, includingn type arguments."""
        if t:
            v = TypePrettyPrintVisitor()
            self.string(t.accept(v))


class TypeErasedPrettyPrintVisitor(TypeVisitor<str>):
    """Pretty-print types.

    Omit type variables (e.g. C instead of C<int>).

    Note that the translation does not preserve all information about the
    types, but this is fine since this is only used in test case output.
    """
    
    def visit_any(self, t):
        return 'any'
    
    def visit_void(self, t):
        return 'void'
    
    def visit_instance(self, t):
        return t.typ.name()
    
    def visit_type_var(self, t):
        return 'any*'
    
    def visit_runtime_type_var(self, t):
        v = PrettyPrintVisitor()
        t.node.accept(v)
        return v.output()


class TypePrettyPrintVisitor(TypeVisitor<str>):
    """Pretty-print types.

    Include type variables.
    
    Note that the translation does not preserve all information about the
    types, but this is fine since this is only used in test case output.
    """
    
    def visit_any(self, t):
        return 'any'
    
    def visit_void(self, t):
        return 'void'
    
    def visit_instance(self, t):
        s = t.typ.name()
        if t.args:
            argstr = ', '.join([a.accept(self) for a in t.args])
            s += '<%s>' % argstr
        return s
    
    def visit_type_var(self, t):
        return 'any*'
    
    def visit_runtime_type_var(self, t):
        v = PrettyPrintVisitor()
        t.node.accept(v)
        return v.output()
