from mtypes import Typ, TypeVars, TypeVarDef, Any, Void, UnboundType
from typerepr import (
    TypeVarsRepr, TypeVarDefRepr, AnyRepr, VoidRepr, CommonTypeRepr
)
from lex import Token, Name


none = Token('') # Empty token


tuple<Typ, int> parse_type(list<Token> tok, int index):
    """Parse a type. Return (type, index after type)."""
    p = TypeParser(tok, index)
    return p.parse_type(), p.index()


tuple<TypeVars, int> parse_type_variables(list<Token> tok, int index,
                                          bool is_func):
    """Parse type variables and optional bounds (<...>). Return (bounds, index
    after bounds).
    """
    p = TypeParser(tok, index)
    return p.parse_type_variables(is_func), p.index()


tuple<list<Typ>, Token, Token, \
      list<Token>, int> parse_type_args(list<Token> tok, int index):
    """Parse type arguments within angle brackets (<...>). Return
    (types, < token, > token, comma tokens, token index after >).
    """
    p = TypeParser(tok, index)
    types, lparen, rparen, commas = p.parse_type_args()
    return types, lparen, rparen, commas, p.index()


class TypeParser:
    list<Token> tok
    int ind
    # Have we consumed only the first '>' of a '>>' token?
    bool partial_shr
    
    void __init__(self, list<Token> tok, int ind):
        self.tok = tok
        self.ind = ind
        self.partial_shr = False
    
    int index(self):
        return self.ind
    
    Typ parse_type(self):
        """Parse a type."""
        t = self.current_token()
        if t.string == 'any':
            return self.parse_any_type()
        elif t.string == 'void':
            return self.parse_void_type()
        elif isinstance(t, Name):
            return self.parse_named_type()
        else:
            self.parse_error()
    
    TypeVars parse_type_variables(self, bool is_func):
        """Parse type variables and optional bounds (<...>)."""
        langle = self.expect('<')
        
        list<Token> commas = []
        list<TypeVarDef> items = []
        n = 1
        while True:
            t = self.parse_type_variable(n, is_func)
            items.append(t)
            if self.current_token_str() != ',':
                break
            commas.append(self.skip())
            n += 1
        
        rangle = self.expect('>')
        return TypeVars(items, TypeVarsRepr(langle, commas, rangle))
    
    TypeVarDef parse_type_variable(self, int n, bool is_func):
        t = self.expect_type(Name)
        
        line = t.line
        name = t.string
        
        is_tok = none
        Typ bound = None
        if self.current_token_str() == 'is':
            is_tok = self.skip()
            bound = self.parse_type()
        
        if is_func:
            n = -n
        
        return TypeVarDef(name, n, bound, line, TypeVarDefRepr(t, is_tok))
    
    tuple<list<Typ>, Token, Token, list<Token>> parse_type_args(self):
        """Parse type arguments within angle brackets (<...>)."""
        langle = self.expect('<')
        list<Token> commas = []
        list<Typ> types = []
        while True:
            types.append(self.parse_type())
            if self.current_token_str() != ',':
                break
            commas.append(self.skip())
        rangle = self.expect('>')
        return types, langle, rangle, commas
    
    Any parse_any_type(self):
        """Parse "any" type."""
        tok = self.skip()
        return Any(tok.line, AnyRepr(tok))
    
    Void parse_void_type(self):
        """Parse "void" type."""
        tok = self.skip()
        return Void(None, tok.line, VoidRepr(tok))
    
    UnboundType parse_named_type(self):
        line = self.current_token().line
        name = ''
        list<Token> components = []
        
        components.append(self.expect_type(Name))
        name += components[-1].string
        
        while self.current_token_str() == '.':
            components.append(self.skip())
            t = self.expect_type(Name)
            components.append(t)
            name += '.' + t.string
        
        langle, rangle = none, none
        list<Token> commas = []
        list<Typ> args = []
        if self.current_token_str() == '<':
            langle = self.skip()
            
            while True:
                typ = self.parse_type()
                args.append(typ)
                if self.current_token_str() != ',':
                    break
                commas.append(self.skip())
            
            rangle = self.expect('>')
        
        return UnboundType(name, args, line, CommonTypeRepr(components, langle,
                                                            commas, rangle))
    
    # Helpers
    
    Token skip(self):
        self.ind += 1
        return self.tok[self.ind - 1]
    
    Token expect(self, str string):
        if string == '>' and self.partial_shr:
            self.partial_shr = False
            self.ind += 1
            return Token('')
        elif string == '>' and self.tok[self.ind].string == '>>':
            self.partial_shr = True
            return self.tok[self.ind]
        elif self.partial_shr:
            self.parse_error()
        elif self.tok[self.ind].string == string:
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()
    
    Token expect_type(self, type typ):
        if self.partial_shr:
            self.parse_error()
        elif isinstance(self.current_token(), typ):
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()
    
    Token current_token(self):
        return self.tok[self.ind]
    
    str current_token_str(self):
        s = self.current_token().string
        if s == '>>':
            s = '>'
        return s
    
    void parse_error(self):
        raise TypeParseError(self.tok, self.ind)


class TypeParseError(Exception):
    int index
    Token token
    
    void __init__(self, list<Token> token, int index):
        self.token = token[index]
        self.index = index
        super().__init__()
