"""Mypy type checker command line tool."""

import argparse
import ast
import configparser
import os
import re
import subprocess
import sys
import time

from typing import Any, Dict, List, Mapping, Optional, Tuple, Callable

from mypy import build
from mypy import defaults
from mypy import experiments
from mypy import util
from mypy.build import BuildSource, BuildResult
from mypy.find_sources import create_source_list, InvalidSourceList
from mypy.fscache import FileSystemCache
from mypy.errors import CompileError
from mypy.options import Options, BuildType
from mypy.report import reporter_classes

from mypy.version import __version__


orig_stat = os.stat

MEM_PROFILE = False  # If True, dump memory profile


def stat_proxy(path: str) -> os.stat_result:
    try:
        st = orig_stat(path)
    except os.error as err:
        print("stat(%r) -> %s" % (path, err))
        raise
    else:
        print("stat(%r) -> (st_mode=%o, st_mtime=%d, st_size=%d)" %
              (path, st.st_mode, st.st_mtime, st.st_size))
        return st


def main(script_path: Optional[str], args: Optional[List[str]] = None) -> None:
    """Main entry point to the type checker.

    Args:
        script_path: Path to the 'mypy' script (used for finding data files).
        args: Custom command-line arguments.  If not given, sys.argv[1:] will
        be used.
    """
    # Check for known bad Python versions.
    if sys.version_info[:2] < (3, 4):
        sys.exit("Running mypy with Python 3.3 or lower is not supported; "
                 "please upgrade to 3.4 or newer")
    if sys.version_info[:3] == (3, 5, 0):
        sys.exit("Running mypy with Python 3.5.0 is not supported; "
                 "please upgrade to 3.5.1 or newer")

    t0 = time.time()
    # To log stat() calls: os.stat = stat_proxy
    if script_path:
        bin_dir = find_bin_directory(script_path)  # type: Optional[str]
    else:
        bin_dir = None
    sys.setrecursionlimit(2 ** 14)
    if args is None:
        args = sys.argv[1:]

    fscache = FileSystemCache()
    sources, options = process_options(args, fscache=fscache)

    messages = []

    def flush_errors(new_messages: List[str], serious: bool) -> None:
        messages.extend(new_messages)
        f = sys.stderr if serious else sys.stdout
        try:
            for msg in new_messages:
                f.write(msg + '\n')
            f.flush()
        except BrokenPipeError:
            sys.exit(2)

    serious = False
    blockers = False
    try:
        # Keep a dummy reference (res) for memory profiling below, as otherwise
        # the result could be freed.
        res = type_check_only(sources, bin_dir, options, flush_errors, fscache)  # noqa
    except CompileError as e:
        blockers = True
        if not e.use_stdout:
            serious = True
    if options.warn_unused_configs and options.unused_configs:
        print("Warning: unused section(s) in %s: %s" %
              (options.config_file,
               ", ".join("[mypy-%s]" % glob for glob in options.per_module_options.keys()
                         if glob in options.unused_configs)),
              file=sys.stderr)
    if options.junit_xml:
        t1 = time.time()
        util.write_junit_xml(t1 - t0, serious, messages, options.junit_xml)

    if MEM_PROFILE:
        from mypy.memprofile import print_memory_profile
        print_memory_profile()

    if messages:
        code = 2 if blockers else 1
        sys.exit(code)


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


def type_check_only(sources: List[BuildSource], bin_dir: Optional[str],
                    options: Options,
                    flush_errors: Optional[Callable[[List[str], bool], None]],
                    fscache: FileSystemCache) -> BuildResult:
    # Type-check the program and dependencies.
    return build.build(sources=sources,
                       bin_dir=bin_dir,
                       options=options,
                       flush_errors=flush_errors,
                       fscache=fscache)


FOOTER = "environment variables: Define MYPYPATH for additional module search path entries."


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
    if not m:
        raise argparse.ArgumentTypeError(
            "Invalid python version '{}' (expected format: 'x.y')".format(v))
    major, minor = int(m.group(1)), int(m.group(2))
    if major == 2:
        if minor != 7:
            raise argparse.ArgumentTypeError(
                "Python 2.{} is not supported (must be 2.7)".format(minor))
    elif major == 3:
        if minor < defaults.PYTHON3_VERSION_MIN[1]:
            raise argparse.ArgumentTypeError(
                "Python 3.{0} is not supported (must be {1}.{2} or higher)".format(minor,
                                                                    *defaults.PYTHON3_VERSION_MIN))
    else:
        raise argparse.ArgumentTypeError(
            "Python major version '{}' out of range (must be 2 or 3)".format(major))
    return major, minor


# Make the help output a little less jarring.
class AugmentedHelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog=prog, max_help_position=28)


