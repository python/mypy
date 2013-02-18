# Stubs for re
# Ron Murawski <ron@horizonchess.com>
# 'bytes' support added by Jukka Lehtosalo

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

# ----- re classes -----
class Pattern:
    int flags, groupindex, groups
    str pattern

    Match search(self, str string, int pos=0, int endpos=-1): pass
    Match match(self, str string, int pos=0, int endpos=-1): pass
    str[] split(self, str string, int maxsplit=0): pass
    str[] findall(self, str string, int pos=0, int endpos=-1): pass
    Iterator<Match> finditer(self, str string, int pos=0, int endpos=-1): pass
    str sub(self, str repl, str string, int count=0): pass
    str sub(self, func<str(Match)> repl, str string, int count=0): pass
    tuple<str, int> subn(self, str repl, str string, int count=0): pass
    tuple<str, int> subn(self, func<str(Match)> repl, str string,
                         int count=0): pass

class BytesPattern:
    int flags, groupindex, groups
    bytes pattern

    BytesMatch search(self, bytes string, int pos=0, int endpos=-1): pass
    BytesMatch match(self, bytes string, int pos=0, int endpos=-1): pass
    bytes[] split(self, bytes string, int maxsplit=0): pass
    bytes[] findall(self, bytes string, int pos=0, int endpos=-1): pass
    Iterator<BytesMatch> finditer(self, bytes string, int pos=0,
                                  int endpos=-1): pass
    bytes sub(self, bytes repl, bytes string, int count=0): pass
    bytes sub(self, func<bytes(BytesMatch)> repl, bytes string,
              int count=0): pass
    tuple<bytes, int> subn(self, bytes repl, bytes string, int count=0): pass
    tuple<bytes, int> subn(self, func<bytes(BytesMatch)> repl, bytes string,
                           int count=0): pass

class Match:
    int pos, int endpos, int lastindex
    str lastgroup, str string
    
    # The regular expression object whose match() or search() method produced
    # this match instance.
    Pattern re
    
    str expand(self, str template): pass
    str group(self, int group1=0): pass
    str group(self, str group1): pass
    Sequence<str> group(self, int group1, int group2, int *groups): pass
    Sequence<str> group(self, str group1, str group2, str *groups): pass    
    Sequence<str> groups(self, str default=None): pass
    dict<str, str> groupdict(self, str default=None): pass
    int start(self, int group=0): pass
    int end(self, int group=0): pass
    tuple<int, int> span(self, int group=0): pass

class BytesMatch:
    int pos, int endpos, int lastindex
    bytes lastgroup, bytes string
    
    # The regular expression object whose match() or search() method produced
    # this match instance.
    BytesPattern re
    
    bytes expand(self, bytes template): pass
    str group(self, int group1=0): pass
    str group(self, str group1): pass
    Sequence<bytes> group(self, int group1, int group2, int *groups): pass
    Sequence<bytes> group(self, bytes group1, bytes group2,
                          bytes *groups): pass    
    Sequence<bytes> groups(self, bytes default=None): pass
    dict<bytes, bytes> groupdict(self, bytes default=None): pass
    int start(self, int group=0): pass
    int end(self, int group=0): pass
    tuple<int, int> span(self, int group=0): pass

Pattern compile(str pattern, int flags=0): pass
BytesPattern compile(bytes pattern, int flags=0): pass
Match search(str pattern, str string, int flags=0): pass
BytesMatch search(bytes pattern, bytes string, int flags=0): pass
Match match(str pattern, str string, int flags=0): pass
BytesMatch match(bytes pattern, bytes string, int flags=0): pass
str[] split(str pattern, str string, int maxsplit=0, int flags=0): pass
bytes[] split(bytes pattern, bytes string, int maxsplit=0, int flags=0): pass
str[] findall(str pattern, str string, int flags=0): pass
bytes[] findall(bytes pattern, bytes string, int flags=0): pass

# Return an iterator yielding match objects over all non-overlapping matches 
# for the RE pattern in string. The string is scanned left-to-right, and 
# matches are returned in the order found. Empty matches are included in the 
# result unless they touch the beginning of another match.
Iterator<Match> finditer(str pattern, str string, int flags=0): pass
Iterator<BytesMatch> finditer(bytes pattern, bytes string, int flags=0): pass

str sub(str pattern, str repl, str string, int count=0, int flags=0): pass
str sub(str pattern, func<str(Match)> repl, str string, int count=0,
        int flags=0): pass
bytes sub(bytes pattern, bytes repl, bytes string, int count=0,
          int flags=0): pass
bytes sub(bytes pattern, func<bytes(BytesMatch)> repl, bytes string,
          int count=0, int flags=0): pass

tuple<str, int> subn(str pattern, str repl, str string, int count=0, 
                     int flags=0): pass
tuple<str, int> subn(str pattern, func<str(Match)> repl, str string, 
                     int count=0, int flags=0): pass
tuple<bytes, int> subn(bytes pattern, bytes repl, bytes string, int count=0, 
                       int flags=0): pass
tuple<bytes, int> subn(bytes pattern, func<bytes(BytesMatch)> repl,
                       bytes string, int count=0, int flags=0): pass

str escape(str string): pass
bytes escape(bytes string): pass
void purge(): pass
