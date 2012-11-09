from typevisitor import TypeVisitor
import types


# Visitor for pretty-printing types into strings. Do not preserve original
# formatting.
#
# Notes:
#  - Include argument ranges for Instance types, when present.
#  - Include implicit bound type variables of callables.
#  - Represent unbound types as Foo? or Foo?<...>.
#  - Represent the nil type as Nil.
class TypeStrVisitor(TypeVisitor<str>):
    def visit_unbound_type(self, t):
        s = t.name + '?'
        if t.args != []:
            s += '<{}>'.format(self.list_str(t.args))
        return s
    
    def visit_error_type(self, t):
        return '<ERROR>'
    
    def visit_any(self, t):
        return 'any'
    
    def visit_void(self, t):
        return 'void'
    
    def visit_none_type(self, t):
        return 'None'
    
    def visit_instance(self, t):
        s = t.typ.full_name
        if t.erased:
            s += '*'
        if t.args != []:
            s += '<{}>'.format(self.list_str(t.args))
        return s
    
    def visit_type_var(self, t):
        if t.name is None:
            # Anonymous type variable type (only numeric id).
            return '`{}'.format(t.id)
        else:
            # Named type variable type.
            s = '{}`{}'.format(t.name, t.id)
            if t.is_wrapper_var == types.BOUND_VAR:
                s += '!B'
            elif t.is_wrapper_var == True:
                s += '!W'
            elif t.is_wrapper_var == types.OBJECT_VAR:
                s += '!O'
            return s
    
    def visit_callable(self, t):
        s = self.list_str(t.arg_types[:t.min_args])
        
        opt = t.arg_types[t.min_args:]
        if t.is_var_arg:
            opt = opt[:-1]
        
        for o in opt:
            if s != '':
                s += ', '
            s += str(o) + '='
        
        if t.is_var_arg:
            if s != '':
                s += ', '
            s += '*' + str(t.arg_types[-1])
        
        s = '({})'.format(s)
        
        if not isinstance(t.ret_type, types.Void):
            s += ' -> {}'.format(t.ret_type)
        
        if t.variables.items != []:
            s = '{} {}'.format(t.variables, s)
        
        if t.bound_vars != []:
            # Include implicit bound type variables.
            a = []
            for i, bt in t.bound_vars:
                a.append('{}:{}'.format(i, bt))
            s = '[{}] {}'.format(', '.join(a), s)
        
        return 'def {}'.format(s)
    
    def visit_overloaded(self, t):
        a = []
        for i in t.items():
            a.append(i.accept(self))
        return 'Overload({})'.format(', '.join(a))
    
    def visit_tuple_type(self, t):
        s = self.list_str(t.items)
        return 'tuple<{}>'.format(s)
    
    def visit_runtime_type_var(self, t):
        return '<RuntimeTypeVar>'
    
    # Convert items of an array to strings (pretty-print types) and join the
    # results with commas.
    def list_str(self, a):
        res = []
        for t in a:
            if isinstance(t, types.Typ):
                res.append(t.accept(self))
            else:
                res.append(str(t))
        return ', '.join(res)
