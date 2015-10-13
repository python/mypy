"""Mypy type checker command line tool."""

import os
import os.path
import shutil
import subprocess
import sys
import tempfile

import typing
from typing import Dict, List, Tuple

from mypy import build
from mypy.syntax.dialect import Implementation, default_implementation
from mypy.errors import CompileError

from mypy.version import __version__


class Options:
    def __init__(self) -> None:
        # Set default options.
        self.target = build.TYPE_CHECK
        self.build_flags = []  # type: List[str]
        self.implementation = None  # type: Implementation
        self.custom_typing_module = None  # type: str
        self.report_dirs = {}  # type: Dict[str, str]
        self.python_path = False


def main() -> None:
    path, module, program_text, options = process_options(sys.argv[1:])
    try:
        if options.target == build.TYPE_CHECK:
            type_check_only(path, module, program_text, options)
        else:
            raise RuntimeError('unsupported target %d' % options.target)
    except CompileError as e:
        for m in e.messages:
            sys.stderr.write(m + '\n')
        sys.exit(1)


def readlinkabs(link: str) -> str:
    """Return an absolute path to symbolic link destination."""
    # Adapted from code by Greg Smith.
    assert os.path.islink(link)
    path = os.readlink(link)
    if os.path.isabs(path):
        return path
    return os.path.join(os.path.dirname(link), path)


def type_check_only(path: str, module: str, program_text: str,
        options: Options) -> None:
    # Type check the program and dependencies and translate to Python.
    build.build(path,
                module=module,
                program_text=program_text,
                target=build.TYPE_CHECK,
                implementation=options.implementation,
                custom_typing_module=options.custom_typing_module,
                report_dirs=options.report_dirs,
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
    python_executable = None  # type: str
    force_py2 = False

    while args and args[0].startswith('-'):
        if args[0] == '--verbose':
            options.build_flags.append(build.VERBOSE)
            args = args[1:]
        elif args[0] == '--py2':
            # Use Python 2 mode.
            force_py2 = True
            args = args[1:]
        elif args[0] == '--python-executable':
            if len(args) < 2:
                fail('argument required')
            python_executable = args[1]
            args = args[2:]
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
            options.build_flags.append(build.DUMP_TYPE_STATS)
            args = args[1:]
        elif args[0] == '--inferstats':
            options.build_flags.append(build.DUMP_INFER_STATS)
            args = args[1:]
        elif args[0] == '--custom-typing' and args[1:]:
            options.custom_typing_module = args[1]
            args = args[2:]
        elif is_report(args[0]) and args[1:]:
            report_type = args[0][2:-7]
            report_dir = args[1]
            options.report_dirs[report_type] = report_dir
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

    if python_executable is not None:
        options.implementation = Implementation(python_executable)
        if force_py2 and options.implementation.base_dialect.major != 2:
            usage('given --python-executable is not --py2')
    else:
        options.implementation = default_implementation(force_py2=force_py2)

    return args[0], None, None, options


# Don't generate this from mypy.reports, not all are meant to be public.
REPORTS = [
    'html',
    'old-html',
    'xslt-html',
    'xml',
    'txt',
    'xslt-txt',
]


def is_report(arg: str) -> bool:
    if arg.startswith('--') and arg.endswith('-report'):
        report_type = arg[2:-7]
        return report_type in REPORTS
    return False


def usage(msg: str = None) -> None:
    if msg:
        sys.stderr.write('%s\n' % msg)
        sys.stderr.write("""\
usage: mypy [option ...] [-c cmd | -m mod | file]
Try 'mypy -h' for more information.
""")
    else:
        sys.stderr.write("""\
usage: mypy [option ...] [-m mod | file]

Optional arguments:
  -h, --help         print this help message and exit
  --<fmt>-report dir generate a <fmt> report of type precision under dir/
                     <fmt> may be one of: %s
  -m mod             type check module
  -c string          type check program passed in as string
  --verbose          more verbose messages
  --use-python-path  search for modules in sys.path of running Python
  --version          show the current version information
  --python-executable    emulate this python interpreter
  --py2              deprecated, automatically find a python2 interpreter

Environment variables:
  MYPYPATH     additional module search path
  MYPY_PYTHON  interpreter to emulate
""" % ', '.join(REPORTS))
    sys.exit(2)


def version() -> None:
    sys.stdout.write("mypy {}\n".format(__version__))
    exit(0)


def fail(msg: str) -> None:
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)
