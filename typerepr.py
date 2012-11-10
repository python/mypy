from lex import Token

# Representation classes for Typ subclasses and TypeVars. These are used for
# source-source transformation that preserves original formatting and
# comments.


# Representation of UnboundType, Instance and Callable.
class CommonTypeRepr:
    # Note: langle and rangle may be empty.
    void __init__(self, list<Token> components,  langle, list<Token> commas,
                  any rangle):
        self.components = components
        self.langle = langle
        self.commas = commas
        self.rangle = rangle


# Representation of Any.
class AnyRepr:
    void __init__(self, any any_tok):
        self.any_tok = any_tok


# Representation of Void.
class VoidRepr:
    void __init__(self, any void):
        self.void = void


# Representation of NoneType.
class NoneTypeRepr: pass


# Representation of TypeVar.
class TypeVarRepr:
    void __init__(self, any name):
        self.name = name


# Representation of TypeVars.
class TypeVarsRepr:
    void __init__(self, any langle, list<Token> commas, any rangle):
        self.langle = langle
        self.commas = commas
        self.rangle = rangle


# Representation of TypeVarDef.
class TypeVarDefRepr:
    # TODO remove is_tok
    void __init__(self, any name, any is_tok):
        self.name = name
        self.is_tok = is_tok
