"""Mypy type checker command line tool."""

import sys
from mypy.main import main


def console_entry() -> None:
    try:
        main(None, sys.stdout, sys.stderr)
    except BrokenPipeError:
        sys.exit(2)


if __name__ == '__main__':
    try:
        main(None, sys.stdout, sys.stderr)
    except BrokenPipeError:
        sys.exit(2)
