"""Mypy type checker command line tool."""

import sys
from mypy.main import main


def console_entry() -> None:
    main(None, sys.stdout, sys.stderr)


if __name__ == '__main__':
    main(None, sys.stdout, sys.stderr)
