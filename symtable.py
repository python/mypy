import re
from mtypes import Typ
from util import short_type
import nodes


# TODO move to nodes?
TVAR = 4 # Constant for type variable nodes in symbol table


class SymbolTable(dict<str, SymbolTableNode>):
    str __str__(self):
        list<str> a = []
        for key, value in self.items():
            # Filter out the implicit import of builtins.
            if isinstance(value, SymbolTableNode):
                if value.full_name() != 'builtins':
                    a.append('  ' + str(key) + ' : ' + repr(value))
            else:
                a.append('  <invalid item>')
        a = sorted(a)
        a.insert(0, 'SymbolTable(')
        a[-1] += ')'
        return '\n'.join(a)


# Supertype for node types that can be stored in the symbol table.
interface SymNode:
    str name(self)
    str full_name(self)


class SymbolTableNode:
    int kind # Ldef/Gdef/Mdef/Tvar
    SymNode node  # Parse tree node of definition (FuncDef/Var/
    # TypeInfo), nil for Tvar
    int tvar_id    # Type variable id (for Tvars only)
    str mod_id    # Module id (e.g. "foo.bar") or nil
    
    Typ type_override  # If nil, fall back to type of node
    
    void __init__(self, int kind, SymNode node, str mod_id=None, Typ typ=None, int tvar_id=0):
        self.kind = kind
        self.node = node
        self.type_override = typ
        self.mod_id = mod_id
        self.tvar_id = tvar_id
    
    str full_name(self):
        if self.node is not None:
            return self.node.full_name()
        else:
            return None
    
    Typ typ(self):
        # IDEA: Get rid of the dynamic cast.
        any node = self.node
        if self.type_override is not None:
            return self.type_override
        elif (isinstance(node, nodes.Var) or isinstance(node, nodes.FuncDef)) and node.typ is not None:
            return node.typ.typ
        else:
            return None
    
    str __str__(self):
        s = '{}/{}'.format(clean_up(str(self.kind)), short_type(self.node))
        if self.mod_id is not None:
            s += ' ({})'.format(self.mod_id)
        # Include declared type of variables and functions.
        if self.typ is not None:
            s += ' : {}'.format(self.typ)
        return s


str clean_up(str s):
    return re.sub('.*::', '', s)
