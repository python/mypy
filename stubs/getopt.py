# Stubs for getopt

# Based on http://docs.python.org/3.2/library/getopt.html

tuple<tuple<str, str>[], str[]> \
                      getopt(str[] args, str shortopts,
                             str[] longopts): pass

tuple<tuple<str, str>[], str[]> \
                      gnu_getopt(str[] args, str shortopts,
                                 str[] longopts): pass

class GetoptError(Exception):
    str msg
    str opt

error = GetoptError
