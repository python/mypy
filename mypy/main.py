"""Mypy type checker command line tool."""

import argparse
import os
import re
import sys

from typing import Any, Dict, List, Optional, Set, Tuple

from mypy import build
from mypy import defaults
from mypy import git
from mypy import experiments
from mypy.build import BuildSource, BuildResult, PYTHON_EXTENSIONS
from mypy.errors import CompileError, set_drop_into_pdb, set_show_tb
from mypy.options import Options, BuildType

from mypy.version import __version__

PY_EXTENSIONS = tuple(PYTHON_EXTENSIONS)


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
    if options.show_traceback:
        set_show_tb(True)
    f = sys.stdout
    try:
        res = type_check_only(sources, bin_dir, options)
        a = res.errors
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
                       bin_dir=bin_dir,
                       options=options)


FOOTER = """environment variables:
MYPYPATH     additional module search path"""


class SplitNamespace(argparse.Namespace):
    def __init__(self, standard_namespace: object, alt_namespace: object, alt_prefix: str) -> None:
        self.__dict__['_standard_namespace'] = standard_namespace
        self.__dict__['_alt_namespace'] = alt_namespace
        self.__dict__['_alt_prefix'] = alt_prefix

    def _get(self) -> Tuple[Any, Any]:
        return (self._standard_namespace, self._alt_namespace)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith(self._alt_prefix):
            setattr(self._alt_namespace, name[len(self._alt_prefix):], value)
        else:
            setattr(self._standard_namespace, name, value)

    def __getattr__(self, name: str) -> Any:
        if name.startswith(self._alt_prefix):
            return getattr(self._alt_namespace, name[len(self._alt_prefix):])
        else:
            return getattr(self._standard_namespace, name)


def parse_version(v: str) -> Tuple[int, int]:
    m = re.match(r'\A(\d)\.(\d+)\Z', v)
    if m:
        return int(m.group(1)), int(m.group(2))
    else:
        raise argparse.ArgumentTypeError(
            "Invalid python version '{}' (expected format: 'x.y')".format(v))


