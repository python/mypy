# Stubs for getopt

# Based on http://docs.python.org/3.2/library/getopt.html

tuple<list<tuple<str, str>>, str[]> \
                      getopt(str[] args, str shortopts,
                             str[] longopts): pass

tuple<list<tuple<str, str>>, str[]> \
                      gnu_getopt(str[] args, str shortopts,
                                 str[] longopts): pass

class GetoptError(Exception):
    str msg
    str opt

error = GetoptError
