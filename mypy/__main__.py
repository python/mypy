"""Mypy type checker command line tool."""

import sys
from mypy.main import main


def console_entry() -> None:
    try:
        main(None, sys.stdout, sys.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(2)


if __name__ == '__main__':
    console_entry()
