"""Mypy type checker command line tool."""

import sys

from mypy.main import main


def console_entry() -> None:
    try:
        main(None)
    except AssertionError:
        print("Uncaught AssertionError thrown by mypy. "
              "This may be caused by a bug in mypy, and can sometimes be "
              "worked around by clearing the '.mypy_cache' directory. "
              "Please report an issue at: https://github.com/python/mypy/issues",
              file=sys.stderr)
        raise


if __name__ == '__main__':
    main(None)