# Define pairs of flag prefixes with inverse meaning.
flag_prefix_pairs = [
    ('allow', 'disallow'),
    ('show', 'hide'),
]
flag_prefix_map = {}  # type: Dict[str, str]
for a, b in flag_prefix_pairs:
    flag_prefix_map[a] = b
    flag_prefix_map[b] = a


def invert_flag_name(flag: str) -> str:
    split = flag[2:].split('-', 1)
    if len(split) == 2:
        prefix, rest = split
        if prefix in flag_prefix_map:
            return '--{}-{}'.format(flag_prefix_map[prefix], rest)
        elif prefix == 'no':
            return '--{}'.format(rest)

    return '--no-{}'.format(flag[2:])


class PythonExecutableInferenceError(Exception):
    """Represents a failure to infer the version or executable while searching."""


def python_executable_prefix(v: str) -> List[str]:
    if sys.platform == 'win32':
        # on Windows, all Python executables are named `python`. To handle this, there
        # is the `py` launcher, which can be passed a version e.g. `py -3.5`, and it will
        # execute an installed Python 3.5 interpreter. See also:
        # https://docs.python.org/3/using/windows.html#python-launcher-for-windows
        return ['py', '-{}'.format(v)]
    else:
        return ['python{}'.format(v)]


def _python_version_from_executable(python_executable: str) -> Tuple[int, int]:
    try:
        check = subprocess.check_output([python_executable, '-c',
                                         'import sys; print(repr(sys.version_info[:2]))'],
                                        stderr=subprocess.STDOUT).decode()
        return ast.literal_eval(check)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise PythonExecutableInferenceError(
            'invalid Python executable {}'.format(python_executable))


def _python_executable_from_version(python_version: Tuple[int, int]) -> str:
    if sys.version_info[:2] == python_version:
        return sys.executable
    str_ver = '.'.join(map(str, python_version))
    try:
        sys_exe = subprocess.check_output(python_executable_prefix(str_ver) +
                                          ['-c', 'import sys; print(sys.executable)'],
                                          stderr=subprocess.STDOUT).decode().strip()
        return sys_exe
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise PythonExecutableInferenceError(
            'failed to find a Python executable matching version {},'
            ' perhaps try --python-executable, or --no-site-packages?'.format(python_version))


def infer_python_version_and_executable(options: Options,
                                        special_opts: argparse.Namespace) -> None:
    """Infer the Python version or executable from each other. Check they are consistent.

    This function mutates options based on special_opts to infer the correct Python version and
    executable to use.
    """
    # Infer Python version and/or executable if one is not given

    # TODO: (ethanhs) Look at folding these checks and the site packages subprocess calls into
    # one subprocess call for speed.
    if special_opts.python_executable is not None and special_opts.python_version is not None:
        py_exe_ver = _python_version_from_executable(special_opts.python_executable)
        if py_exe_ver != special_opts.python_version:
            raise PythonExecutableInferenceError(
                'Python version {} did not match executable {}, got version {}.'.format(
                    special_opts.python_version, special_opts.python_executable, py_exe_ver
                ))
        else:
            options.python_version = special_opts.python_version
            options.python_executable = special_opts.python_executable
    elif special_opts.python_executable is None and special_opts.python_version is not None:
        options.python_version = special_opts.python_version
        py_exe = None
        if not special_opts.no_executable:
            py_exe = _python_executable_from_version(special_opts.python_version)
        options.python_executable = py_exe
    elif special_opts.python_version is None and special_opts.python_executable is not None:
        options.python_version = _python_version_from_executable(
            special_opts.python_executable)
        options.python_executable = special_opts.python_executable


