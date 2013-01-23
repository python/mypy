# Builtins for the native back end

# TODO this still in early stages of development

class object:
    void __init__(self): pass

class type: pass
class str: pass

# Primitive types are special in generated code.

class int:
    int __add__(self, int n): pass
    int __sub__(self, int n): pass
    int __mul__(self, int n): pass
    int __floordiv__(self, int n): pass
    int __mod__(self, int n): pass
    int __neg__(self): pass
    bool __eq__(self, int n): pass
    bool __ne__(self, int n): pass
    bool __lt__(self, int n): pass
    bool __gt__(self, int n): pass
    bool __le__(self, int n): pass
    bool __ge__(self, int n): pass

class float: pass
class bool: pass

class list<t>: pass

void print(*object): pass
