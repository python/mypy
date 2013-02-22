# Stubs for fnmatch

# Based on http://docs.python.org/3.2/library/fnmatch.html

bool fnmatch(str filename, str pattern): pass
bool fnmatch(bytes filename, bytes pattern): pass
bool fnmatchcase(str filename, str pattern): pass
bool fnmatchcase(bytes filename, bytes pattern): pass
str[] filter(Iterable<str> names, str pattern): pass
bytes[] filter(Iterable<bytes> names, bytes pattern): pass
str translate(str pattern): pass