def process_options(args: List[str],
                    require_targets: bool = True,
                    server_options: bool = False,
                    fscache: Optional[FileSystemCache] = None,
                    ) -> Tuple[List[BuildSource], Options]:
    """Parse command line arguments.

    If a FileSystemCache is passed in, and package_root options are given,
    call fscache.set_package_root() to set the cache's package root.
    """

    parser = argparse.ArgumentParser(prog='mypy', epilog=FOOTER,
                                     fromfile_prefix_chars='@',
                                     formatter_class=AugmentedHelpFormatter)

    strict_flag_names = []  # type: List[str]
    strict_flag_assignments = []  # type: List[Tuple[str, bool]]

    def add_invertible_flag(flag: str,
                            *,
                            inverse: Optional[str] = None,
                            default: bool,
                            dest: Optional[str] = None,
                            help: str,
                            strict_flag: bool = False,
                            group: Optional[argparse._ActionsContainer] = None
                            ) -> None:
        if inverse is None:
            inverse = invert_flag_name(flag)
        if group is None:
            group = parser

        if help is not argparse.SUPPRESS:
            help += " (inverse: {})".format(inverse)

        arg = group.add_argument(flag,
                                 action='store_false' if default else 'store_true',
                                 dest=dest,
                                 help=help)
        dest = arg.dest
        arg = group.add_argument(inverse,
                                 action='store_true' if default else 'store_false',
                                 dest=dest,
                                 help=argparse.SUPPRESS)
        if strict_flag:
            assert dest is not None
            strict_flag_names.append(flag)
            strict_flag_assignments.append((dest, not default))

    # Unless otherwise specified, arguments will be parsed directly onto an
    # Options object.  Options that require further processing should have
    # their `dest` prefixed with `special-opts:`, which will cause them to be
    # parsed into the separate special_opts namespace object.
    parser.add_argument('-v', '--verbose', action='count', dest='verbosity',
                        help="more verbose messages")
    parser.add_argument('-V', '--version', action='version',
                        version='%(prog)s ' + __version__,
                        help="show program's version number and exit")

    config_group = parser.add_argument_group(
        title='config file',
        description="Use a config file instead of command line arguments.")
    config_group.add_argument(
        '--config-file',
        help="configuration file, must have a [mypy] section "
             "(defaults to {})".format(', '.join(defaults.CONFIG_FILES)))
    add_invertible_flag('--warn-unused-configs', default=False, strict_flag=True,
                        help="warn about unused '[mypy-<pattern>]' config sections",
                        group=config_group)

    imports_group = parser.add_argument_group(
        title='import discovery',
        description="Configure how imports are discovered and followed.")
    imports_group.add_argument(
        '--ignore-missing-imports', action='store_true',
        help="silently ignore imports of missing modules")
    imports_group.add_argument(
        '--follow-imports', choices=['normal', 'silent', 'skip', 'error'],
        default='normal', help="how to treat imports (default normal)")
    imports_group.add_argument(
        '--python-executable', action='store', metavar='EXECUTABLE',
        help="Python executable used for finding PEP 561 compliant installed"
             " packages and stubs",
        dest='special-opts:python_executable')
    imports_group.add_argument(
        '--no-site-packages', action='store_true',
        dest='special-opts:no_executable',
        help="do not search for installed PEP 561 compliant packages")

    platform_group = parser.add_argument_group(
        title='platform configuration',
        description="Type check code assuming certain runtime conditions.")
    platform_group.add_argument(
        '--python-version', type=parse_version, metavar='x.y',
        help='type check code assuming it will be running on Python x.y',
        dest='special-opts:python_version')
    platform_group.add_argument(
        '-2', '--py2', dest='python_version', action='store_const',
        const=defaults.PYTHON2_VERSION,
        help="use Python 2 mode (same as --python-version 2.7)")
    platform_group.add_argument(
        '--platform', action='store', metavar='PLATFORM',
        help="type check special-cased code for the given OS platform "
             "(defaults to sys.platform)")
    platform_group.add_argument(
        '--always-true', metavar='NAME', action='append', default=[],
        help="additional variable to be considered True (may be repeated)")
    platform_group.add_argument(
        '--always-false', metavar='NAME', action='append', default=[],
        help="additional variable to be considered False (may be repeated)")

    disallow_any_group = parser.add_argument_group(
        title='Any type restrictions',
        description="Disallow the use of the 'Any' type under certain conditions.")
    disallow_any_group.add_argument(
        '--disallow-any-unimported', default=False, action='store_true',
        help="disallow Any types resulting from unfollowed imports")
    add_invertible_flag('--disallow-subclassing-any', default=False, strict_flag=True,
                        help="disallow subclassing values of type 'Any' when defining classes",
                        group=disallow_any_group)
    disallow_any_group.add_argument(
        '--disallow-any-expr', default=False, action='store_true',
        help='disallow all expressions that have type Any')
    disallow_any_group.add_argument(
        '--disallow-any-decorated', default=False, action='store_true',
        help='disallow functions that have Any in their signature '
             'after decorator transformation')
    disallow_any_group.add_argument(
        '--disallow-any-explicit', default=False, action='store_true',
        help='disallow explicit Any in type positions')
    disallow_any_group.add_argument(
        '--disallow-any-generics', default=False, action='store_true',
        help='disallow usage of generic types that do not specify explicit '
             'type parameters')

    untyped_group = parser.add_argument_group(
        title='untyped definitions and calls',
        description="Configure how untyped definitions and calls are handled.")
    add_invertible_flag('--disallow-untyped-calls', default=False, strict_flag=True,
                        help="disallow calling functions without type annotations"
                        " from functions with type annotations",
                        group=untyped_group)
    add_invertible_flag('--disallow-untyped-defs', default=False, strict_flag=True,
                        help="disallow defining functions without type annotations"
                        " or with incomplete type annotations",
                        group=untyped_group)
    add_invertible_flag('--disallow-incomplete-defs', default=False, strict_flag=True,
                        help="disallow defining functions with incomplete type annotations",
                        group=untyped_group)
    add_invertible_flag('--check-untyped-defs', default=False, strict_flag=True,
                        help="type check the interior of functions without type annotations",
                        group=untyped_group)
    add_invertible_flag('--warn-incomplete-stub', default=False,
                        help="warn if missing type annotation in typeshed, only relevant with"
                             " --check-untyped-defs enabled",
                        group=untyped_group)

    none_group = parser.add_argument_group(
        title='None and Optional handling',
        description="Adjust how values of type 'None' are handled.")
    add_invertible_flag('--no-implicit-optional', default=False, strict_flag=True,
                        help="don't assume arguments with default values of None are Optional",
                        group=none_group)
    none_group.add_argument(
        '--strict-optional', action='store_true',
        help=argparse.SUPPRESS)
    none_group.add_argument(
        '--no-strict-optional', action='store_false', dest='strict_optional',
        help="disable strict Optional checks (inverse: --strict-optional)")
    none_group.add_argument(
        '--strict-optional-whitelist', metavar='GLOB', nargs='*',
        help="suppress strict Optional errors in all but the provided files; "
             "implies --strict-optional (may suppress certain other errors "
             "in non-whitelisted files)")

    lint_group = parser.add_argument_group(
        title='warnings',
        description="Detect code that is sound but redundant or problematic.")
    add_invertible_flag('--warn-redundant-casts', default=False, strict_flag=True,
                        help="warn about casting an expression to its inferred type",
                        group=lint_group)
    add_invertible_flag('--no-warn-no-return', dest='warn_no_return', default=True,
                        help="do not warn about functions that end without returning",
                        group=lint_group)
    add_invertible_flag('--warn-return-any', default=False, strict_flag=True,
                        help="warn about returning values of type Any"
                             " from non-Any typed functions",
                        group=lint_group)
    add_invertible_flag('--warn-unused-ignores', default=False, strict_flag=True,
                        help="warn about unneeded '# type: ignore' comments",
                        group=lint_group)

    strictness_group = parser.add_argument_group(
        title='other strictness checks',
        description="Other miscellaneous strictness checks.")
    add_invertible_flag('--disallow-untyped-decorators', default=False, strict_flag=True,
                        help="disallow decorating typed functions with untyped decorators",
                        group=strictness_group)

    incremental_group = parser.add_argument_group(
        title='incremental mode',
        description="Adjust how mypy incrementally type checks and caches modules.")
    incremental_group.add_argument(
        '-i', '--incremental', action='store_true',
        help=argparse.SUPPRESS)
    incremental_group.add_argument(
        '--no-incremental', action='store_false', dest='incremental',
        help="disable module cache (inverse: --incremental)")
    incremental_group.add_argument(
        '--cache-dir', action='store', metavar='DIR',
        help="store module cache info in the given folder in incremental mode "
             "(defaults to '{}')".format(defaults.CACHE_DIR))
    incremental_group.add_argument(
        '--cache-fine-grained', action='store_true',
        help="include fine-grained dependency information in the cache for the mypy daemon")
    incremental_group.add_argument(
        '--quick-and-dirty', action='store_true',
        help="use cache even if dependencies out of date (implies --incremental)")
    incremental_group.add_argument(
        '--skip-version-check', action='store_true',
        help="allow using cache written by older mypy version")

    internals_group = parser.add_argument_group(
        title='mypy internals',
        description="Debug and customize mypy internals.")
    internals_group.add_argument(
        '--pdb', action='store_true', help="invoke pdb on fatal error")
    internals_group.add_argument(
        '--show-traceback', '--tb', action='store_true',
        help="show traceback on fatal error")
    internals_group.add_argument(
        '--custom-typing', metavar='MODULE', dest='custom_typing_module',
        help="use a custom typing module")
    internals_group.add_argument(
        '--custom-typeshed-dir', metavar='DIR',
        help="use the custom typeshed in DIR")
    internals_group.add_argument(
        '--shadow-file', nargs=2, metavar=('SOURCE_FILE', 'SHADOW_FILE'),
        dest='shadow_file', action='append',
        help="when encountering SOURCE_FILE, read and type check "
             "the contents of SHADOW_FILE instead.")

    error_group = parser.add_argument_group(
        title='error reporting',
        description="Adjust the amount of detail shown in error messages.")
    add_invertible_flag('--show-error-context', default=False,
                        dest='show_error_context',
                        help='precede errors with "note:" messages explaining context',
                        group=error_group)
    add_invertible_flag('--show-column-numbers', default=False,
                        help="show column numbers in error messages",
                        group=error_group)

    analysis_group = parser.add_argument_group(
        title='extra analysis',
        description="Extract additional information and analysis.")
    analysis_group.add_argument(
        '--stats', action='store_true', dest='dump_type_stats', help=argparse.SUPPRESS)
    analysis_group.add_argument(
        '--inferstats', action='store_true', dest='dump_inference_stats',
        help=argparse.SUPPRESS)
    analysis_group.add_argument(
        '--find-occurrences', metavar='CLASS.MEMBER',
        dest='special-opts:find_occurrences',
        help="print out all usages of a class member (experimental)")

    strict_help = "strict mode; enables the following flags: {}".format(
        ", ".join(strict_flag_names))
    strictness_group.add_argument(
        '--strict', action='store_true', dest='special-opts:strict',
        help=strict_help)

    report_group = parser.add_argument_group(
        title='report generation',
        description='Generate a report in the specified format.')
    for report_type in sorted(reporter_classes):
        report_group.add_argument('--%s-report' % report_type.replace('_', '-'),
                                  metavar='DIR',
                                  dest='special-opts:%s_report' % report_type)

    other_group = parser.add_argument_group(
        title='miscellaneous',
        description="Other miscellaneous flags.")
    other_group.add_argument(
        '--junit-xml', help="write junit.xml to the given file")
    other_group.add_argument(
        '--scripts-are-modules', action='store_true',
        help="script x becomes module x instead of __main__")

    if server_options:
        # TODO: This flag is superfluous; remove after a short transition (2018-03-16)
        other_group.add_argument(
            '--experimental', action='store_true', dest='fine_grained_incremental',
            help="enable fine-grained incremental mode")
        other_group.add_argument(
            '--use-fine-grained-cache', action='store_true',
            help="use the cache in fine-grained incremental mode")

    # hidden options
    # --debug-cache will disable any cache-related compressions/optimizations,
    # which will make the cache writing process output pretty-printed JSON (which
    # is easier to debug).
    parser.add_argument('--debug-cache', action='store_true', help=argparse.SUPPRESS)
    # --dump-deps will dump all fine-grained dependencies to stdout
    parser.add_argument('--dump-deps', action='store_true', help=argparse.SUPPRESS)
    # --dump-graph will dump the contents of the graph of SCCs and exit.
    parser.add_argument('--dump-graph', action='store_true', help=argparse.SUPPRESS)
    # --semantic-analysis-only does exactly that.
    parser.add_argument('--semantic-analysis-only', action='store_true', help=argparse.SUPPRESS)
    # --local-partial-types disallows partial types spanning module top level and a function
    # (implicitly defined in fine-grained incremental mode)
    parser.add_argument('--local-partial-types', action='store_true', help=argparse.SUPPRESS)
    # --bazel changes some behaviors for use with Bazel (https://bazel.build).
    parser.add_argument('--bazel', action='store_true', help=argparse.SUPPRESS)
    # --package-root adds a directory below which directories are considered
    # packages even without __init__.py.  May be repeated.
    parser.add_argument('--package-root', metavar='ROOT', action='append', default=[],
                        help=argparse.SUPPRESS)
    # --cache-map FILE ... gives a mapping from source files to cache files.
    # Each triple of arguments is a source file, a cache meta file, and a cache data file.
    # Modules not mentioned in the file will go through cache_dir.
    # Must be followed by another flag or by '--' (and then only file args may follow).
    parser.add_argument('--cache-map', nargs='+', dest='special-opts:cache_map',
                        help=argparse.SUPPRESS)

    # deprecated options
    parser.add_argument('--disallow-any', dest='special-opts:disallow_any',
                        help=argparse.SUPPRESS)
    add_invertible_flag('--strict-boolean', default=False,
                        help=argparse.SUPPRESS)
    parser.add_argument('-f', '--dirty-stubs', action='store_true',
                        dest='special-opts:dirty_stubs',
                        help=argparse.SUPPRESS)
    parser.add_argument('--use-python-path', action='store_true',
                        dest='special-opts:use_python_path',
                        help=argparse.SUPPRESS)
    parser.add_argument('-s', '--silent-imports', action='store_true',
                        dest='special-opts:silent_imports',
                        help=argparse.SUPPRESS)
    parser.add_argument('--almost-silent', action='store_true',
                        dest='special-opts:almost_silent',
                        help=argparse.SUPPRESS)
    parser.add_argument('--fast-parser', action='store_true', dest='special-opts:fast_parser',
                        help=argparse.SUPPRESS)
    parser.add_argument('--no-fast-parser', action='store_true',
                        dest='special-opts:no_fast_parser',
                        help=argparse.SUPPRESS)

    code_group = parser.add_argument_group(title='specifying which code to type check')
    code_group.add_argument('-m', '--module', action='append', metavar='MODULE',
                            default=[],
                            dest='special-opts:modules',
                            help="type-check module; can repeat for more modules")
    code_group.add_argument('-p', '--package', action='append', metavar='PACKAGE',
                            default=[],
                            dest='special-opts:packages',
                            help="type-check package recursively; can be repeated")
    code_group.add_argument('-c', '--command', action='append', metavar='PROGRAM_TEXT',
                            dest='special-opts:command',
                            help="type-check program passed in as string")
    code_group.add_argument(metavar='files', nargs='*', dest='special-opts:files',
                            help="type-check given files or directories")

    # Parse arguments once into a dummy namespace so we can get the
    # filename for the config file and know if the user requested all strict options.
    dummy = argparse.Namespace()
    parser.parse_args(args, dummy)
    config_file = dummy.config_file
    if config_file is not None and not os.path.exists(config_file):
        parser.error("Cannot find config file '%s'" % config_file)

    # Parse config file first, so command line can override.
    options = Options()
    parse_config_file(options, config_file)

    # Set strict flags before parsing (if strict mode enabled), so other command
    # line options can override.
    if getattr(dummy, 'special-opts:strict'):
        for dest, value in strict_flag_assignments:
            setattr(options, dest, value)

    # Parse command line for real, using a split namespace.
    special_opts = argparse.Namespace()
    parser.parse_args(args, SplitNamespace(options, special_opts, 'special-opts:'))

    # --use-python-path is no longer supported; explain why.
    if special_opts.use_python_path:
        parser.error("Sorry, --use-python-path is no longer supported.\n"
                     "If you are trying this because your code depends on a library module,\n"
                     "you should really investigate how to obtain stubs for that module.\n"
                     "See https://github.com/python/mypy/issues/1411 for more discussion."
                     )

    # Process deprecated options
    if special_opts.disallow_any:
        print("--disallow-any option was split up into multiple flags. "
              "See http://mypy.readthedocs.io/en/latest/command_line.html#disallow-any-flags")
    if options.strict_boolean:
        print("Warning: --strict-boolean is deprecated; "
              "see https://github.com/python/mypy/issues/3195", file=sys.stderr)
    if special_opts.almost_silent:
        print("Warning: --almost-silent has been replaced by "
              "--follow-imports=errors", file=sys.stderr)
        if options.follow_imports == 'normal':
            options.follow_imports = 'errors'
    elif special_opts.silent_imports:
        print("Warning: --silent-imports has been replaced by "
              "--ignore-missing-imports --follow-imports=skip", file=sys.stderr)
        options.ignore_missing_imports = True
        if options.follow_imports == 'normal':
            options.follow_imports = 'skip'
    if special_opts.dirty_stubs:
        print("Warning: -f/--dirty-stubs is deprecated and no longer necessary. Mypy no longer "
              "checks the git status of stubs.",
              file=sys.stderr)
    if special_opts.fast_parser:
        print("Warning: --fast-parser is now the default (and only) parser.")
    if special_opts.no_fast_parser:
        print("Warning: --no-fast-parser no longer has any effect.  The fast parser "
              "is now mypy's default and only parser.")

    try:
        infer_python_version_and_executable(options, special_opts)
    except PythonExecutableInferenceError as e:
        parser.error(str(e))

    if special_opts.no_executable:
        options.python_executable = None

    # Check for invalid argument combinations.
    if require_targets:
        code_methods = sum(bool(c) for c in [special_opts.modules + special_opts.packages,
                                             special_opts.command,
                                             special_opts.files])
        if code_methods == 0:
            parser.error("Missing target module, package, files, or command.")
        elif code_methods > 1:
            parser.error("May only specify one of: module/package, files, or command.")

    # Check for overlapping `--always-true` and `--always-false` flags.
    overlap = set(options.always_true) & set(options.always_false)
    if overlap:
        parser.error("You can't make a variable always true and always false (%s)" %
                     ', '.join(sorted(overlap)))

    # Set build flags.
    if options.strict_optional_whitelist is not None:
        # TODO: Deprecate, then kill this flag
        options.strict_optional = True
    if special_opts.find_occurrences:
        experiments.find_occurrences = special_opts.find_occurrences.split('.')
        assert experiments.find_occurrences is not None
        if len(experiments.find_occurrences) < 2:
            parser.error("Can only find occurrences of class members.")
        if len(experiments.find_occurrences) != 2:
            parser.error("Can only find occurrences of non-nested class members.")

    # Set reports.
    for flag, val in vars(special_opts).items():
        if flag.endswith('_report') and val is not None:
            report_type = flag[:-7].replace('_', '-')
            report_dir = val
            options.report_dirs[report_type] = report_dir

    # Process --package-root.
    if options.package_root:
        process_package_roots(fscache, parser, options)

    # Process --cache-map.
    if special_opts.cache_map:
        process_cache_map(parser, special_opts, options)

    # Let quick_and_dirty imply incremental.
    if options.quick_and_dirty:
        options.incremental = True

    # Set target.
    if special_opts.modules + special_opts.packages:
        options.build_type = BuildType.MODULE
        lib_path = [os.getcwd()] + build.mypy_path()
        targets = []
        # TODO: use the same cache that the BuildManager will
        cache = build.FindModuleCache(fscache)
        for p in special_opts.packages:
            if os.sep in p or os.altsep and os.altsep in p:
                fail("Package name '{}' cannot have a slash in it.".format(p))
            p_targets = cache.find_modules_recursive(p, tuple(lib_path), options.python_executable)
            if not p_targets:
                fail("Can't find package '{}'".format(p))
            targets.extend(p_targets)
        for m in special_opts.modules:
            targets.append(BuildSource(None, m, None))
        return targets, options
    elif special_opts.command:
        options.build_type = BuildType.PROGRAM_TEXT
        targets = [BuildSource(None, None, '\n'.join(special_opts.command))]
        return targets, options
    else:
        try:
            targets = create_source_list(special_opts.files, options, fscache)
        except InvalidSourceList as e:
            fail(str(e))
        return targets, options


