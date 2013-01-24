# Stubs for shlex

# Based on http://docs.python.org/3.2/library/shlex.html

str[] split(str s, bool comments=False, bool posix=True): pass

class shlex:
    str commenters
    str wordchars
    str whitespace
    str escape
    str quotes
    str escapedquotes
    str whitespace_split
    str infile
    TextIO instream
    str source
    int debug
    int lineno
    str token
    str eof
    
    void __init__(self, instream=None, infile=None, bool posix=False): pass
    str get_token(self): pass
    void push_token(self, str tok): pass
    str read_token(self): pass
    tuple<str, TextIO> sourcehook(self, str filename): pass
    # TODO argument types
    void push_source(self, any newstream, any newfile=None): pass
    void pop_source(self): pass
    # TODO int with None default
    void error_leader(self, str infile=None, int lineno=None): pass
