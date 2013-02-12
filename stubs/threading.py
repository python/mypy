# Stubs for threading

# NOTE: These are incomplete!

class Thread:
    str name
    int ident
    bool daemon
    
    void __init__(self, any group=None, any target=None, any args=(),
                  dict<any, any> kwargs=None, any verbose=None): pass
    void start(self): pass
    void run(self): pass
    # TODO None value for float
    void join(self, float timeout=None): pass
    bool is_alive(self): pass

    # Legacy methods
    str getName(self): pass
    void setName(self, str name): pass
    bool isDaemon(self): pass
    void setDaemon(self, bool daemon): pass

class Event:
    bool is_set(self): pass
    void set(self): pass
    void clear(self): pass
    # TODO can it return None?
    # TOOD None value for float
    bool wait(self, float timeout=None): pass
