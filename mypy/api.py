"""This module makes it possible to use mypy as part of a Python application.

Since mypy still changes, the API was kept utterly simple and non-intrusive.
It just mimics command line activation without starting a new interpreter.
So the normal docs about the mypy command line apply.
Changes in the command line version of mypy will be immediately useable.

Just import this module and then call the 'run' function with a parameter of
type List[str], containing what normally would have been the command line
arguments to mypy.

Function 'run' returns a Tuple[str, str, int], namely
(<normal_report>, <error_report>, <exit_status>),
in which <normal_report> is what mypy normally writes to sys.stdout,
<error_report> is what mypy normally writes to sys.stderr and exit_status is
the exit status mypy normally returns to the operating system.

Any pretty formatting is left to the caller.

Trivial example of code using this module:

import sys
from mypy import api

result = api.run(sys.argv[1:])

if result[0]:
    print('\nType checking report:\n')
    print(result[0])  # stdout

if result[1]:
    print('\nError report:\n')
    print(result[1])  # stderr

print ('\nExit status:', result[2])
"""

import sys
from io import StringIO
from typing import List, Tuple
from mypy.main import main


def run(args: List[str]) -> Tuple[str, str, int]:
    old_stdout = sys.stdout
    new_stdout = StringIO()
    sys.stdout = new_stdout

    old_stderr = sys.stderr
    new_stderr = StringIO()
    sys.stderr = new_stderr

    try:
        main(None, args=args)
        exit_status = 0
    except SystemExit as system_exit:
        exit_status = system_exit.code
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return new_stdout.getvalue(), new_stderr.getvalue(), exit_status
