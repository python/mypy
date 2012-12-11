from parse import none
from mtypes import (
    Any, Instance, Void, TypeVar, TupleType, Callable, UnboundType
)
from nodes import IfStmt, ForStmt, WhileStmt, WithStmt, TryStmt
from nodes import function_type
from output import OutputVisitor
from typerepr import ListTypeRepr


# Names present in mypy but not in Python. Imports of these names are removed
# during translation. These are generally type names, so references to these
# generally appear in declarations, which are erased during translation.
#
# TODO for many of these a corresponding alternative exists in Python; if
#      these names are used in a non-erased context (e.g. isinstance test or
#      overloaded method signature), we should change the reference to the
#      Python alternative
removed_names = {'re': ['Pattern', 'Match']}


class PythonGenerator(OutputVisitor):
    """Python backend.

    Translate semantically analyzed parse trees to Python.  Reuse most
    of the generation logic from the mypy pretty printer implemented
    in OutputVisitor.
    """

    def __init__(self, pyversion=3):
        super().__init__()
        self.pyversion = pyversion
    
    def visit_import_from(self, o):
        if o.id in removed_names:
            r = o.repr
            
            # Filter out any names not defined in Python from a
            # from ... import statement.
            
            toks = []
            comma = none
            for i in range(len(o.names)):
                if o.names[i][0] not in removed_names[o.id]:
                    toks.append(comma)
                    toks.extend(r.names[i][0])
                    comma = r.names[i][1]
            
            # If everything was filtered out, omit the statement.
            if toks != []:
                # Output the filtered statement.
                self.token(r.from_tok)
                self.tokens(r.components)
                self.token(r.import_tok)
                self.token(r.lparen)
                self.tokens(toks)
                self.token(r.rparen)
                self.token(r.br)
        else:
            super().visit_import_from(o)
    
    def visit_func_def(self, o, name_override=None):
        r = o.repr
        
        if r.def_tok and r.def_tok.string:
            self.token(r.def_tok)
        else:
            self.string(self.get_pre_whitespace(o.typ.typ.ret_type) + 'def')
        
        if name_override is None:
            self.token(r.name)
        else:
            self.string(' ' + name_override)
        self.function_header(o, r.args, o.arg_kinds, None, True, True)
        if not o.body.body:
            self.string(': pass' + '\n')
        else:
            self.node(o.body)
    
    def get_pre_whitespace(self, t):
        """Return whitespace before the first token of a type."""
        if isinstance(t, Any):
            return t.repr.any_tok.pre
        elif isinstance(t, Instance):
            if isinstance(t.repr, ListTypeRepr):
                return self.get_pre_whitespace(t.args[0])
            else:
                return t.repr.components[0].pre
        elif isinstance(t, Void):
            return t.repr.void.pre
        elif isinstance(t, TypeVar):
            return t.repr.name.pre
        elif isinstance(t, TupleType):
            return t.repr.components[0].pre
        elif isinstance(t, Callable):
            return t.repr.func.pre
        else:
            raise RuntimeError('Unsupported type {}'.format(t))
    
    def visit_var_def(self, o):
        r = o.repr
        if r:
            self.string(self.get_pre_whitespace(o.items[0][1]))
            self.omit_next_space = True
            for v, t in o.items:
                self.node(v)
            if o.init:
                self.token(r.assign)
                self.node(o.init)
            else:
                self.string(' = {}'.format(', '.join(['None'] * len(o.items))))
            self.token(r.br)
    
    def visit_cast_expr(self, o):
        self.string(o.repr.lparen.pre)
        self.node(o.expr)

    def visit_type_application(self, o):
        self.node(o.expr)
    
    def visit_for_stmt(self, o):
        r = o.repr
        self.token(r.for_tok)
        for i in range(len(o.index)):
            self.node(o.index[i])
            self.token(r.commas[i])
        self.token(r.in_tok)
        self.node(o.expr)
        
        self.node(o.body)
        if o.else_body:
            self.token(r.else_tok)
            self.node(o.else_body)
    
    def visit_type_def(self, o):
        r = o.repr
        self.string(r.class_tok.pre)
        self.string('class')
        self.token(r.name)
        self.token(r.lparen)
        for i in range(len(o.base_types)):
            self.string(self.erased_type(o.base_types[i]))
            if i < len(r.commas):
                self.token(r.commas[i])
        self.token(r.rparen)
        if not r.lparen.string and self.pyversion == 2:
            self.string('(object)')
        self.node(o.defs)
    
    def erased_type(self, t):
        if isinstance(t, Instance) or isinstance(t, UnboundType):
            if isinstance(t.repr, ListTypeRepr):
                return '__builtins__.list'
            else:
                a = []
                if t.repr:
                    for tok in t.repr.components:
                        a.append(tok.rep())
                return ''.join(a)
        elif isinstance(t, TupleType):
            return 'tuple' # FIX: aliasing?
        elif isinstance(t, TypeVar):
            return 'object' # Type variables are erased to "object"
        else:
            raise RuntimeError('Cannot translate type {}'.format(t))
    
    def visit_func_expr(self, o):
        r = o.repr
        self.token(r.lambda_tok)
        self.function_header(o, r.args, o.arg_kinds, None, True, False)
        self.token(r.colon)
        self.node(o.body.body[0].expr)
    
    def visit_overloaded_func_def(self, o):
        """Translate overloaded function definition.

        Overloaded functions are transformed into a single Python function that
        performs argument type checks and length checks to dispatch to the
        right implementation.
        """
        indent = self.indent * ' '
        first = o.items[0]
        r = first.repr
        if r.def_tok and r.def_tok.string:
            self.token(r.def_tok)
        else:
            # TODO omit (some) comments; now comments may be duplicated
            self.string(self.get_pre_whitespace(first.typ.typ.ret_type) +
                        'def')
        self.string(' {}('.format(first.name()))
        self.extra_indent += 4
        fixed_args, is_more = self.get_overload_args(o)
        self.string(', '.join(fixed_args))
        rest_args = None
        if is_more:
            rest_args = self.make_unique('args', fixed_args)
            if len(fixed_args) > 0:
                self.string(', ')
            self.string('*{}'.format(rest_args))
        self.string('):\n' + indent)
        n = 1
        for f in o.items:
            self.visit_func_def(f, '{}{}'.format(f.name(), n))
            n += 1
        self.string('\n')
        
        n = 1
        for fi in o.items:
            c = self.make_overload_check(fi, fixed_args, rest_args)
            self.string(indent)
            if n == 1:
                self.string('if ')
            else:
                self.string('elif ')
            self.string(c)
            self.string(':' + '\n' + indent)
            self.string('    return {}'.format(self.make_overload_call(
                fi, n, fixed_args, rest_args)) + '\n')
            n += 1
        self.string(indent + 'else:' + '\n')
        self.string(indent + '    raise TypeError("Invalid argument types")')
        self.extra_indent -= 4
        last_stmt = o.items[-1].body.body[-1]
        self.token(self.find_break_after_statement(last_stmt))
    
    def find_break_after_statement(self, s):
        if isinstance(s, IfStmt):
            blocks = s.body + [s.else_body]
        elif isinstance(s, ForStmt) or isinstance(s, WhileStmt):
            blocks = [s.body, s.else_body]
        elif isinstance(s, WithStmt):
            blocks = [s.body]
        elif isinstance(s, TryStmt):
            blocks = s.handlers + [s.else_body, s.finally_body]
        else:
            return s.repr.br
        for b in reversed(blocks):
            if b:
                return self.find_break_after_statement(b.body[-1])
        raise RuntimeError('Could not find break after statement')
    
    def make_unique(self, n, others):
        if n in others:
            return self.make_unique('_' + n, others)
        else:
            return n
    
    def get_overload_args(self, o):
        fixed = []
        min_fixed = 100000
        max_fixed = 0
        for f in o.items:
            if len(f.args) > len(fixed):
                for v in f.args[len(fixed):]:
                    fixed.append(v.name())
            min_fixed = min(min_fixed, f.min_args)
            max_fixed = max(max_fixed, len(f.args))
        return fixed[:min_fixed], max_fixed > min_fixed
    
    def make_overload_check(self, f, fixed_args, rest_args):
        a = []
        i = 0
        if rest_args:
            a.append(self.make_argument_count_check(f, len(fixed_args),
                                                    rest_args))
        for t in function_type(f).arg_types:
            if not isinstance(t, Any) and (t.repr or
                                           isinstance(t, Callable)):
                a.append(self.make_argument_check(
                    self.argument_ref(i, fixed_args, rest_args), t))
            i += 1
        if len(a) > 0:
            return ' and '.join(a)
        else:
            return 'True'
    
    def make_argument_count_check(self, f, num_fixed, rest_args):
        return 'len({}) == {}'.format(rest_args, f.min_args - num_fixed)
    
    def make_argument_check(self, name, typ):
        if isinstance(typ, Callable):
            return 'callable({})'.format(name)
        else:
            cond = 'isinstance({}, {})'.format(name, self.erased_type(typ))
            return cond.replace('  ', ' ')
    
    def make_overload_call(self, f, n, fixed_args, rest_args):
        a = []
        for i in range(len(f.args)):
            a.append(self.argument_ref(i, fixed_args, rest_args))
        return '{}{}({})'.format(f.name(), n, ', '.join(a))
    
    def argument_ref(self, i, fixed_args, rest_args):
        if i < len(fixed_args):
            return fixed_args[i]
        else:
            return '{}[{}]'.format(rest_args, i - len(fixed_args))
    
    def visit_list_expr(self, o):
        r = o.repr
        self.token(r.lbracket)
        self.comma_list(o.items, r.commas)
        self.token(r.rbracket)
    
    def visit_dict_expr(self, o):
        r = o.repr
        self.token(r.lbrace)
        i = 0
        for k, v in o.items:
            self.node(k)
            self.token(r.colons[i])
            self.node(v)
            if i < len(r.commas):
                self.token(r.commas[i])
            i += 1
        self.token(r.rbrace)

    def visit_super_expr(self, o):
        if self.pyversion > 2:
            super().visit_super_expr(o)
        else:
            r = o.repr
            self.tokens([r.super_tok, r.lparen])
            # TODO do not hard code 'self'
            self.string('%s, self' % o.info.name())
            self.tokens([r.rparen, r.dot, r.name])
            
