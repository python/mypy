# Stubs for fnmatch

# Based on http://docs.python.org/3.2/library/fnmatch.html and
# python-lib/fnmatch.py

bool fnmatch(str name, str pat): pass
bool fnmatch(bytes name, bytes pat): pass
bool fnmatchcase(str name, str pat): pass
bool fnmatchcase(bytes name, bytes pat): pass
str[] filter(Iterable<str> names, str pat): pass
bytes[] filter(Iterable<bytes> names, bytes pat): pass
str translate(str pat): pass
