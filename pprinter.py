from output import OutputVisitor, TypeOutputVisitor
from nodes import Node
from mtypes import Void, TypeStrVisitor
from maptypevar2 import num_slots
from transutil import tvar_arg_name


class PrettyPrintVisitor(OutputVisitor):
    """Class for converting transformed parse trees into source code. Pretty print
    nodes created in transformation using default formatting, as these nodes may
    not have representations.
    """
    any is_pretty
    list<tuple<int, int>> line_assoc = []
    dict<Node, tuple<int, int>> node_line_map
    
    
    def __init__(self, is_pretty=True, node_line_map={}):
        self.is_pretty = is_pretty
        self.node_line_map = node_line_map
        super().__init__()
    
    
    def line_map(self):
        return sorted(self.line_assoc, key=lambda x: x[1])
    
    
    # Definitions
    # -----------
    
    
    def visit_type_def(self, tdef):
        if tdef.repr is not None:
            super().visit_type_def(tdef)
            self.add_line_mapping(tdef.repr.endBr)
        else:
            # The type does not have an explicit representation: it must have been
            # created during the transformation.
            
            # FIX implements etc.
            if self.last_output_char() != '\n':
                self.string('\n')
            start = self.line()
            if tdef.isPrivate:
                self.string('private ')
            self.string('class ')
            self.string(tdef.name)
            if tdef.base is not None:
                self.string(' is ')
                self.node(tdef.base)
            self.string('\n')
            for d in tdef.defs:
                d.accept(self)
            self.add_node_line_mapping(tdef, start, self.line())
            self.string('end' + '\n')
    
    def visit_func_def(self, fdef):
        if fdef.repr is not None:
            self.add_line_mapping(fdef.repr.def_tok)
        if fdef.repr is not None or (fdef.is_constructor() and num_slots(fdef.info) == 0):
            super().visit_func_def(fdef)
        else:
            # The function does not have an explicit representation. It must have
            # been created during the transformation.
            
            # FIX private, varargs, default args etc.
            start = self.line()
            self.string('  def ')
            self.string(fdef.name)
            if not fdef.isAccessor():
                self.string('(')
                for i in range(len(fdef.args)):
                    a = fdef.args[i]
                    self.string(a.name)
                    self.string(' as ')
                    self.omit_next_space = True
                    self.typ(fdef.typ.typ.arg_types[i])
                    if i < len(fdef.args) - 1:
                        self.string(', ')
                self.string(')')
                if not isinstance(fdef.typ.typ.ret_type, Void):
                    self.string(' as ')
                    self.omit_next_space = True
                    self.typ(fdef.typ.typ.ret_type)
            else:
                if fdef.isSetter:
                    self.string(' = ')
                    self.string(fdef.args[0].name)
                self.string(' as ')
                self.omit_next_space = True
                self.typ(fdef.typ.typ)
            self.string('\n')
            self.nodes(fdef.body)
            self.add_node_line_mapping(fdef, start, self.line())
            self.string('  end' + '\n')
    
    def visit_var_def(self, vdef):
        if vdef.repr is not None:
            super().visit_var_def(vdef)
        else:
            # No explicit representation. It node was created during transformation.
            self.string('  ')       
            if vdef.isPrivate:
                self.string('private ')
            if vdef.isConst:
                self.string('const ')
            else:
                self.string('var ')
            self.string(vdef.names[0].name)
            self.string(' as ')
            self.string(str(vdef.typ.typ))
            self.string('\n')
    
    
    # Statements
    # ----------
    
    
    def visit_return_stmt(self, o):
        if o.repr is not None:
            super().visit_return_stmt(o)
        else:
            # No explicit representation. Use automatic formatting.
            self.string('    return ')
            self.omit_next_space = True
            self.node(o.expr)
            self.string('\n')
    
    def visit_expression_stmt(self, o):
        if o.repr is not None:
            super().visit_expression_stmt(o)
        else:
            # No explicit representation. Use automatic formatting.
            self.string('    ')
            self.omit_next_space = True
            self.node(o.expr)
            self.string('\n')
    
    def visit_assignment_stmt(self, o):
        if o.repr is not None:
            super().visit_assignment_stmt(o)
        else:
            # No explicit representation. Use automatic formatting.
            self.string('    ')
            self.omit_next_space = True
            self.node(o.lvalues[0]) # FIX multiple lvalues
            self.string(' = ')
            self.node(o.rvalue)
            self.string('\n')      
    
    
    # Expressions
    # -----------
    
    
    def visit_call_expr(self, o):
        if o.repr is not None:
            super().visit_call_expr(o)
        else:
            # No explicit representation. Use automatic formatting.
            self.node(o.callee)
            self.string('(')
            self.omit_next_space = True
            for i in range(len(o.args)):
                self.node(o.args[i])
                if i < len(o.args) - 1:
                    self.string(', ')
            self.string(')')
    
    def visit_member_expr(self, o):
        if o.repr is not None:
            super().visit_member_expr(o)
        else:
            # No explicit representation. Use automatic formatting.
            self.node(o.expr)
            self.string('.' + o.name)
    
    def visit_name_expr(self, o):
        if o.repr is not None:
            super().visit_name_expr(o)
        else:
            # No explicit representation. Use automatic formatting.
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
        if o.repr is not None:
            super().visit_index_expr(o)
        else:
            # No explicit representation. Use automatic formatting.
            self.node(o.base)
            self.string('[')
            self.omit_next_space = True
            self.node(o.index)
            self.string(']')
    
    def visit_int_expr(self, o):
        # IDEA: Try to use explicit representation?
        self.string(' ')
        self.string(str(o.value))
    
    def visit_super_expr(self, o):
        if o.repr is not None:
            super().visit_super_expr(o)
        else:
            self.string('super.')
            self.string(o.name)
    
    
    # Helpers
    # -------
    
    
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
    
    def add_line_mapping(self, token):
        """Record a line mapping between the current output line and the line of
        the token.
        """
        self.line_assoc.append((token.line + token.string.count('\n'), self.line()))
    
    def add_node_line_mapping(self, node, start, stop):
        if self.node_line_map.has_key(node):
            start2, stop2 = self.node_line_map[node]
            self.line_assoc.append((start2, start))
            self.line_assoc.append((stop2, stop))


class TypePrettyPrintVisitor(TypeOutputVisitor):
    """Visitor for pretty-printing types using original formatting whenever
    possible.
    """
    def visit_any(self, t):
        # Any types do not always have explicit formatting.
        if t.repr is None:
            self.string(' dynamic')
        else:
            super().visit_any(t)


class PrettyTypeStrVisitor(TypeStrVisitor):
    """Translate a type to source code, with or without pretty printing. Always
    use automatic formatting.
    """
    # Pretty formatting is designed to be human-readable, while the default
    # formatting is suitable for evaluation (it's valid Alore).
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
