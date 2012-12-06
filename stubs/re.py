# Stubs for re

# based on: http://docs.python.org/3.2/library/re.html
# and http://hg.python.org/cpython/file/618ea5612e83/Lib/re.py

# ----- re variables and constants -----
int A
int ASCII
int DEBUG
int I
int IGNORECASE
int L
int LOCALE
int M
int MULTILINE
int S
int DOTALL
int X
int VERBOSE

class error(Exception): pass

# TODO functions and classes that work on bytes objects

# ----- re classes -----
class Pattern:
    int flags, groupindex, groups
    str pattern

    Match search(self, str string, int pos=0, int endpos=-1): pass
    Match match(self, str string, int pos=0, int endpos=-1): pass
    list<str> split(self, str string, int maxsplit=0): pass
    list<str> findall(self, str string, int pos=0, int endpos=-1): pass
    Iterator<Match> finditer(self, str string, int pos=0, int endpos=-1): pass
    str sub(self, str repl, str string, int count=0): pass
    str sub(self, func<str(Match)> repl, str string, int count=0): pass
    tuple<str, int> subn(self, str repl, str string, int count=0): pass
    tuple<str, int> subn(self, func<str(Match)> repl, str string,
                         int count=0): pass

class Match:
    int pos, endpos, lastindex
    str lastgroup, string
    
    # The regular expression object whose match() or search() method produced
    # this match instance.
    Pattern re
    
    str expand(self, str template): pass
    str group(self): pass
    str group(self, int group1): pass
    
    # TODO group(...) with multiple groups
    # if there are multiple arguments, the result is a tuple with one item per
    # argument
    list<str> group(self, list<int> group1): pass  # not quite correct! ???
    
    tuple<str, str> groups(self, str default=None): pass
    dict<str, str> groupdict(self, str default=None): pass
    int start(self, int group=0): pass
    int end(self, int group=0): pass
    tuple<int, int> span(self, int group=0): pass

Pattern compile(str pattern, int flags=0): pass
Match search(str pattern, str string, int flags=0): pass
Match match(str pattern, str string, int flags=0): pass
list<str> split(str pattern, str string, int maxsplit=0, int flags=0): pass
list<str> findall(str pattern, str string, int flags=0): pass

# Return an iterator yielding match objects over all non-overlapping matches 
# for the RE pattern in string. The string is scanned left-to-right, and 
# matches are returned in the order found. Empty matches are included in the 
# result unless they touch the beginning of another match.
Iterator<Match> finditer(str pattern, str string, int flags=0): pass

str sub(str pattern, str repl, str string, int count=0, int flags=0): pass
str sub(str pattern, func<str(Match)> repl, str string, int count=0,
        int flags=0): pass
tuple<str, int> subn(str pattern, str repl, str string, int count=0, 
                     int flags=0): pass
tuple<str, int> subn(str pattern, func<str(Match)> repl, str string, 
                     int count=0, int flags=0): pass
str escape(str string): pass
void purge(): pass