def process_options(args: List[str],
                    require_targets: bool = True
                    ) -> Tuple[List[BuildSource], Options]:
    """Parse command line arguments."""

    # Make the help output a little less jarring.
    help_factory = (lambda prog:
                    argparse.RawDescriptionHelpFormatter(prog=prog, max_help_position=28))
    parser = argparse.ArgumentParser(prog='mypy', epilog=FOOTER,
                                     formatter_class=help_factory)

    # Unless otherwise specified, arguments will be parsed directly onto an
    # Options object.  Options that require further processing should have
    # their `dest` prefixed with `special-opts:`, which will cause them to be
    # parsed into the separate special_opts namespace object.
    parser.add_argument('-v', '--verbose', action='count', dest='verbosity',
                        help="more verbose messages")
    parser.add_argument('-V', '--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('--python-version', type=parse_version, metavar='x.y',
                        help='use Python x.y')
    parser.add_argument('--platform', action='store', metavar='PLATFORM',
                        help="typecheck special-cased code for the given OS platform "
                        "(defaults to sys.platform).")
    parser.add_argument('-2', '--py2', dest='python_version', action='store_const',
                        const=defaults.PYTHON2_VERSION, help="use Python 2 mode")
    parser.add_argument('-s', '--silent-imports', action='store_true',
                        help="don't follow imports to .py files")
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
    parser.add_argument('--disallow-subclassing-any', action='store_true',
                        help="disallow subclassing values of type 'Any' when defining classes")
    parser.add_argument('--warn-incomplete-stub', action='store_true',
                        help="warn if missing type annotation in typeshed, only relevant with"
                        " --check-untyped-defs enabled")
    parser.add_argument('--warn-redundant-casts', action='store_true',
                        help="warn about casting an expression to its inferred type")
    parser.add_argument('--warn-unused-ignores', action='store_true',
                        help="warn about unneeded '# type: ignore' comments")
    parser.add_argument('--suppress-error-context', action='store_true',
                        dest='suppress_error_context',
                        help="Suppress context notes before errors")
    parser.add_argument('--fast-parser', action='store_true',
                        help="enable experimental fast parser")
    parser.add_argument('-i', '--incremental', action='store_true',
                        help="enable experimental module cache")
    parser.add_argument('--cache-dir', action='store', metavar='DIR',
                        help="store module cache info in the given folder in incremental mode "
                        "(defaults to '{}')".format(defaults.MYPY_CACHE))
    parser.add_argument('--strict-optional', action='store_true',
                        dest='special-opts:strict_optional',
                        help="enable experimental strict Optional checks")
    parser.add_argument('--strict-optional-whitelist', metavar='GLOB', nargs='*',
                        help="suppress strict Optional errors in all but the provided files "
                        "(experimental -- read documentation before using!).  "
                        "Implies --strict-optional.  Has the undesirable side-effect of "
                        "suppressing other errors in non-whitelisted files.")
    parser.add_argument('--pdb', action='store_true', help="invoke pdb on fatal error")
    parser.add_argument('--show-traceback', '--tb', action='store_true',
                        help="show traceback on fatal error")
    parser.add_argument('--stats', action='store_true', dest='dump_type_stats', help="dump stats")
    parser.add_argument('--inferstats', action='store_true', dest='dump_inference_stats',
                        help="dump type inference stats")
    parser.add_argument('--custom-typing', metavar='MODULE', dest='custom_typing_module',
                        help="use a custom typing module")
    # hidden options
    # --shadow-file a.py tmp.py will typecheck tmp.py in place of a.py.
    # Useful for tools to make transformations to a file to get more
    # information from a mypy run without having to change the file in-place
    # (e.g. by adding a call to reveal_type).
    parser.add_argument('--shadow-file', metavar='PATH', nargs=2, dest='shadow_file',
                        help=argparse.SUPPRESS)
    # --debug-cache will disable any cache-related compressions/optimizations,
    # which will make the cache writing process output pretty-printed JSON (which
    # is easier to debug).
    parser.add_argument('--debug-cache', action='store_true', help=argparse.SUPPRESS)
    # deprecated options
    parser.add_argument('--silent', action='store_true', dest='special-opts:silent',
                        help=argparse.SUPPRESS)
    parser.add_argument('-f', '--dirty-stubs', action='store_true',
                        dest='special-opts:dirty_stubs',
                        help=argparse.SUPPRESS)
    parser.add_argument('--use-python-path', action='store_true',
                        dest='special-opts:use_python_path',
                        help=argparse.SUPPRESS)

    report_group = parser.add_argument_group(
        title='report generation',
        description='Generate a report in the specified format.')
    report_group.add_argument('--html-report', metavar='DIR',
                              dest='special-opts:html_report')
    report_group.add_argument('--old-html-report', metavar='DIR',
                              dest='special-opts:old_html_report')
    report_group.add_argument('--xslt-html-report', metavar='DIR',
                              dest='special-opts:xslt_html_report')
    report_group.add_argument('--xml-report', metavar='DIR',
                              dest='special-opts:xml_report')
    report_group.add_argument('--txt-report', metavar='DIR',
                              dest='special-opts:txt_report')
    report_group.add_argument('--xslt-txt-report', metavar='DIR',
                              dest='special-opts:xslt_txt_report')
    report_group.add_argument('--linecount-report', metavar='DIR',
                              dest='special-opts:linecount_report')
    report_group.add_argument('--linecoverage-report', metavar='DIR',
                              dest='special-opts:linecoverage_report')

    code_group = parser.add_argument_group(title='How to specify the code to type check')
    code_group.add_argument('-m', '--module', action='append', metavar='MODULE',
                            dest='special-opts:modules',
                            help="type-check module; can repeat for more modules")
    # TODO: `mypy -c A -c B` and `mypy -p A -p B` currently silently
    # ignore A (last option wins).  Perhaps -c, -m and -p could just
    # be command-line flags that modify how we interpret self.files?
    code_group.add_argument('-c', '--command', action='append', metavar='PROGRAM_TEXT',
                            dest='special-opts:command',
                            help="type-check program passed in as string")
    code_group.add_argument('-p', '--package', metavar='PACKAGE', dest='special-opts:package',
                            help="type-check all files in a directory")
    code_group.add_argument(metavar='files', nargs='*', dest='special-opts:files',
                            help="type-check given files or directories")

    options = Options()
    special_opts = argparse.Namespace()
    parser.parse_args(args, SplitNamespace(options, special_opts, 'special-opts:'))

    # --use-python-path is no longer supported; explain why.
    if special_opts.use_python_path:
        parser.error("Sorry, --use-python-path is no longer supported.\n"
                     "If you are trying this because your code depends on a library module,\n"
                     "you should really investigate how to obtain stubs for that module.\n"
                     "See https://github.com/python/mypy/issues/1411 for more discussion."
                     )

    # warn about deprecated options
    if special_opts.silent:
        print("Warning: --silent is deprecated; use --silent-imports",
              file=sys.stderr)
        options.silent_imports = True
    if special_opts.dirty_stubs:
        print("Warning: -f/--dirty-stubs is deprecated and no longer necessary. Mypy no longer "
              "checks the git status of stubs.",
              file=sys.stderr)

    # Check for invalid argument combinations.
    if require_targets:
        code_methods = sum(bool(c) for c in [special_opts.modules,
                                            special_opts.command,
                                            special_opts.package,
                                            special_opts.files])
        if code_methods == 0:
            parser.error("Missing target module, package, files, or command.")
        elif code_methods > 1:
            parser.error("May only specify one of: module, package, files, or command.")

    # Set build flags.
    if special_opts.strict_optional or options.strict_optional_whitelist is not None:
        experiments.STRICT_OPTIONAL = True

    # Set reports.
    for flag, val in vars(special_opts).items():
        if flag.endswith('_report') and val is not None:
            report_type = flag[:-7].replace('_', '-')
            report_dir = val
            options.report_dirs[report_type] = report_dir

    # Set target.
    if special_opts.modules:
        options.build_type = BuildType.MODULE
        targets = [BuildSource(None, m, None) for m in special_opts.modules]
        return targets, options
    elif special_opts.package:
        if os.sep in special_opts.package or os.altsep and os.altsep in special_opts.package:
            fail("Package name '{}' cannot have a slash in it."
                 .format(special_opts.package))
        options.build_type = BuildType.MODULE
        lib_path = [os.getcwd()] + build.mypy_path()
        targets = build.find_modules_recursive(special_opts.package, lib_path)
        if not targets:
            fail("Can't find package '{}'".format(special_opts.package))
        return targets, options
    elif special_opts.command:
        options.build_type = BuildType.PROGRAM_TEXT
        return [BuildSource(None, None, '\n'.join(special_opts.command))], options
    else:
        targets = []
        for f in special_opts.files:
            if f.endswith(PY_EXTENSIONS):
                targets.append(BuildSource(f, crawl_up(f)[1], None))
            elif os.path.isdir(f):
                sub_targets = expand_dir(f)
                if not sub_targets:
                    fail("There are no .py[i] files in directory '{}'"
                         .format(f))
                targets.extend(sub_targets)
            else:
                targets.append(BuildSource(f, None, None))
        return targets, options


