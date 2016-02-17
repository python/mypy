"""Mypy type checker command line tool."""

import os
import shutil
import subprocess
import sys
import tempfile

import typing
from typing import Optional, Dict, List, Tuple

from mypy import build
from mypy import defaults
from mypy import git
from mypy.build import BuildSource, PYTHON_EXTENSIONS
from mypy.errors import CompileError, set_drop_into_pdb

from mypy.version import __version__

PY_EXTENSIONS = tuple(PYTHON_EXTENSIONS)


class Options:
    def __init__(self) -> None:
        # Set default options.
        self.target = build.TYPE_CHECK
        self.build_flags = []  # type: List[str]
        self.pyversion = defaults.PYTHON3_VERSION
        self.custom_typing_module = None  # type: str
        self.implicit_any = False
        self.report_dirs = {}  # type: Dict[str, str]
        self.python_path = False
        self.dirty_stubs = False
        self.pdb = False


def main(script_path: str) -> None:
    """Main entry point to the type checker.

    Args:
        script_path: Path to the 'mypy' script (used for finding data files).
    """
    if script_path:
        bin_dir = find_bin_directory(script_path)
    else:
        bin_dir = None
    sources, options = process_options(sys.argv[1:])
    if options.pdb:
        set_drop_into_pdb(True)
    if not options.dirty_stubs:
        git.verify_git_integrity_or_abort(build.default_data_dir(bin_dir))
    try:
        if options.target == build.TYPE_CHECK:
            type_check_only(sources, bin_dir, options)
        else:
            raise RuntimeError('unsupported target %d' % options.target)
    except CompileError as e:
        for m in e.messages:
            sys.stdout.write(m + '\n')
        sys.exit(1)


def find_bin_directory(script_path: str) -> str:
    """Find the directory that contains this script.

    This is used by build to find stubs and other data files.
    """
    # Follow up to 5 symbolic links (cap to avoid cycles).
    for i in range(5):
        if os.path.islink(script_path):
            script_path = readlinkabs(script_path)
        else:
            break
    return os.path.dirname(script_path)


def readlinkabs(link: str) -> str:
    """Return an absolute path to symbolic link destination."""
    # Adapted from code by Greg Smith.
    assert os.path.islink(link)
    path = os.readlink(link)
    if os.path.isabs(path):
        return path
    return os.path.join(os.path.dirname(link), path)


def type_check_only(sources: List[BuildSource],
        bin_dir: str, options: Options) -> None:
    # Type-check the program and dependencies and translate to Python.
    build.build(sources=sources,
                target=build.TYPE_CHECK,
                bin_dir=bin_dir,
                pyversion=options.pyversion,
                custom_typing_module=options.custom_typing_module,
                implicit_any=options.implicit_any,
                report_dirs=options.report_dirs,
                flags=options.build_flags,
                python_path=options.python_path)


def process_options(args: List[str]) -> Tuple[List[BuildSource], Options]:
    """Process command line arguments.

    Return (mypy program path (or None),
            module to run as script (or None),
            parsed flags)
    """
    # TODO: Rewrite using argparse.
    options = Options()
    help = False
    ver = False
    while args and args[0].startswith('-'):
        if args[0] == '--verbose':
            options.build_flags.append(build.VERBOSE)
            args = args[1:]
        elif args[0] == '--py2':
            # Use Python 2 mode.
            options.pyversion = defaults.PYTHON2_VERSION
            args = args[1:]
        elif args[0] == '--python-version':
            version_components = args[1].split(".")[0:2]
            if len(version_components) != 2:
                fail("Invalid python version {} (expected format: 'x.y')".format(
                    repr(args[1])))
            if not all(item.isdigit() for item in version_components):
                fail("Found non-digit in python version: {}".format(
                    args[1]))
            options.pyversion = (int(version_components[0]), int(version_components[1]))
            args = args[2:]
        elif args[0] == '-f' or args[0] == '--dirty-stubs':
            options.dirty_stubs = True
            args = args[1:]
        elif args[0] == '-m' and args[1:]:
            options.build_flags.append(build.MODULE)
            return [BuildSource(None, args[1], None)], options
        elif args[0] == '--package' and args[1:]:
            options.build_flags.append(build.MODULE)
            lib_path = [os.getcwd()] + build.mypy_path()
            targets = build.find_modules_recursive(args[1], lib_path)
            if not targets:
                fail("Can't find package '{}'".format(args[1]))
            return targets, options
        elif args[0] == '-c' and args[1:]:
            options.build_flags.append(build.PROGRAM_TEXT)
            return [BuildSource(None, None, args[1])], options
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
        elif args[0] in ('--silent-imports', '--silent'):
            options.build_flags.append(build.SILENT_IMPORTS)
            args = args[1:]
        elif args[0] == '--pdb':
            options.pdb = True
            args = args[1:]
        elif args[0] == '--implicit-any':
            options.implicit_any = True
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

    if options.python_path and options.pyversion[0] == 2:
        usage('Python version 2 (or --py2) specified, '
              'but --use-python-path will search in sys.path of Python 3')

    targets = []
    for arg in args:
        if arg.endswith(PY_EXTENSIONS):
            targets.append(BuildSource(arg, crawl_up(arg)[1], None))
        elif os.path.isdir(arg):
            targets.extend(expand_dir(arg))
        else:
            targets.append(BuildSource(arg, None, None))
    return targets, options


