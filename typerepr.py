
# Representation classes for Typ subclasses and TypeVars. These are used for
# source-source transformation that preserves original formatting and
# comments.


# Representation of UnboundType, Instance and Callable.
class CommonTypeRepr:
    any components   # Array<Token>
    any langle       # May be None
    any commas       # Array<Token>
    any rangle       # May be None
    
    void __init__(self, any components, any langle, any commas, any rangle):
        self.components = components
        self.langle = langle
        self.commas = commas
        self.rangle = rangle


# Representation of Any.
class AnyRepr:
    any any_tok
    
    void __init__(self, any any_tok):
        self.any_tok = any_tok


# Representation of Void.
class VoidRepr:
    any void
    
    void __init__(self, any void):
        self.void = void


# Representation of Nil.
class NoneTypeRepr: pass


# Representation of TypeVar.
class TypeVarRepr:
    any name
    
    void __init__(self, any name):
        self.name = name


# Representation of TypeVars.
class TypeVarsRepr:
    any langle
    any commas   # Array<Token>
    any rangle
    
    void __init__(self, any langle, any commas, any rangle):
        self.langle = langle
        self.commas = commas
        self.rangle = rangle


# Representation of TypeVarDef.
class TypeVarDefRepr:
    any name
    any is_tok   # May be None
    
    void __init__(self, any name, any is_tok):
        self.name = name
        self.is_tok = is_tok
