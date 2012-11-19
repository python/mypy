# Stubs for pprint

# Based on http://docs.python.org/3.2/library/pprint.html

str pformat(object o, int indent=1, int width=80, int depth=None): pass
void pprint(object o, TextIO stream=None, int indent=1, int width=80,
            int depth=None): pass
bool isreadable(object o): pass
bool isrecursive(object o): pass
str saferepr(object o): pass

class PrettyPrinter:
    void __init__(self, int indent=1, int width=80, int depth=None,
                  TextIO stream=None): pass
    str pformat(self, object o): pass
    void pprint(self, object o): pass
    bool isreadable(self, object o): pass
    bool isrecursive(self, object o): pass
    tuple<str, bool, bool> format(self, object o, dict<int, any> context,
                                  int maxlevels, int level): pass
