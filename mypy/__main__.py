"""Mypy type checker command line tool."""

from __future__ import annotations

import os
import sys
import traceback

if 1:  # Required!
    import inspect
    print('')
    print(__file__)
    print('Start __main__.py')
    print('')
    path = r'c:\Repos\ekr-fork-mypy'
    if path not in sys.path:
        sys.path.insert(0, path)

from mypy.main import main, process_options
from mypy.util import FancyFormatter

if 1:
    for z in (main, process_options, FancyFormatter):
        assert 'ekr-fork-mypy' in inspect.getfile(z), repr(z)

def console_entry() -> None:
    try:
        main()
        sys.stdout.flush()
        sys.stderr.flush()
    except BrokenPipeError:
        # Python flushes standard streams on exit; redirect remaining output
        # to devnull to avoid another BrokenPipeError at shutdown
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(2)
    except KeyboardInterrupt:
        _, options = process_options(args=sys.argv[1:])
        if options.show_traceback:
            sys.stdout.write(traceback.format_exc())
        formatter = FancyFormatter(sys.stdout, sys.stderr, False)
        msg = "Interrupted\n"
        sys.stdout.write(formatter.style(msg, color="red", bold=True))
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(2)


if __name__ == "__main__":
    console_entry()
