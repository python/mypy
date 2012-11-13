# builtins stub used in for statement test cases

class object:
    void __init__(self): pass
class type: pass
class bool: pass

interface iterable<t>:
    iterator<t> __iter__(self)

interface iterator<t>:
    iterator<t> __iter__(self)
    t __next__(self)

class list<t>(iterable<t>):
    iterator<t> __iter__(self): pass

class tuple: pass