def process_package_roots(fscache: Optional[FileSystemCache],
                          parser: argparse.ArgumentParser,
                          options: Options) -> None:
    """Validate and normalize package_root."""
    if fscache is None:
        parser.error("--package-root does not work here (no fscache)")
    assert fscache is not None  # Since mypy doesn't know parser.error() raises.
    # Do some stuff with drive letters to make Windows happy (esp. tests).
    current_drive, _ = os.path.splitdrive(os.getcwd())
    dot = os.curdir
    dotslash = os.curdir + os.sep
    dotdotslash = os.pardir + os.sep
    trivial_paths = {dot, dotslash}
    package_root = []
    for root in options.package_root:
        if os.path.isabs(root):
            parser.error("Package root cannot be absolute: %r" % root)
        drive, root = os.path.splitdrive(root)
        if drive and drive != current_drive:
            parser.error("Package root must be on current drive: %r" % (drive + root))
        # Empty package root is always okay.
        if root:
            root = os.path.relpath(root)  # Normalize the heck out of it.
            if root.startswith(dotdotslash):
                parser.error("Package root cannot be above current directory: %r" % root)
            if root in trivial_paths:
                root = ''
            elif not root.endswith(os.sep):
                root = root + os.sep
        package_root.append(root)
    options.package_root = package_root
    # Pass the package root on the the filesystem cache.
    fscache.set_package_root(package_root)


