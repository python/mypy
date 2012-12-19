from output import TypeOutputVisitor
from nodes import Node, VarDef, TypeDef, FuncDef, NodeVisitor, MypyFile
from mtypes import Void, TypeStrVisitor, Callable, Instance
from maptypevar import num_slots
from transutil import tvar_arg_name


class PrettyPrintVisitor(NodeVisitor):
    """Class for converting transformed parse trees into formatted source code.

    Use default formatting (i.e. omit original formatting).
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
        self.string('def ')
        self.string(fdef.name())
        self.string('(')
        ftyp = (Callable)fdef.typ.typ
        for i in range(len(fdef.args)):
            a = fdef.args[i]
            self.string(a.name())
            self.string(' as ')
            if i < len(ftyp.arg_types):
                self.typ(ftyp.arg_types[i])
            else:
                self.string('xxx')
            if i < len(fdef.args) - 1:
                self.string(', ')
        self.string(')')
        if not isinstance(ftyp.ret_type, Void):
            self.string(' as ')
            self.typ(ftyp.ret_type)
        self.string(':\n')
        fdef.body.accept(self)
        self.dedent()
    
    void visit_var_def(self, VarDef vdef):
        if vdef.items[0][0].name() != '__name__':
            self.string(str(vdef.items[0][1]))
            self.string(' ')
            self.string(vdef.items[0][0].name())
            self.string('\n')
    
    #
    # Statements
    #

    def visit_block(self, b):
        str(':\n')
        for s in b.body:
            s.accept(self)

    def visit_pass_stmt(self, o):
        self.string('pass\n')
    
    def visit_return_stmt(self, o):
        self.string('return ')
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
    
    def visit_name_expr(self, o):
        self.string(o.name)
    
    def visit_coerce_expr(self, o):
        # Coercions are always generated during trasnformation so they do not
        # have a representation. Thus always use automatic formatting.
        last = self.last_output_char()
        if last in (',', '=') or last.isalnum():
            self.string(' ')
        if self.is_pretty:
            self.string('{')
            self.omit_next_space = True
            self.compact_type(o.target_type)
            self.string(' <= ')
            self.omit_next_space = True
            self.compact_type(o.source_type)
            self.string(' | ')
            self.omit_next_space = True
            self.node(o.expr)
            self.string('}')
        else:
            self.string('__Cast(')
            self.omit_next_space = True
            self.compact_type(o.target_type)
            self.string(', ')
            self.omit_next_space = True
            self.compact_type(o.source_type)
            self.string(', ')
            self.omit_next_space = True
            self.node(o.expr)
            self.string(')')
    
    def visit_type_expr(self, o):
        # Type expressions are only generated during transformation, so we must
        # use automatic formatting.
        if self.is_pretty:
            self.string('<')
        self.compact_type(o.typ)
        if self.is_pretty:
            self.string('>')
    
    def visit_index_expr(self, o):
        self.node(o.base)
        self.string('[')
        self.node(o.index)
        self.string(']')
    
    def visit_int_expr(self, o):
        self.string(str(o.value))
    
    def visit_super_expr(self, o):
        self.string('super().')
        self.string(o.name)
    
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
        """Pretty-print a type using original formatting."""
        if t:
            v = TypePrettyPrintVisitor()
            t.accept(v)
            self.string(v.output())
    
    def compact_type(self, t):
        """Pretty-print a type using automatic formatting."""
        if t:
            self.string(t.accept(PrettyTypeStrVisitor(self.is_pretty)))


class TypePrettyPrintVisitor(TypeOutputVisitor):
    """Pretty-print types."""
    
    def visit_any(self, t):
        self.string('any')
    
    def visit_instance(self, t):
        self.string(t.typ.name())


class PrettyTypeStrVisitor(TypeStrVisitor):
    """Translate a type to source code, with or without pretty printing.

    Always use automatic formatting.
    """
    # Pretty formatting is designed to be human-readable, while the default
    # formatting is suitable for evaluation.
    any is_pretty
    
    def __init__(self, is_pretty):
        self.is_pretty = is_pretty
        super().__init__()
    
    def visit_instance(self, t):
        if t.args == [] or self.is_pretty:
            return super().visit_instance(t)
        else:
            # Generate a type constructor for a generic instance type.
            a = []
            for at in t.args:
                a.append(at.accept(self))
            return '__Gen({}, [{}])'.format(t.typ.full_name, ', '.join(a))
    
    def visit_type_var(self, t):
        # FIX __tv vs. self.__tv?
        return tvar_arg_name(t.id)
    
    def visit_runtime_type_var(self, t):
        v = PrettyPrintVisitor()
        t.node.accept(v)
        return v.output()
    
    def visit_any(self, t):
        if self.is_pretty:
            return 'dyn'
        else:
            return '__Dyn'
