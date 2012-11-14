

# Type visitor that outputs source code.
class TypeOutputVisitor:
    result = [] # Array<Str>
    
    # Return a string representation of the output.
    def output(self):
        return ''.join(self.result)
    
    def visit_unbound_type(self, t):
        r = t.repr
        self.tokens(r.components)
        self.token(r.langle)
        self.comma_list(t.args, r.commas)
        self.token(r.rangle)
    
    def visit_any(self, t):
        if t.repr is not None:
            self.token(t.repr.any_tok)
    
    def visit_void(self, t):
        if t.repr is not None:
            self.token(t.repr.void)
    
    def visit_instance(self, t):
        r = t.repr
        self.tokens(r.components)
        self.token(r.langle)
        self.comma_list(t.args, r.commas)
        self.token(r.rangle)
    
    def visit_type_var(self, t):
        self.token(t.repr.name)
    
    def visit_tuple_type(self, t):
        r = t.repr
        self.tokens(r.components)
        self.token(r.langle)
        self.comma_list(t.items, r.commas)
        self.token(r.rangle)
    
    def visit_callable(self, t):
        r = t.repr
        self.tokens(r.components)
        self.token(r.langle)
        self.comma_list(t.arg_types + [t.ret_type], r.commas)
        self.token(r.rangle)
    
    def type_vars(self, v):
        if v is not None and v.repr is not None:
            r = v.repr
            self.token(r.langle)
            for i in range(len(v.items)):
                d = v.items[i]
                self.token(d.repr.name)
                self.token(d.repr.is_tok)
                if d.bound is not None:
                    self.typ(d.bound)
                if i < len(r.commas):
                    self.token(r.commas[i])
            self.token(r.rangle)
    
    # Helpers
    
    # Output a string.
    def string(self, s):
        self.result.append(s)
    
    # Output a token.
    def token(self, t):
        self.result.append(t.rep)
    
    # Output an array of tokens.
    def tokens(self, a):
        for t in a:
            self.token(t)
    
    # Output a type.
    def typ(self, n):
        if n is not None:
            n.accept(self)
    
    def comma_list(self, items, commas):
        for i in range(len(items)):
            self.typ(items[i])
            if i < len(commas):
                self.token(commas[i])
