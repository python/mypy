# Stubs for logging.handlers

# NOTE: These are incomplete!

class BufferingHandler:
    void __init__(self, int capacity): pass
    void emit(self, any record): pass
    void flush(self): pass
    bool shouldFlush(self, any record): pass
