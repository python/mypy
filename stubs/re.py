# Stubs for re

# TODO functions and classes that work on bytes objects
# TODO more functionality

int MULTILINE

class Pattern:
    Match match(self, str string, int pos=0, int endpos=-1): pass
    Match search(self, str string, int pos=0, int endpos=-1): pass
    str sub(self, str repl, str string, int count=0, int flags=0): pass
    str sub(self, func<Match, str> repl, str string, int count=0,
            int flags=0): pass

class Match:
    str expand(self, str template): pass
    str group(self): pass
    str group(self, int group1): pass
    # TODO group(...) with multiple groups
    int start(self, int group=0): pass
    int end(self, int group=0): pass
    tuple<int, int> span(self, int group=0): pass

Pattern compile(str pattern, int flags=0): pass

Match match(str pattern, str string, int flags=0): pass
Match search(str pattern, str string, int flags=0): pass
str sub(str pattern, str repl, str string, int count=0, int flags=0): pass
str sub(str pattern, func<Match, str> repl, str string, int count=0,
        int flags=0): pass
