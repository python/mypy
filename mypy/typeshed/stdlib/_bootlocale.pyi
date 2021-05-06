import sys

if sys.version_info < (3, 10):
    def getpreferredencoding(do_setlocale: bool = ...) -> str: ...
