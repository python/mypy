# This is a separate module from mypy.myunit so it doesn't exist twice.
"""Myunit test runner command line tool.

Usually used as a slave by runtests.py, but can be used directly.
"""

from mypy.myunit import main

main()
