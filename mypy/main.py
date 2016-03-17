"""Mypy type checker command line tool."""

import argparse
import os
import sys
import textwrap

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
        f = sys.stdout if e.use_stdout else sys.stderr
        for m in e.messages:
            f.write(m + '\n')
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

    footer = textwrap.dedent(
        """environment variables:
        MYPYPATH     additional module search path"""
    )

    parser = argparse.ArgumentParser(prog='mypy', epilog=footer,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    def parse_version(v):
        version_components = v.split(".")[0:2]
        if len(version_components) != 2:
            raise argparse.ArgumentTypeError(
                "Invalid python version '{}' (expected format: 'x.y')".format(v))
        if not all(item.isdigit() for item in version_components):
            raise argparse.ArgumentTypeError("Found non-digit in python version: '{}'".format(v))
        return (int(version_components[0]), int(version_components[1]))

    parser.add_argument('-v', '--verbose', action='store_true', help="more verbose messages")
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('--python-version', type=parse_version, metavar='x.y',
                        help='use Python x.y')
    parser.add_argument('--py2', action='store_true', help="use Python 2 mode")
    parser.add_argument('-s', '--silent-imports', '--silent', action='store_true',
                        help="don't follow imports to .py files")
    parser.add_argument('--disallow-untyped-calls', action='store_true',
                        help="disallow calling functions without type annotations"
                        " from functions with type annotations")
    parser.add_argument('--disallow-untyped-defs', action='store_true',
                        help="disallow defining functions without type annotations"
                        " or with incomplete type annotations")
    parser.add_argument('--implicit-any', action='store_true',
                        help="behave as though all functions were annotated with Any")
    parser.add_argument('--fast-parser', action='store_true',
                        help="enable experimental fast parser")
    parser.add_argument('-i', '--incremental', action='store_true',
                        help="enable experimental module cache")
    parser.add_argument('-f', '--dirty-stubs', action='store_true',
                        help="don't warn if typeshed is out of sync")
    parser.add_argument('--pdb', action='store_true', help="invoke pdb on fatal error")
    parser.add_argument('--use-python-path', action='store_true',
                        help="search for modules in sys.path of running Python")
    parser.add_argument('--stats', action='store_true', help="dump stats")
    parser.add_argument('--inferstats', action='store_true', help="dump type inference stats")
    parser.add_argument('--custom-typing', metavar='MODULE', help="use a custom typing module")

    report_group = parser.add_argument_group(
        title='report generation',
        description='Generate a report in the specified format.')
    report_group.add_argument('--html-report', metavar='DIR')
    report_group.add_argument('--old-html-report', metavar='DIR')
    report_group.add_argument('--xslt-html-report', metavar='DIR')
    report_group.add_argument('--xml-report', metavar='DIR')
    report_group.add_argument('--txt-report', metavar='DIR')
    report_group.add_argument('--xslt-txt-report', metavar='DIR')

    code_group = parser.add_argument_group(title='How to specify the code to type check')
    code_group.add_argument('-m', '--module', help="type-check module (may be a dotted name)")
    code_group.add_argument('-c', '--command', help="type-check program passed in as string")
    code_group.add_argument('-p', '--package', help="type-check all files in a directory")
    code_group.add_argument('files', nargs='*', help="type-check given files or directories")

    args = parser.parse_args()

    # Check for invalid argument combinations.
    code_methods = sum(bool(c) for c in [args.module, args.command, args.package, args.files])
    if code_methods == 0:
        parser.error("Missing target module, package, files, or command.")
    elif code_methods > 1:
        parser.error("May only specify one of: module, package, files, or command.")

    if args.use_python_path and args.python_version and args.python_version[0] == 2:
        parser.error('Python version 2 (or --py2) specified, '
                     'but --use-python-path will search in sys.path of Python 3')

    if args.fast_parser and (args.py2 or
                             args.python_version and args.python_version[0] == 2):
        parser.error('The experimental fast parser is only compatible with Python 3, '
                     'but Python 2 specified.')

    # Set options.
    options = Options()
    options.dirty_stubs = args.dirty_stubs
    options.python_path = args.use_python_path
    options.pdb = args.pdb
    options.implicit_any = args.implicit_any
    options.custom_typing_module = args.custom_typing

    # Set build flags.
    if args.py2:
        options.pyversion = defaults.PYTHON2_VERSION

    if args.python_version is not None:
        options.pyversion = args.python_version

    if args.verbose:
        options.build_flags.append(build.VERBOSE)

    if args.stats:
        options.build_flags.append(build.DUMP_TYPE_STATS)

    if args.inferstats:
        options.build_flags.append(build.DUMP_INFER_STATS)

    if args.silent_imports:
        options.build_flags.append(build.SILENT_IMPORTS)

    if args.disallow_untyped_calls:
        options.build_flags.append(build.DISALLOW_UNTYPED_CALLS)

    if args.disallow_untyped_defs:
        options.build_flags.append(build.DISALLOW_UNTYPED_DEFS)

    # experimental
    if args.fast_parser:
        options.build_flags.append(build.FAST_PARSER)
    if args.incremental:
        options.build_flags.append(build.INCREMENTAL)

    # Set reports.
    for flag, val in vars(args).items():
        if flag.endswith('_report') and val is not None:
            report_type = flag[:-7].replace('_', '-')
            report_dir = val
            options.report_dirs[report_type] = report_dir

    # Set target.
    if args.module:
        options.build_flags.append(build.MODULE)
        return [BuildSource(None, args.module, None)], options
    elif args.package:
        options.build_flags.append(build.MODULE)
        lib_path = [os.getcwd()] + build.mypy_path()
        targets = build.find_modules_recursive(args.package, lib_path)
        if not targets:
            fail("Can't find package '{}'".format(args.package))
        return targets, options
    elif args.command:
        options.build_flags.append(build.PROGRAM_TEXT)
        return [BuildSource(None, None, args.command)], options
    else:
        targets = []
        for f in args.files:
            if f.endswith(PY_EXTENSIONS):
                targets.append(BuildSource(f, crawl_up(f)[1], None))
            elif os.path.isdir(f):
                targets.extend(expand_dir(f))
            else:
                targets.append(BuildSource(f, None, None))
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


def fail(msg: str) -> None:
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)
