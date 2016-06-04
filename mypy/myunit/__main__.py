# This is a separate module from mypy.myunit so it doesn't exist twice.
"""Myunit test runner command line tool.

Usually used as a slave by runtests.py, but can be used directly.
"""

from mypy.myunit import main

# In Python 3.3, mypy.__path__ contains a relative path to the mypy module
# (whereas in later Python versions it contains an absolute path).  Because the
# test runner changes directories, this breaks non-toplevel mypy imports.  We
# fix that problem by fixing up the path to be absolute here.
import os.path
import mypy
# User-defined packages always have __path__ attributes, but mypy doesn't know that.
mypy.__path__ = [os.path.abspath(p) for p in mypy.__path__]  # type: ignore

main()
