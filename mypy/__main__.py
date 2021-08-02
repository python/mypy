"""Mypy type checker command line tool."""

import sys
import os

from mypy.main import main
from mypy.util import FancyFormatter


def console_entry() -> None:
    try:
        main(None, sys.stdout, sys.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
    except BrokenPipeError:
        # Python flushes standard streams on exit; redirect remaining output
        # to devnull to avoid another BrokenPipeError at shutdown
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(2)
    except KeyboardInterrupt:
        formatter = FancyFormatter(sys.stdout, sys.stderr, False)
        msg = " KeybordInterrupt called by user. Abort!\n"
        sys.stdout.write(formatter.style(msg, color="red", bold=True))
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(2)


if __name__ == '__main__':
    console_entry()
