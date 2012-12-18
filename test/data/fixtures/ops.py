# This is an extension of transform builtins with additional operations.

class object:
    void __init__(self): pass

class type: pass

class str:
    void __init__(self, int x): pass
    str __add__(self, str x): pass

class int:
    int __add__(self, int x): pass
    int __sub__(self, int x): pass
    int __mul__(self, int x): pass
    int __mod__(self, int x): pass
    int __idiv__(self, int x): pass
    int __neg__(self): pass
    bool __eq__(self, int x): pass
    bool __lt__(self, int x): pass
    bool __gt__(self, int x): pass

class float: pass

class bool: pass

class BaseException: pass

bool True
bool False

def __print(a1=None, a2=None, a3=None, a4=None): pass