def expand_dir(arg: str) -> List[BuildSource]:
    """Convert a directory name to a list of sources to build."""
    dir, mod = crawl_up(arg)
    if not mod:
        # It's a directory without an __init__.py[i].
        # List all the .py[i] files (but not recursively).
        targets = []  # type: List[BuildSource]
        for name in os.listdir(dir):
            stripped = strip_py(name)
            if stripped:
                path = os.path.join(dir, name)
                targets.append(BuildSource(path, stripped, None))
        if not targets:
            fail("There are no .py[i] files in directory '{}'".format(arg))
        return targets

    else:
        lib_path = [dir]
        targets = build.find_modules_recursive(mod, lib_path)
        if not targets:
            fail("Found no modules in package '{}'".format(arg))
        return targets


def crawl_up(arg: str) -> Tuple[str, str]:
    """Given a .py[i] filename, return (root directory, module).

    We crawl up the path until we find a directory without __init__.py[i].
    """
    dir, mod = os.path.split(arg)
    mod = strip_py(mod) or mod
    assert '.' not in mod
    while dir and has_init_file(dir):
        dir, base = os.path.split(dir)
        if not base:
            break
        if mod == '__init__' or not mod:
            mod = base
        else:
            mod = base + '.' + mod
    return dir, mod


def strip_py(arg: str) -> Optional[str]:
    """Strip a trailing .py or .pyi suffix.

    Return None if no such suffix is found.
    """
    for ext in PY_EXTENSIONS:
        if arg.endswith(ext):
            return arg[:-len(ext)]
    return None


def has_init_file(dir: str) -> bool:
    """Return whether a directory contains a file named __init__.py[i]."""
    for ext in PY_EXTENSIONS:
        if os.path.isfile(os.path.join(dir, '__init__' + ext)):
            return True
    return False


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
usage: mypy [option ...] [-c cmd | -m mod | file_or_dir ...]
Try 'mypy -h' for more information.
""")
        sys.exit(2)
    else:
        sys.stdout.write("""\
usage: mypy [option ...] [-c cmd | -m mod | file_or_dir ...]

Options:
  -h, --help         print this help message and exit
  --version          show the current version information and exit
  --verbose          more verbose messages
  --py2              use Python 2 mode
  --python-version x.y  use Python x.y
  --silent, --silent-imports  don't follow imports to .py files
  -f, --dirty-stubs  don't warn if typeshed is out of sync
  --implicit-any     behave as though all functions were annotated with Any
  --pdb              invoke pdb on fatal error
  --use-python-path  search for modules in sys.path of running Python
  --stats            dump stats
  --inferstats       dump type inference stats
  --custom-typing mod  use a custom typing module
  --<fmt>-report dir generate a <fmt> report of type precision under dir/
                     <fmt> may be one of: %s

How to specify the code to type-check:
  -m mod             type-check module (may be a dotted name)
  -c string          type-check program passed in as string
  --package dir      type-check all files in a directory
  file ...           type-check given files
  dir ...            type-check all files in given directories

Environment variables:
  MYPYPATH     additional module search path
""" % ', '.join(REPORTS))
        sys.exit(0)


def version() -> None:
    sys.stdout.write("mypy {}\n".format(__version__))
    sys.exit(0)


def fail(msg: str) -> None:
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)