def process_cache_map(parser: argparse.ArgumentParser,
                      special_opts: argparse.Namespace,
                      options: Options) -> None:
    """Validate cache_map and copy into options.cache_map."""
    n = len(special_opts.cache_map)
    if n % 3 != 0:
        parser.error("--cache-map requires one or more triples (see source)")
    for i in range(0, n, 3):
        source, meta_file, data_file = special_opts.cache_map[i:i + 3]
        if source in options.cache_map:
            parser.error("Duplicate --cache-map source %s)" % source)
        if not source.endswith('.py') and not source.endswith('.pyi'):
            parser.error("Invalid --cache-map source %s (triple[0] must be *.py[i])" % source)
        if not meta_file.endswith('.meta.json'):
            parser.error("Invalid --cache-map meta_file %s (triple[1] must be *.meta.json)" %
                         meta_file)
        if not data_file.endswith('.data.json'):
            parser.error("Invalid --cache-map data_file %s (triple[2] must be *.data.json)" %
                         data_file)
        options.cache_map[source] = (meta_file, data_file)


# For most options, the type of the default value set in options.py is
# sufficient, and we don't have to do anything here.  This table
# exists to specify types for values initialized to None or container
# types.
config_types = {
    'python_version': parse_version,
    'strict_optional_whitelist': lambda s: s.split(),
    'custom_typing_module': str,
    'custom_typeshed_dir': str,
    'mypy_path': lambda s: [p.strip() for p in re.split('[,:]', s)],
    'junit_xml': str,
    # These two are for backwards compatibility
    'silent_imports': bool,
    'almost_silent': bool,
    'plugins': lambda s: [p.strip() for p in s.split(',')],
    'always_true': lambda s: [p.strip() for p in s.split(',')],
    'always_false': lambda s: [p.strip() for p in s.split(',')],
    'package_root': lambda s: [p.strip() for p in s.split(',')],
}