def keyfunc(name: str) -> Tuple[int, str]:
    """Determines sort order for directory listing.

    The desirable property is foo < foo.pyi < foo.py.
    """
    base, suffix = os.path.splitext(name)
    for i, ext in enumerate(PY_EXTENSIONS):
        if suffix == ext:
            return (i, base)
    return (-1, name)


def expand_dir(arg: str, mod_prefix: str = '') -> List[BuildSource]:
    """Convert a directory name to a list of sources to build."""
    f = get_init_file(arg)
    if mod_prefix and not f:
        return []
    seen = set()  # type: Set[str]
    sources = []
    if f and not mod_prefix:
        top_dir, top_mod = crawl_up(f)
        mod_prefix = top_mod + '.'
    if mod_prefix:
        sources.append(BuildSource(f, mod_prefix.rstrip('.'), None))
    names = os.listdir(arg)
    names.sort(key=keyfunc)
    for name in names:
        path = os.path.join(arg, name)
        if os.path.isdir(path):
            sub_sources = expand_dir(path, mod_prefix + name + '.')
            if sub_sources:
                seen.add(name)
                sources.extend(sub_sources)
        else:
            base, suffix = os.path.splitext(name)
            if base == '__init__':
                continue
            if base not in seen and '.' not in base and suffix in PY_EXTENSIONS:
                seen.add(base)
                src = BuildSource(path, mod_prefix + base, None)
                sources.append(src)
    return sources


def crawl_up(arg: str) -> Tuple[str, str]:
    """Given a .py[i] filename, return (root directory, module).

    We crawl up the path until we find a directory without
    __init__.py[i], or until we run out of path components.
    """
    dir, mod = os.path.split(arg)
    mod = strip_py(mod) or mod
    assert '.' not in mod
    while dir and get_init_file(dir):
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


def get_init_file(dir: str) -> Optional[str]:
    """Check whether a directory contains a file named __init__.py[i].

    If so, return the file's name (with dir prefixed).  If not, return
    None.

    This prefers .pyi over .py (because of the ordering of PY_EXTENSIONS).
    """
    for ext in PY_EXTENSIONS:
        f = os.path.join(dir, '__init__' + ext)
        if os.path.isfile(f):
            return f
    return None


def fail(msg: str) -> None:
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)
