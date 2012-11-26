# Stubs for struct

# Based on http://docs.python.org/3.2/library/struct.html

class error(Exception): pass

bytes pack(str fmt, any *v): pass
bytes pack(bytes fmt, any *v): pass
void pack_into(str fmt, any buffer, int offset, any *v): pass
# TODO buffer type
void pack_into(bytes fmt, any buffer, int offset, any *v): pass
# TODO return type should be tuple
# TODO buffer type
any unpack(str fmt, any buffer): pass
any unpack(bytes fmt, any buffer): pass
any unpack_from(str fmt, any buffer): pass
any unpack_from(bytes fmt, any buffer, int offset=0): pass
int calcsize(str fmt): pass
int calcsize(bytes fmt): pass

class Struct:
    bytes format
    int size
    
    void __init__(self, str format): pass
    void __init__(self, bytes format): pass

    bytes pack(self, any *v): pass
    # TODO buffer type
    void pack_into(self, any buffer, int offset, any *v): pass
    # TOTO return type should be tuple
    # TODO buffer type
    any unpack(self, any buffer): pass
    any unpack_from(self, any buffer, int offset=0): pass
