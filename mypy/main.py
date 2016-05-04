"""Mypy type checker command line tool."""

import argparse
import os
import re
import sys

from typing import Optional, Dict, List, Set, Tuple

from mypy import build
from mypy import defaults
from mypy import git
from mypy.build import BuildSource, BuildResult, PYTHON_EXTENSIONS
from mypy.errors import CompileError, set_drop_into_pdb

from mypy.version import __version__

PY_EXTENSIONS = tuple(PYTHON_EXTENSIONS)


class Options:
    """Options collected from flags."""

    def __init__(self) -> None:
        # Set default options.
        self.target = build.TYPE_CHECK
        self.build_flags = []  # type: List[str]
        self.pyversion = defaults.PYTHON3_VERSION
        self.custom_typing_module = None  # type: str
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
    sources, options = process_options()
    if options.pdb:
        set_drop_into_pdb(True)
    if not options.dirty_stubs:
        git.verify_git_integrity_or_abort(build.default_data_dir(bin_dir))
    f = sys.stdout
    try:
        if options.target == build.TYPE_CHECK:
            res = type_check_only(sources, bin_dir, options)
            a = res.errors
        else:
            raise RuntimeError('unsupported target %d' % options.target)
    except CompileError as e:
        a = e.messages
        if not e.use_stdout:
            f = sys.stderr
    if a:
        for m in a:
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
        bin_dir: str, options: Options) -> BuildResult:
    # Type-check the program and dependencies and translate to Python.
    return build.build(sources=sources,
                       target=build.TYPE_CHECK,
                       bin_dir=bin_dir,
                       pyversion=options.pyversion,
                       custom_typing_module=options.custom_typing_module,
                       report_dirs=options.report_dirs,
                       flags=options.build_flags,
                       python_path=options.python_path)


FOOTER = """environment variables:
MYPYPATH     additional module search path"""


