# These builtins stubs are used implicitly in parse-tree to icode generation
# test cases (testicodegen.py and test/data/icode-basic.test).

class object:
    void __init__(self): pass

class type: pass
class str: pass

# Primitive types are special in generated code.

class int:
    int __add__(self, int n): pass
    int __sub__(self, int n): pass
    int __mul__(self, int n): pass
    int __neg__(self): pass
    bool __eq__(self, int n): pass
    bool __ne__(self, int n): pass
    bool __lt__(self, int n): pass
    bool __gt__(self, int n): pass
    bool __le__(self, int n): pass
    bool __ge__(self, int n): pass

class float: pass
class bool: pass
