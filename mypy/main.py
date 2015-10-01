"""Mypy type checker command line tool."""

import os
import os.path
import shutil
import subprocess
import sys
import tempfile

import typing
from typing import List, Tuple

from mypy import build
from mypy.errors import CompileError

from mypy.version import __version__


class Options:
    def __init__(self) -> None:
        # Set default options.
        self.target = build.TYPE_CHECK
        self.build_flags = []  # type: List[str]
        self.pyversion = 3
        self.custom_typing_module = None  # type: str
        self.html_report_dir = None  # type: str
        self.python_path = False


def main() -> None:
    bin_dir = find_bin_directory()
    path, module, program_text, options = process_options(sys.argv[1:])
    try:
        if options.target == build.TYPE_CHECK:
            type_check_only(path, module, program_text, bin_dir, options)
        else:
            raise RuntimeError('unsupported target %d' % options.target)
    except CompileError as e:
        for m in e.messages:
            sys.stderr.write(m + '\n')
        sys.exit(1)


def find_bin_directory() -> str:
    """Find the directory that contains this script.

    This is used by build to find stubs and other data files.
    """
    script = __file__
    # Follow up to 5 symbolic links (cap to avoid cycles).
    for i in range(5):
        if os.path.islink(script):
            script = readlinkabs(script)
        else:
            break
    return os.path.dirname(script)


def readlinkabs(link: str) -> str:
    """Return an absolute path to symbolic link destination."""
    # Adapted from code by Greg Smith.
    assert os.path.islink(link)
    path = os.readlink(link)
    if os.path.isabs(path):
        return path
    return os.path.join(os.path.dirname(link), path)


def type_check_only(path: str, module: str, program_text: str,
        bin_dir: str, options: Options) -> None:
    # Type check the program and dependencies and translate to Python.
    build.build(path,
                module=module,
                program_text=program_text,
                bin_dir=bin_dir,
                target=build.TYPE_CHECK,
                pyversion=options.pyversion,
                custom_typing_module=options.custom_typing_module,
                html_report_dir=options.html_report_dir,
                flags=options.build_flags,
                python_path=options.python_path)


def process_options(args: List[str]) -> Tuple[str, str, str, Options]:
    """Process command line arguments.

    Return (mypy program path (or None),
            module to run as script (or None),
            parsed flags)
    """
    options = Options()
    help = False
    ver = False
    while args and args[0].startswith('-'):
        if args[0] == '--verbose':
            options.build_flags.append(build.VERBOSE)
            args = args[1:]
        elif args[0] == '--py2':
            # Use Python 2 mode.
            options.pyversion = 2
            args = args[1:]
        elif args[0] == '-m' and args[1:]:
            options.build_flags.append(build.MODULE)
            return None, args[1], None, options
        elif args[0] == '-c' and args[1:]:
            options.build_flags.append(build.PROGRAM_TEXT)
            return None, None, args[1], options
        elif args[0] in ('-h', '--help'):
            help = True
            args = args[1:]
        elif args[0] == '--stats':
            options.build_flags.append('dump-type-stats')
            args = args[1:]
        elif args[0] == '--inferstats':
            options.build_flags.append('dump-infer-stats')
            args = args[1:]
        elif args[0] == '--custom-typing' and args[1:]:
            options.custom_typing_module = args[1]
            args = args[2:]
        elif args[0] == '--html-report' and args[1:]:
            options.html_report_dir = args[1]
            options.build_flags.append('html-report')
            args = args[2:]
        elif args[0] == '--use-python-path':
            options.python_path = True
            args = args[1:]
        elif args[0] == '--version':
            ver = True
            args = args[1:]
        else:
            usage('Unknown option: {}'.format(args[0]))

    if help:
        usage()

    if ver:
        version()

    if not args:
        usage('Missing target file or module')

    if args[1:]:
        usage('Extra argument: {}'.format(args[1]))

    if options.python_path and options.pyversion == 2:
        usage('--py2 specified, '
              'but --use-python-path will search in sys.path of Python 3')

    return args[0], None, None, options


def usage(msg: str = None) -> None:
    if msg:
        sys.stderr.write('%s\n' % msg)
        sys.stderr.write("""\
usage: mypy [option ...] [-m mod | file]
Try 'mypy -h' for more information.
""")
    else:
        sys.stderr.write("""\
usage: mypy [option ...] [-m mod | file]

Optional arguments:
  -h, --help         print this help message and exit
  --html-report dir  generate a HTML report of type precision under dir/
  -m mod             type check module
  -c string          type check string
  --verbose          more verbose messages
  --use-python-path  search for modules in sys.path of running Python
  --version          show the current version information

Environment variables:
  MYPYPATH     additional module search path
""")
    sys.exit(2)


def version() -> None:
    sys.stdout.write("mypy {}\n".format(__version__))
    exit(0)


def fail(msg: str) -> None:
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)
