import sys

from mypy.version import __version__
from mypy.build import build, BuildSource, Options

print(__version__)

options = Options()
options.show_traceback = True
options.raise_exceptions = True
# options.verbosity = 10
result = build([BuildSource("test.py", None, )], options, stderr=sys.stderr, stdout=sys.stdout)
print(*result.errors, sep="\n")
