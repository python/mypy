# Stubs for getopt

# Based on http://docs.python.org/3.2/library/getopt.html

tuple<list<tuple<str, str>>, list<str>> \
                      getopt(list<str> args, str shortopts,
                             list<str> longopts): pass

tuple<list<tuple<str, str>>, list<str>> \
                      gnu_getopt(list<str> args, str shortopts,
                                 list<str> longopts): pass

class GetoptError(Exception):
    str msg
    str opt

error = GetoptError
