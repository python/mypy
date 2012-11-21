# Stubs for test.support

# This is an internal module used by Python tests.

# TODO this is a partial implementation

bool verbose
bool is_jython

class EnvironmentVarGuard:
    # TODO dictionary interface
    void __enter__(self): pass
    void __exit__(self): pass

void run_unittest(any *classes): pass # arguments can be types or strings
tuple<int, int> run_doctest(any module, int verbosity=None): # int can be None
    pass
