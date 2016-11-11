# This module makes it possible to use mypy as part of a Python application.
#
# Since mypy still changes, the API was kept utterly simple and non-intrusive.
# It just mimics command line activation without starting a new interpreter.
# So the normal docs about the mypy command line apply.
# Changes in the command line version of mypy will be immediately useable.
#
# Just import this module and then call the 'run' function with exactly the
# string you would have passed to mypy from the command line.
# Function 'run' returns all reporting info that's normally printed.
# Any pretty formatting is left to the caller.

import sys
from io import StringIO
from mypy.main import main

def run (params):
	sys.argv = [None] + params.split ()
	string_io = StringIO ()
	old_stdout = sys.stdout
	sys.stdout = string_io
	try:
		main (None)
	except:
		pass
	sys.stdout = old_stdout
	return string_io.getvalue ()
	