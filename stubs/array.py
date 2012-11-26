# Stubs for array

# Based on http://docs.python.org/3.2/library/array.html

class array:
    str typecodes # TODO static
    str typecode
    int itemsize
    
    void __init__(self, str typecode, Iterable<any> initializer=None): pass

    void append(self, any x): pass
    tuple<int, int> buffer_info(self): pass
    void byteswap(self): pass
    int count(self, any x): pass
    void extend(self, Iterable<any> iterable): pass
    void frombytes(self, bytes s): pass
    void fromfile(self, IO f, int n): pass
    void fromlist(self, list<any> list): pass
    void fromstring(self, bytes s): pass
    void fromunicode(self, str s): pass
    int index(self, any x): pass
    void insert(self, int i, any x): pass
    any pop(self, int i=-1): pass
    void remove(self, any x): pass
    void reverse(self): pass
    bytes tobytes(self): pass
    void tofile(self, IO f): pass
    list<any> tolist(self): pass
    bytes tostring(self): pass
    str tounicode(self): pass
    
    int __len__(self): pass
    Iterator<any> __iter__(self): pass
    str __str__(self): pass
    int __hash__(self): pass
    
    any __getitem__(self, int i): pass
    array __getitem__(self, slice s): pass    
    void __setitem__(self, int i, any o): pass
    void __delitem__(self, int i): pass
    array __add__(self, array x): pass
    array __mul__(self, int n): pass
    bool __contains__(self, object o): pass
