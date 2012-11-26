# Stubs for warnings

# Based on http://docs.python.org/3.2/library/warnings.html

void warn(str message, type category=None, int stacklevel=1): pass
void warn(Warning message, type category=None, int stacklevel=1): pass
void warn_explicit(str message, type category, str filename, int lineno,
                   str module=None, any registry=None,
                   any module_globals=None): pass
void warn_explicit(Warning message, type category, str filename, int lineno,
                   str module=None, any registry=None,
                   any module_globals=None): pass
void showwarning(str message, type category, str filename, int lineno,
                 TextIO file=None, str line=None): pass
void formatwarning(str message, type category, str filename, int lineno,
                   str line=None): pass
void filterwarnings(str action, str message='', type category=Warning,
                    str module='', int lineno=0, bool append=False): pass
void simplefilter(str action, type category=Warning, int lineno=0,
                  bool append=False): pass
void resetwarnings(): pass

class catch_warnings:
    # TODO record and module must be keyword arguments!
    # TODO type of module?
    void __init__(self, bool record=False, any module=None): pass
    void __enter__(self): pass
    void __exit__(self): pass