def process_options() -> Tuple[List[BuildSource], Options]:
    """Process command line arguments.

    Return (mypy program path (or None),
            module to run as script (or None),
            parsed flags)
    """

    # Make the help output a little less jarring.
    help_factory = (lambda prog:
                    argparse.RawDescriptionHelpFormatter(prog=prog, max_help_position=28))
    parser = argparse.ArgumentParser(prog='mypy', epilog=FOOTER,
                                     formatter_class=help_factory)

    def parse_version(v):
        m = re.match(r'\A(\d)\.(\d+)\Z', v)
        if m:
            return int(m.group(1)), int(m.group(2))
        else:
            raise argparse.ArgumentTypeError(
                "Invalid python version '{}' (expected format: 'x.y')".format(v))

    parser.add_argument('-v', '--verbose', action='count', help="more verbose messages")
    parser.add_argument('-V', '--version', action='version',  # type: ignore # see typeshed#124
                        version='%(prog)s ' + __version__)
    parser.add_argument('--python-version', type=parse_version, metavar='x.y',
                        help='use Python x.y')
    parser.add_argument('--py2', dest='python_version', action='store_const',
                        const=defaults.PYTHON2_VERSION, help="use Python 2 mode")
    parser.add_argument('-s', '--silent-imports', action='store_true',
                        help="don't follow imports to .py files")
    parser.add_argument('--silent', action='store_true',
                        help="deprecated name for --silent-imports")
    parser.add_argument('--almost-silent', action='store_true',
                        help="like --silent-imports but reports the imports as errors")
    parser.add_argument('--disallow-untyped-calls', action='store_true',
                        help="disallow calling functions without type annotations"
                        " from functions with type annotations")
    parser.add_argument('--disallow-untyped-defs', action='store_true',
                        help="disallow defining functions without type annotations"
                        " or with incomplete type annotations")
    parser.add_argument('--check-untyped-defs', action='store_true',
                        help="type check the interior of functions without type annotations")
    parser.add_argument('--fast-parser', action='store_true',
                        help="enable experimental fast parser")
    parser.add_argument('-i', '--incremental', action='store_true',
                        help="enable experimental module cache")
    parser.add_argument('-f', '--dirty-stubs', action='store_true',
                        help="don't warn if typeshed is out of sync")
    parser.add_argument('--pdb', action='store_true', help="invoke pdb on fatal error")
    parser.add_argument('--use-python-path', action='store_true',
                        help="an anti-pattern")
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
    report_group.add_argument('--linecount-report', metavar='DIR')

    code_group = parser.add_argument_group(title='How to specify the code to type check')
    code_group.add_argument('-m', '--module', action='append', dest='modules',
                            help="type-check module; can repeat for more modules")
    # TODO: `mypy -c A -c B` and `mypy -p A -p B` currently silently
    # ignore A (last option wins).  Perhaps -c, -m and -p could just
    # be command-line flags that modify how we interpret self.files?
    code_group.add_argument('-c', '--command', help="type-check program passed in as string")
    code_group.add_argument('-p', '--package', help="type-check all files in a directory")
    code_group.add_argument('files', nargs='*', help="type-check given files or directories")

    args = parser.parse_args()

    # --use-python-path is no longer supported; explain why.
    if args.use_python_path:
        parser.error("Sorry, --use-python-path is no longer supported.\n"
                     "If you are trying this because your code depends on a library module,\n"
                     "you should really investigate how to obtain stubs for that module.\n"
                     "See https://github.com/python/mypy/issues/1411 for more discussion."
                     )
    # --silent is deprecated; warn about this.
    if args.silent:
        print("Warning: --silent is deprecated; use --silent-imports",
              file=sys.stderr)

    # Check for invalid argument combinations.
    code_methods = sum(bool(c) for c in [args.modules, args.command, args.package, args.files])
    if code_methods == 0:
        parser.error("Missing target module, package, files, or command.")
    elif code_methods > 1:
        parser.error("May only specify one of: module, package, files, or command.")

    if args.use_python_path and args.python_version and args.python_version[0] == 2:
        parser.error('Python version 2 (or --py2) specified, '
                     'but --use-python-path will search in sys.path of Python 3')

    # Set options.
    options = Options()
    options.dirty_stubs = args.dirty_stubs
    options.python_path = args.use_python_path
    options.pdb = args.pdb
    options.custom_typing_module = args.custom_typing

    # Set build flags.
    if args.python_version is not None:
        options.pyversion = args.python_version

    if args.verbose:
        options.build_flags.extend(args.verbose * [build.VERBOSE])

    if args.stats:
        options.build_flags.append(build.DUMP_TYPE_STATS)

    if args.inferstats:
        options.build_flags.append(build.DUMP_INFER_STATS)

    if args.silent_imports or args.silent:
        options.build_flags.append(build.SILENT_IMPORTS)
    if args.almost_silent:
        options.build_flags.append(build.SILENT_IMPORTS)
        options.build_flags.append(build.ALMOST_SILENT)

    if args.disallow_untyped_calls:
        options.build_flags.append(build.DISALLOW_UNTYPED_CALLS)

    if args.disallow_untyped_defs:
        options.build_flags.append(build.DISALLOW_UNTYPED_DEFS)

    if args.check_untyped_defs:
        options.build_flags.append(build.CHECK_UNTYPED_DEFS)

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
    if args.modules:
        options.build_flags.append(build.MODULE)
        targets = [BuildSource(None, m, None) for m in args.modules]
        return targets, options
    elif args.package:
        if os.sep in args.package or os.altsep and os.altsep in args.package:
            fail("Package name '{}' cannot have a slash in it."
                 .format(args.package))
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
    """Convert a directory name to a list of sources to build.

    This always recursively walks through the directory and collects
    all .py[i] files, with the exception that if both foo.py and
    foo.pyi exist, we only use foo.pyi; and another exception is that
    if both directory foo/ and one or both of foo.py[i] exist,
    directory foo/ wins (so foo.py[i] are both ignored in that case).

    The tricky bit is how to map filenames to module names.

    There are two cases to consider.

    1) The argument directory is a package, i.e. it has an
       __init__.py[i].  In this case we crawl up until we find a
       parent without __init__.py[i], and determine the module name
       relative to that point (considering the highest directory with
       a __init__.py[i] as the toplevel package).

    2) The argument directory has no __init__.py[i].  In this case we
       consider every .py[i] file and subpackage a toplevel module
       or package.

    Note that in either case, once we're decided on a toplevel package
    name, only subdirectories with __init__.py[i] files are searched.
    """
    assert os.path.isdir(arg), arg
    arg = os.path.abspath(arg)
    for ext in PY_EXTENSIONS:
        f = os.path.join(arg, '__init__' + ext)
        if os.path.exists(f):
            top_dir = crawl_up(f)[0]
            break
    else:
        top_dir = arg

    mods = set()  # type: Set[str]
    sources = []
    for root, dirs, files in os.walk(arg):
        # Sort dirs and files in place to create a stable order.
        dirs.sort()
        files.sort()
        # Look for dirs that are packages.
        packages = []
        for pkg in dirs:
            d = os.path.join(root, pkg)
            for ext in PY_EXTENSIONS:
                f = os.path.join(d, '__init__' + ext)
                mod = make_mod(top_dir, f, ext)
                if os.path.exists(f):
                    if mod not in mods:
                        sources.append(BuildSource(f, mod, None))
                        mods.add(mod)
                        packages.append(pkg)
                        break
        # Only descend into packages.
        dirs[:] = packages
        # Add modules at this level.  Note that (like Python) if
        # both foo.py and foo/__init__.py exist, the package wins.
        for ext in PY_EXTENSIONS:
            # Note that .pyi gets preferred over .py because it
            # comes first in PY_EXTENSIONS.
            for f in files:
                f = os.path.join(root, f)
                if f.endswith(ext):
                    mod = make_mod(top_dir, f, ext)
                    if mod not in mods:
                        sources.append(BuildSource(f, mod, None))
                        mods.add(mod)
    if not sources:
        fail("There are no .py[i] files in directory '{}'".format(arg))
    return sources


def make_mod(dir: str, file: str, ext: str) -> str:
    """Produce the correct module name."""
    assert file.startswith(dir), (dir, file)
    assert file.endswith(ext), (file, ext)
    file = file[len(dir):len(file) - len(ext)]
    if os.altsep:
        file = file.replace(os.altsep, os.sep)
    if file.startswith(os.sep):
        file = file[1:]
    mod = file.replace(os.sep, '.')
    if mod.endswith('.__init__'):
        mod = mod[:-9]  # len('.__init__')
    return mod


def crawl_up(arg: str) -> Tuple[str, str]:
    """Given a .py[i] filename, return (root directory, module).

    We crawl up the path until we find a directory without
    __init__.py[i], or until we run out of path components.
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