def parse_config_file(options: Options, filename: Optional[str]) -> None:
    """Parse a config file into an Options object.

    Errors are written to stderr but are not fatal.

    If filename is None, fall back to default config files.
    """
    if filename is not None:
        config_files = (filename,)  # type: Tuple[str, ...]
    else:
        config_files = tuple(map(os.path.expanduser, defaults.CONFIG_FILES))

    parser = configparser.RawConfigParser()

    for config_file in config_files:
        if not os.path.exists(config_file):
            continue
        try:
            parser.read(config_file)
        except configparser.Error as err:
            print("%s: %s" % (config_file, err), file=sys.stderr)
        else:
            file_read = config_file
            options.config_file = file_read
            break
    else:
        return

    if 'mypy' not in parser:
        if filename or file_read not in defaults.SHARED_CONFIG_FILES:
            print("%s: No [mypy] section in config file" % file_read, file=sys.stderr)
    else:
        section = parser['mypy']
        prefix = '%s: [%s]' % (file_read, 'mypy')
        updates, report_dirs = parse_section(prefix, options, section)
        for k, v in updates.items():
            setattr(options, k, v)
        options.report_dirs.update(report_dirs)

    for name, section in parser.items():
        if name.startswith('mypy-'):
            prefix = '%s: [%s]' % (file_read, name)
            updates, report_dirs = parse_section(prefix, options, section)
            if report_dirs:
                print("%s: Per-module sections should not specify reports (%s)" %
                      (prefix, ', '.join(s + '_report' for s in sorted(report_dirs))),
                      file=sys.stderr)
            if set(updates) - Options.PER_MODULE_OPTIONS:
                print("%s: Per-module sections should only specify per-module flags (%s)" %
                      (prefix, ', '.join(sorted(set(updates) - Options.PER_MODULE_OPTIONS))),
                      file=sys.stderr)
                updates = {k: v for k, v in updates.items() if k in Options.PER_MODULE_OPTIONS}
            globs = name[5:]
            for glob in globs.split(','):
                # For backwards compatibility, replace (back)slashes with dots.
                glob = glob.replace(os.sep, '.')
                if os.altsep:
                    glob = glob.replace(os.altsep, '.')

                if (any(c in glob for c in '?[]!') or
                        any('*' in x and x != '*' for x in glob.split('.'))):
                    print("%s: Patterns must be fully-qualified module names, optionally "
                          "with '*' in some components (e.g spam.*.eggs.*)"
                          % prefix,
                          file=sys.stderr)
                else:
                    options.per_module_options[glob] = updates


