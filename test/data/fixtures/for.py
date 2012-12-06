# builtins stub used in for statement test cases

class object:
    void __init__(self): pass
class type: pass
class bool: pass

interface Iterable<t>:
    Iterator<t> __iter__(self)

interface Iterator<t>(Iterable<t>):
    t __next__(self)

class list<t>(Iterable<t>):
    Iterator<t> __iter__(self): pass

class tuple: pass
