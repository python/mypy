"""Type parser"""

from mypy.types import Type, UnboundType, TupleType, TypeList
from mypy.typerepr import CommonTypeRepr, ListTypeRepr
from mypy.lex import Token, Name
from mypy import nodes


none = Token('') # Empty token


tuple<Type, int> parse_type(Token[] tok, int index):
    """Parse a type.

    Return (type, index after type).
    """
    p = TypeParser(tok, index)
    return p.parse_type(), p.index()


tuple<Type, int> parse_types(Token[] tok, int index):
    """Parse one or more types separated by commas (optional parentheses).

    Return (type, index after type).
    """
    p = TypeParser(tok, index)
    return p.parse_types(), p.index()


class TypeParser:
    Token[] tok
    int ind
    
    void __init__(self, Token[] tok, int ind):
        self.tok = tok
        self.ind = ind
    
    int index(self):
        return self.ind
    
    Type parse_type(self):
        """Parse a type."""
        t = self.current_token()
        if isinstance(t, Name):
            return self.parse_named_type()
        elif t.string == '[':
            return self.parse_type_list()
        else:
            self.parse_error()

    Type parse_types(self):
        parens = False
        if self.current_token_str() == '(':
            self.skip()
            parens = True
        type = self.parse_type()
        if self.current_token_str() == ',':
            items = [type]
            while self.current_token_str() == ',':
                self.skip()
                items.append(self.parse_type())
            type = TupleType(items)
        if parens:
            self.expect(')')
        return type

    TypeList parse_type_list(self):
        """Parse type list [t, ...]."""
        lbracket = self.expect('[')
        Token[] commas = []
        Type[] items = []
        while self.current_token_str() != ']':
            t = self.parse_type()
            items.append(t)
            if self.current_token_str() != ',':
                break
            commas.append(self.skip())
        rbracket = self.expect(']')
        return TypeList(items)
    
    Type parse_named_type(self):
        line = self.current_token().line
        name = ''
        Token[] components = []
        
        components.append(self.expect_type(Name))
        name += components[-1].string
        
        while self.current_token_str() == '.':
            components.append(self.skip())
            t = self.expect_type(Name)
            components.append(t)
            name += '.' + t.string
        
        langle, rangle = none, none
        Token[] commas = []
        Type[] args = []
        if self.current_token_str() == '[':
            lbracket = self.skip()
            
            while True:
                typ = self.parse_type()
                args.append(typ)
                if self.current_token_str() != ',':
                    break
                commas.append(self.skip())
            
            rbracket = self.expect(']')
        
        typ = UnboundType(name, args, line, CommonTypeRepr(components,
                                                           langle,
                                                           commas, rangle))
        return typ
    
    # Helpers
    
    Token skip(self):
        self.ind += 1
        return self.tok[self.ind - 1]
    
    Token expect(self, str string):
        if self.tok[self.ind].string == string:
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()
    
    Token expect_type(self, type typ):
        if isinstance(self.current_token(), typ):
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()
    
    Token current_token(self):
        return self.tok[self.ind]
    
    str current_token_str(self):
        return self.current_token().string
    
    void parse_error(self):
        raise TypeParseError(self.tok, self.ind)


class TypeParseError(Exception):
    int index
    Token token
    
    void __init__(self, Token[] token, int index):
        self.token = token[index]
        self.index = index
        super().__init__()