def parse_section(prefix: str, template: Options,
                  section: Mapping[str, str]) -> Tuple[Dict[str, object], Dict[str, str]]:
    """Parse one section of a config file.

    Returns a dict of option values encountered, and a dict of report directories.
    """
    results = {}  # type: Dict[str, object]
    report_dirs = {}  # type: Dict[str, str]
    for key in section:
        if key in config_types:
            ct = config_types[key]
        else:
            dv = getattr(template, key, None)
            if dv is None:
                if key.endswith('_report'):
                    report_type = key[:-7].replace('_', '-')
                    if report_type in reporter_classes:
                        report_dirs[report_type] = section[key]
                    else:
                        print("%s: Unrecognized report type: %s" % (prefix, key),
                              file=sys.stderr)
                    continue
                if key.startswith('x_'):
                    continue  # Don't complain about `x_blah` flags
                elif key == 'strict':
                    print("%s: Strict mode is not supported in configuration files: specify "
                          "individual flags instead (see 'mypy -h' for the list of flags enabled "
                          "in strict mode)" % prefix, file=sys.stderr)
                else:
                    print("%s: Unrecognized option: %s = %s" % (prefix, key, section[key]),
                          file=sys.stderr)
                continue
            ct = type(dv)
        v = None  # type: Any
        try:
            if ct is bool:
                v = section.getboolean(key)  # type: ignore  # Until better stub
            elif callable(ct):
                try:
                    v = ct(section.get(key))
                except argparse.ArgumentTypeError as err:
                    print("%s: %s: %s" % (prefix, key, err), file=sys.stderr)
                    continue
            else:
                print("%s: Don't know what type %s should have" % (prefix, key), file=sys.stderr)
                continue
        except ValueError as err:
            print("%s: %s: %s" % (prefix, key, err), file=sys.stderr)
            continue
        if key == 'silent_imports':
            print("%s: silent_imports has been replaced by "
                  "ignore_missing_imports=True; follow_imports=skip" % prefix, file=sys.stderr)
            if v:
                if 'ignore_missing_imports' not in results:
                    results['ignore_missing_imports'] = True
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'skip'
        if key == 'almost_silent':
            print("%s: almost_silent has been replaced by "
                  "follow_imports=error" % prefix, file=sys.stderr)
            if v:
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'error'
        results[key] = v
    return results, report_dirs


def fail(msg: str) -> None:
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)
