# Stubs for string

# Based on http://docs.python.org/3.2/library/string.html

str ascii_letters
str ascii_lowercase
str ascii_uppercase
str digits
str hexdigits
str octdigits
str punctuation
str printable
str whitespace

str capwords(str s, str sep=None): pass

class Template:
    str template
    
    void __init__(self, str template): pass
    str substitute(self, Mapping<str, str> mapping, str **kwds): pass
    str safe_substitute(self, Mapping<str, str> mapping, str **kwds): pass

# TODO Formatter
