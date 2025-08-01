"""Mypy type checker command line tool."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from gettext import gettext
from io import TextIOWrapper
from typing import IO, TYPE_CHECKING, Any, Final, NoReturn, TextIO

from mypy import build, defaults, state, util
from mypy.config_parser import (
    get_config_module_names,
    parse_config_file,
    parse_version,
    validate_package_allow_list,
)
from mypy.error_formatter import OUTPUT_CHOICES
from mypy.errors import CompileError
from mypy.find_sources import InvalidSourceList, create_source_list
from mypy.fscache import FileSystemCache
from mypy.modulefinder import (
    BuildSource,
    FindModuleCache,
    ModuleNotFoundReason,
    SearchPaths,
    get_search_dirs,
    mypy_path,
)
from mypy.options import INCOMPLETE_FEATURES, BuildType, Options
from mypy.split_namespace import SplitNamespace
from mypy.version import __version__

if TYPE_CHECKING:
    from _typeshed import SupportsWrite


orig_stat: Final = os.stat
MEM_PROFILE: Final = False  # If True, dump memory profile
RECURSION_LIMIT: Final = 2**14


def stat_proxy(path: str) -> os.stat_result:
    try:
        st = orig_stat(path)
    except OSError as err:
        print(f"stat({path!r}) -> {err}")
        raise
    else:
        print(
            "stat(%r) -> (st_mode=%o, st_mtime=%d, st_size=%d)"
            % (path, st.st_mode, st.st_mtime, st.st_size)
        )
        return st


def main(
    *,
    args: list[str] | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    clean_exit: bool = False,
) -> None:
    """Main entry point to the type checker.

    Args:
        args: Custom command-line arguments.  If not given, sys.argv[1:] will
            be used.
        clean_exit: Don't hard kill the process on exit. This allows catching
            SystemExit.
    """
    util.check_python_version("mypy")
    t0 = time.time()
    # To log stat() calls: os.stat = stat_proxy
    sys.setrecursionlimit(RECURSION_LIMIT)
    if args is None:
        args = sys.argv[1:]

    # Write an escape sequence instead of raising an exception on encoding errors.
    if isinstance(stdout, TextIOWrapper) and stdout.errors == "strict":
        stdout.reconfigure(errors="backslashreplace")

    fscache = FileSystemCache()
    sources, options = process_options(args, stdout=stdout, stderr=stderr, fscache=fscache)
    if clean_exit:
        options.fast_exit = False

    formatter = util.FancyFormatter(
        stdout, stderr, options.hide_error_codes, hide_success=bool(options.output)
    )

    if options.allow_redefinition_new and not options.local_partial_types:
        fail(
            "error: --local-partial-types must be enabled if using --allow-redefinition-new",
            stderr,
            options,
        )

    if options.install_types and (stdout is not sys.stdout or stderr is not sys.stderr):
        # Since --install-types performs user input, we want regular stdout and stderr.
        fail("error: --install-types not supported in this mode of running mypy", stderr, options)

    if options.non_interactive and not options.install_types:
        fail("error: --non-interactive is only supported with --install-types", stderr, options)

    if options.install_types and not options.incremental:
        fail(
            "error: --install-types not supported with incremental mode disabled", stderr, options
        )

    if options.install_types and options.python_executable is None:
        fail(
            "error: --install-types not supported without python executable or site packages",
            stderr,
            options,
        )

    if options.install_types and not sources:
        install_types(formatter, options, non_interactive=options.non_interactive)
        return

    res, messages, blockers = run_build(sources, options, fscache, t0, stdout, stderr)

    if options.non_interactive:
        missing_pkgs = read_types_packages_to_install(options.cache_dir, after_run=True)
        if missing_pkgs:
            # Install missing type packages and rerun build.
            install_types(formatter, options, after_run=True, non_interactive=True)
            fscache.flush()
            print()
            res, messages, blockers = run_build(sources, options, fscache, t0, stdout, stderr)
        show_messages(messages, stderr, formatter, options)

    if MEM_PROFILE:
        from mypy.memprofile import print_memory_profile

        print_memory_profile()

    code = 0
    n_errors, n_notes, n_files = util.count_stats(messages)
    if messages and n_notes < len(messages):
        code = 2 if blockers else 1
    if options.error_summary:
        if n_errors:
            summary = formatter.format_error(
                n_errors, n_files, len(sources), blockers=blockers, use_color=options.color_output
            )
            stdout.write(summary + "\n")
        # Only notes should also output success
        elif not messages or n_notes == len(messages):
            stdout.write(formatter.format_success(len(sources), options.color_output) + "\n")
        stdout.flush()

    if options.install_types and not options.non_interactive:
        result = install_types(formatter, options, after_run=True, non_interactive=False)
        if result:
            print()
            print("note: Run mypy again for up-to-date results with installed types")
            code = 2

    if options.fast_exit:
        # Exit without freeing objects -- it's faster.
        #
        # NOTE: We don't flush all open files on exit (or run other destructors)!
        util.hard_exit(code)
    elif code:
        sys.exit(code)

    # HACK: keep res alive so that mypyc won't free it before the hard_exit
    list([res])  # noqa: C410


def run_build(
    sources: list[BuildSource],
    options: Options,
    fscache: FileSystemCache,
    t0: float,
    stdout: TextIO,
    stderr: TextIO,
) -> tuple[build.BuildResult | None, list[str], bool]:
    formatter = util.FancyFormatter(
        stdout, stderr, options.hide_error_codes, hide_success=bool(options.output)
    )

    messages = []
    messages_by_file = defaultdict(list)

    def flush_errors(filename: str | None, new_messages: list[str], serious: bool) -> None:
        if options.pretty:
            new_messages = formatter.fit_in_terminal(new_messages)
        messages.extend(new_messages)
        if new_messages:
            messages_by_file[filename].extend(new_messages)
        if options.non_interactive:
            # Collect messages and possibly show them later.
            return
        f = stderr if serious else stdout
        show_messages(new_messages, f, formatter, options)

    serious = False
    blockers = False
    res = None
    try:
        # Keep a dummy reference (res) for memory profiling afterwards, as otherwise
        # the result could be freed.
        res = build.build(sources, options, None, flush_errors, fscache, stdout, stderr)
    except CompileError as e:
        blockers = True
        if not e.use_stdout:
            serious = True
    if (
        options.warn_unused_configs
        and options.unused_configs
        and not options.incremental
        and not options.non_interactive
    ):
        print(
            "Warning: unused section(s) in {}: {}".format(
                options.config_file,
                get_config_module_names(
                    options.config_file,
                    [
                        glob
                        for glob in options.per_module_options.keys()
                        if glob in options.unused_configs
                    ],
                ),
            ),
            file=stderr,
        )
    maybe_write_junit_xml(time.time() - t0, serious, messages, messages_by_file, options)
    return res, messages, blockers


def show_messages(
    messages: list[str], f: TextIO, formatter: util.FancyFormatter, options: Options
) -> None:
    for msg in messages:
        if options.color_output:
            msg = formatter.colorize(msg)
        f.write(msg + "\n")
    f.flush()


# Make the help output a little less jarring.
class AugmentedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog: str, **kwargs: Any) -> None:
        super().__init__(prog=prog, max_help_position=28, **kwargs)

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        if "\n" in text:
            # Assume we want to manually format the text
            return super()._fill_text(text, width, indent)
        else:
            # Assume we want argparse to manage wrapping, indenting, and
            # formatting the text for us.
            return argparse.HelpFormatter._fill_text(self, text, width, indent)


# Define pairs of flag prefixes with inverse meaning.
flag_prefix_pairs: Final = [("allow", "disallow"), ("show", "hide")]
flag_prefix_map: Final[dict[str, str]] = {}
for a, b in flag_prefix_pairs:
    flag_prefix_map[a] = b
    flag_prefix_map[b] = a


def invert_flag_name(flag: str) -> str:
    split = flag[2:].split("-", 1)
    if len(split) == 2:
        prefix, rest = split
        if prefix in flag_prefix_map:
            return f"--{flag_prefix_map[prefix]}-{rest}"
        elif prefix == "no":
            return f"--{rest}"

    return f"--no-{flag[2:]}"


class PythonExecutableInferenceError(Exception):
    """Represents a failure to infer the version or executable while searching."""


def python_executable_prefix(v: str) -> list[str]:
    if sys.platform == "win32":
        # on Windows, all Python executables are named `python`. To handle this, there
        # is the `py` launcher, which can be passed a version e.g. `py -3.8`, and it will
        # execute an installed Python 3.8 interpreter. See also:
        # https://docs.python.org/3/using/windows.html#python-launcher-for-windows
        return ["py", f"-{v}"]
    else:
        return [f"python{v}"]


def _python_executable_from_version(python_version: tuple[int, int]) -> str:
    if sys.version_info[:2] == python_version:
        return sys.executable
    str_ver = ".".join(map(str, python_version))
    try:
        sys_exe = (
            subprocess.check_output(
                python_executable_prefix(str_ver) + ["-c", "import sys; print(sys.executable)"],
                stderr=subprocess.STDOUT,
            )
            .decode()
            .strip()
        )
        return sys_exe
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise PythonExecutableInferenceError(
            "failed to find a Python executable matching version {},"
            " perhaps try --python-executable, or --no-site-packages?".format(python_version)
        ) from e


def infer_python_executable(options: Options, special_opts: argparse.Namespace) -> None:
    """Infer the Python executable from the given version.

    This function mutates options based on special_opts to infer the correct Python executable
    to use.
    """
    # TODO: (ethanhs) Look at folding these checks and the site packages subprocess calls into
    # one subprocess call for speed.

    # Use the command line specified executable, or fall back to one set in the
    # config file. If an executable is not specified, infer it from the version
    # (unless no_executable is set)
    python_executable = special_opts.python_executable or options.python_executable

    if python_executable is None:
        if not special_opts.no_executable and not options.no_site_packages:
            python_executable = _python_executable_from_version(options.python_version)
    options.python_executable = python_executable


HEADER: Final = """%(prog)s [-h] [-v] [-V] [more options; see below]
            [-m MODULE] [-p PACKAGE] [-c PROGRAM_TEXT] [files ...]"""


DESCRIPTION: Final = """
Mypy is a program that will type check your Python code.

Pass in any files or folders you want to type check. Mypy will
recursively traverse any provided folders to find .py files:

    $ mypy my_program.py my_src_folder

For more information on getting started, see:

- https://mypy.readthedocs.io/en/stable/getting_started.html

For more details on both running mypy and using the flags below, see:

- https://mypy.readthedocs.io/en/stable/running_mypy.html
- https://mypy.readthedocs.io/en/stable/command_line.html

You can also use a config file to configure mypy instead of using
command line flags. For more details, see:

- https://mypy.readthedocs.io/en/stable/config_file.html
"""

FOOTER: Final = """Environment variables:
  Define MYPYPATH for additional module search path entries.
  Define MYPY_CACHE_DIR to override configuration cache_dir path."""


class CapturableArgumentParser(argparse.ArgumentParser):
    """Override ArgumentParser methods that use sys.stdout/sys.stderr directly.

    This is needed because hijacking sys.std* is not thread-safe,
    yet output must be captured to properly support mypy.api.run.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.stdout = kwargs.pop("stdout", sys.stdout)
        self.stderr = kwargs.pop("stderr", sys.stderr)
        super().__init__(*args, **kwargs)

    # =====================
    # Help-printing methods
    # =====================
    def print_usage(self, file: SupportsWrite[str] | None = None) -> None:
        if file is None:
            file = self.stdout
        self._print_message(self.format_usage(), file)

    def print_help(self, file: SupportsWrite[str] | None = None) -> None:
        if file is None:
            file = self.stdout
        self._print_message(self.format_help(), file)

    def _print_message(self, message: str, file: SupportsWrite[str] | None = None) -> None:
        if message:
            if file is None:
                file = self.stderr
            file.write(message)

    # ===============
    # Exiting methods
    # ===============
    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._print_message(message, self.stderr)
        sys.exit(status)

    def error(self, message: str) -> NoReturn:
        """error(message: string)

        Prints a usage message incorporating the message to stderr and
        exits.

        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """
        self.print_usage(self.stderr)
        args = {"prog": self.prog, "message": message}
        self.exit(2, gettext("%(prog)s: error: %(message)s\n") % args)


class CapturableVersionAction(argparse.Action):
    """Supplement CapturableArgumentParser to handle --version.

    This is nearly identical to argparse._VersionAction except,
    like CapturableArgumentParser, it allows output to be captured.

    Another notable difference is that version is mandatory.
    This allows removing a line in __call__ that falls back to parser.version
    (which does not appear to exist).
    """

    def __init__(
        self,
        option_strings: Sequence[str],
        version: str,
        dest: str = argparse.SUPPRESS,
        default: str = argparse.SUPPRESS,
        help: str = "show program's version number and exit",
        stdout: IO[str] | None = None,
    ) -> None:
        super().__init__(
            option_strings=option_strings, dest=dest, default=default, nargs=0, help=help
        )
        self.version = version
        self.stdout = stdout or sys.stdout

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> NoReturn:
        formatter = parser._get_formatter()
        formatter.add_text(self.version)
        parser._print_message(formatter.format_help(), self.stdout)
        parser.exit()


def process_options(
    args: list[str],
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    require_targets: bool = True,
    server_options: bool = False,
    fscache: FileSystemCache | None = None,
    program: str = "mypy",
    header: str = HEADER,
) -> tuple[list[BuildSource], Options]:
    """Parse command line arguments.

    If a FileSystemCache is passed in, and package_root options are given,
    call fscache.set_package_root() to set the cache's package root.
    """
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    parser = CapturableArgumentParser(
        prog=program,
        usage=header,
        description=DESCRIPTION,
        epilog=FOOTER,
        fromfile_prefix_chars="@",
        formatter_class=AugmentedHelpFormatter,
        add_help=False,
        stdout=stdout,
        stderr=stderr,
    )
    if sys.version_info >= (3, 14):
        parser.color = True  # Set as init arg in 3.14

    strict_flag_names: list[str] = []
    strict_flag_assignments: list[tuple[str, bool]] = []

    def add_invertible_flag(
        flag: str,
        *,
        inverse: str | None = None,
        default: bool,
        dest: str | None = None,
        help: str,
        strict_flag: bool = False,
        group: argparse._ActionsContainer | None = None,
    ) -> None:
        if inverse is None:
            inverse = invert_flag_name(flag)
        if group is None:
            group = parser

        if help is not argparse.SUPPRESS:
            help += f" (inverse: {inverse})"

        arg = group.add_argument(
            flag, action="store_false" if default else "store_true", dest=dest, help=help
        )
        dest = arg.dest
        group.add_argument(
            inverse,
            action="store_true" if default else "store_false",
            dest=dest,
            help=argparse.SUPPRESS,
        )
        if strict_flag:
            assert dest is not None
            strict_flag_names.append(flag)
            strict_flag_assignments.append((dest, not default))

    # Unless otherwise specified, arguments will be parsed directly onto an
    # Options object.  Options that require further processing should have
    # their `dest` prefixed with `special-opts:`, which will cause them to be
    # parsed into the separate special_opts namespace object.

    # Our style guide for formatting the output of running `mypy --help`:
    # Flags:
    # 1.  The flag help text should start with a capital letter but never end with a period.
    # 2.  Keep the flag help text brief -- ideally just a single sentence.
    # 3.  All flags must be a part of a group, unless the flag is deprecated or suppressed.
    # 4.  Avoid adding new flags to the "miscellaneous" groups -- instead add them to an
    #     existing group or, if applicable, create a new group. Feel free to move existing
    #     flags to a new group: just be sure to also update the documentation to match.
    #
    # Groups:
    # 1.  The group title and description should start with a capital letter.
    # 2.  The first sentence of a group description should be written in the bare infinitive.
    #     Tip: try substituting the group title and description into the following sentence:
    #     > {group_title}: these flags will {group_description}
    #     Feel free to add subsequent sentences that add additional details.
    # 3.  If you cannot think of a meaningful description for a new group, omit it entirely.
    #     (E.g. see the "miscellaneous" sections).
    # 4.  The group description should end with a period (unless the last line is a link). If you
    #     do end the group description with a link, omit the 'http://' prefix. (Some links are too
    #     long and will break up into multiple lines if we include that prefix, so for consistency
    #     we omit the prefix on all links.)

    general_group = parser.add_argument_group(title="Optional arguments")
    general_group.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit"
    )
    general_group.add_argument(
        "-v", "--verbose", action="count", dest="verbosity", help="More verbose messages"
    )

    compilation_status = "no" if __file__.endswith(".py") else "yes"
    general_group.add_argument(
        "-V",
        "--version",
        action=CapturableVersionAction,
        version="%(prog)s " + __version__ + f" (compiled: {compilation_status})",
        help="Show program's version number and exit",
        stdout=stdout,
    )

    general_group.add_argument(
        "-O",
        "--output",
        metavar="FORMAT",
        help="Set a custom output format",
        choices=OUTPUT_CHOICES,
    )

    config_group = parser.add_argument_group(
        title="Config file",
        description="Use a config file instead of command line arguments. "
        "This is useful if you are using many flags or want "
        "to set different options per each module.",
    )
    config_group.add_argument(
        "--config-file",
        help=(
            f"Configuration file, must have a [mypy] section "
            f"(defaults to {', '.join(defaults.CONFIG_NAMES + defaults.SHARED_CONFIG_NAMES)})"
        ),
    )
    add_invertible_flag(
        "--warn-unused-configs",
        default=False,
        strict_flag=True,
        help="Warn about unused '[mypy-<pattern>]' or '[[tool.mypy.overrides]]' config sections",
        group=config_group,
    )

    imports_group = parser.add_argument_group(
        title="Import discovery", description="Configure how imports are discovered and followed."
    )
    add_invertible_flag(
        "--no-namespace-packages",
        dest="namespace_packages",
        default=True,
        help="Disable support for namespace packages (PEP 420, __init__.py-less)",
        group=imports_group,
    )
    imports_group.add_argument(
        "--ignore-missing-imports",
        action="store_true",
        help="Silently ignore imports of missing modules",
    )
    imports_group.add_argument(
        "--follow-untyped-imports",
        action="store_true",
        help="Typecheck modules without stubs or py.typed marker",
    )
    imports_group.add_argument(
        "--follow-imports",
        choices=["normal", "silent", "skip", "error"],
        default="normal",
        help="How to treat imports (default normal)",
    )
    imports_group.add_argument(
        "--python-executable",
        action="store",
        metavar="EXECUTABLE",
        help="Python executable used for finding PEP 561 compliant installed packages and stubs",
        dest="special-opts:python_executable",
    )
    imports_group.add_argument(
        "--no-site-packages",
        action="store_true",
        dest="special-opts:no_executable",
        help="Do not search for installed PEP 561 compliant packages",
    )
    imports_group.add_argument(
        "--no-silence-site-packages",
        action="store_true",
        help="Do not silence errors in PEP 561 compliant installed packages",
    )

    platform_group = parser.add_argument_group(
        title="Platform configuration",
        description="Type check code assuming it will be run under certain "
        "runtime conditions. By default, mypy assumes your code "
        "will be run using the same operating system and Python "
        "version you are using to run mypy itself.",
    )
    platform_group.add_argument(
        "--python-version",
        type=parse_version,
        metavar="x.y",
        help="Type check code assuming it will be running on Python x.y",
        dest="special-opts:python_version",
    )
    platform_group.add_argument(
        "--platform",
        action="store",
        metavar="PLATFORM",
        help="Type check special-cased code for the given OS platform (defaults to sys.platform)",
    )
    platform_group.add_argument(
        "--always-true",
        metavar="NAME",
        action="append",
        default=[],
        help="Additional variable to be considered True (may be repeated)",
    )
    platform_group.add_argument(
        "--always-false",
        metavar="NAME",
        action="append",
        default=[],
        help="Additional variable to be considered False (may be repeated)",
    )

    disallow_any_group = parser.add_argument_group(
        title="Disallow dynamic typing",
        description="Disallow the use of the dynamic 'Any' type under certain conditions.",
    )
    disallow_any_group.add_argument(
        "--disallow-any-expr",
        default=False,
        action="store_true",
        help="Disallow all expressions that have type Any",
    )
    disallow_any_group.add_argument(
        "--disallow-any-decorated",
        default=False,
        action="store_true",
        help="Disallow functions that have Any in their signature after decorator transformation",
    )
    disallow_any_group.add_argument(
        "--disallow-any-explicit",
        default=False,
        action="store_true",
        help="Disallow explicit Any in type positions",
    )
    add_invertible_flag(
        "--disallow-any-generics",
        default=False,
        strict_flag=True,
        help="Disallow usage of generic types that do not specify explicit type parameters",
        group=disallow_any_group,
    )
    add_invertible_flag(
        "--disallow-any-unimported",
        default=False,
        help="Disallow Any types resulting from unfollowed imports",
        group=disallow_any_group,
    )
    add_invertible_flag(
        "--disallow-subclassing-any",
        default=False,
        strict_flag=True,
        help="Disallow subclassing values of type 'Any' when defining classes",
        group=disallow_any_group,
    )

    untyped_group = parser.add_argument_group(
        title="Untyped definitions and calls",
        description="Configure how untyped definitions and calls are handled. "
        "Note: by default, mypy ignores any untyped function definitions "
        "and assumes any calls to such functions have a return "
        "type of 'Any'.",
    )
    add_invertible_flag(
        "--disallow-untyped-calls",
        default=False,
        strict_flag=True,
        help="Disallow calling functions without type annotations"
        " from functions with type annotations",
        group=untyped_group,
    )
    untyped_group.add_argument(
        "--untyped-calls-exclude",
        metavar="MODULE",
        action="append",
        default=[],
        help="Disable --disallow-untyped-calls for functions/methods coming"
        " from specific package, module, or class",
    )
    add_invertible_flag(
        "--disallow-untyped-defs",
        default=False,
        strict_flag=True,
        help="Disallow defining functions without type annotations"
        " or with incomplete type annotations",
        group=untyped_group,
    )
    add_invertible_flag(
        "--disallow-incomplete-defs",
        default=False,
        strict_flag=True,
        help="Disallow defining functions with incomplete type annotations "
        "(while still allowing entirely unannotated definitions)",
        group=untyped_group,
    )
    add_invertible_flag(
        "--check-untyped-defs",
        default=False,
        strict_flag=True,
        help="Type check the interior of functions without type annotations",
        group=untyped_group,
    )
    add_invertible_flag(
        "--disallow-untyped-decorators",
        default=False,
        strict_flag=True,
        help="Disallow decorating typed functions with untyped decorators",
        group=untyped_group,
    )

    none_group = parser.add_argument_group(
        title="None and Optional handling",
        description="Adjust how values of type 'None' are handled. For more context on "
        "how mypy handles values of type 'None', see: "
        "https://mypy.readthedocs.io/en/stable/kinds_of_types.html#optional-types-and-the-none-type",
    )
    add_invertible_flag(
        "--implicit-optional",
        default=False,
        help="Assume arguments with default values of None are Optional",
        group=none_group,
    )
    none_group.add_argument("--strict-optional", action="store_true", help=argparse.SUPPRESS)
    none_group.add_argument(
        "--no-strict-optional",
        action="store_false",
        dest="strict_optional",
        help="Disable strict Optional checks (inverse: --strict-optional)",
    )

    # This flag is deprecated, Mypy only supports Python 3.9+
    add_invertible_flag(
        "--force-uppercase-builtins", default=False, help=argparse.SUPPRESS, group=none_group
    )

    add_invertible_flag(
        "--force-union-syntax", default=False, help=argparse.SUPPRESS, group=none_group
    )

    lint_group = parser.add_argument_group(
        title="Configuring warnings",
        description="Detect code that is sound but redundant or problematic.",
    )
    add_invertible_flag(
        "--warn-redundant-casts",
        default=False,
        strict_flag=True,
        help="Warn about casting an expression to its inferred type",
        group=lint_group,
    )
    add_invertible_flag(
        "--warn-unused-ignores",
        default=False,
        strict_flag=True,
        help="Warn about unneeded '# type: ignore' comments",
        group=lint_group,
    )
    add_invertible_flag(
        "--no-warn-no-return",
        dest="warn_no_return",
        default=True,
        help="Do not warn about functions that end without returning",
        group=lint_group,
    )
    add_invertible_flag(
        "--warn-return-any",
        default=False,
        strict_flag=True,
        help="Warn about returning values of type Any from non-Any typed functions",
        group=lint_group,
    )
    add_invertible_flag(
        "--warn-unreachable",
        default=False,
        strict_flag=False,
        help="Warn about statements or expressions inferred to be unreachable",
        group=lint_group,
    )
    add_invertible_flag(
        "--report-deprecated-as-note",
        default=False,
        strict_flag=False,
        help="Report importing or using deprecated features as notes instead of errors",
        group=lint_group,
    )
    lint_group.add_argument(
        "--deprecated-calls-exclude",
        metavar="MODULE",
        action="append",
        default=[],
        help="Disable deprecated warnings for functions/methods coming"
        " from specific package, module, or class",
    )

    # Note: this group is intentionally added here even though we don't add
    # --strict to this group near the end.
    #
    # That way, this group will appear after the various strictness groups
    # but before the remaining flags.
    # We add `--strict` near the end so we don't accidentally miss any strictness
    # flags that are added after this group.
    strictness_group = parser.add_argument_group(title="Miscellaneous strictness flags")

    add_invertible_flag(
        "--allow-untyped-globals",
        default=False,
        strict_flag=False,
        help="Suppress toplevel errors caused by missing annotations",
        group=strictness_group,
    )

    add_invertible_flag(
        "--allow-redefinition",
        default=False,
        strict_flag=False,
        help="Allow restricted, unconditional variable redefinition with a new type",
        group=strictness_group,
    )

    add_invertible_flag(
        "--allow-redefinition-new",
        default=False,
        strict_flag=False,
        help=argparse.SUPPRESS,  # This is still very experimental
        group=strictness_group,
    )

    add_invertible_flag(
        "--no-implicit-reexport",
        default=True,
        strict_flag=True,
        dest="implicit_reexport",
        help="Treat imports as private unless aliased",
        group=strictness_group,
    )

    add_invertible_flag(
        "--strict-equality",
        default=False,
        strict_flag=True,
        help="Prohibit equality, identity, and container checks for non-overlapping types",
        group=strictness_group,
    )

    add_invertible_flag(
        "--strict-bytes",
        default=False,
        strict_flag=True,
        help="Disable treating bytearray and memoryview as subtypes of bytes",
        group=strictness_group,
    )

    add_invertible_flag(
        "--extra-checks",
        default=False,
        strict_flag=True,
        help="Enable additional checks that are technically correct but may be impractical "
        "in real code. For example, this prohibits partial overlap in TypedDict updates, "
        "and makes arguments prepended via Concatenate positional-only",
        group=strictness_group,
    )

    strict_help = "Strict mode; enables the following flags: {}".format(
        ", ".join(strict_flag_names)
    )
    strictness_group.add_argument(
        "--strict", action="store_true", dest="special-opts:strict", help=strict_help
    )

    strictness_group.add_argument(
        "--disable-error-code",
        metavar="NAME",
        action="append",
        default=[],
        help="Disable a specific error code",
    )
    strictness_group.add_argument(
        "--enable-error-code",
        metavar="NAME",
        action="append",
        default=[],
        help="Enable a specific error code",
    )

    error_group = parser.add_argument_group(
        title="Configuring error messages",
        description="Adjust the amount of detail shown in error messages.",
    )
    add_invertible_flag(
        "--show-error-context",
        default=False,
        dest="show_error_context",
        help='Precede errors with "note:" messages explaining context',
        group=error_group,
    )
    add_invertible_flag(
        "--show-column-numbers",
        default=False,
        help="Show column numbers in error messages",
        group=error_group,
    )
    add_invertible_flag(
        "--show-error-end",
        default=False,
        help="Show end line/end column numbers in error messages."
        " This implies --show-column-numbers",
        group=error_group,
    )
    add_invertible_flag(
        "--hide-error-codes",
        default=False,
        help="Hide error codes in error messages",
        group=error_group,
    )
    add_invertible_flag(
        "--show-error-code-links",
        default=False,
        help="Show links to error code documentation",
        group=error_group,
    )
    add_invertible_flag(
        "--pretty",
        default=False,
        help="Use visually nicer output in error messages:"
        " Use soft word wrap, show source code snippets,"
        " and show error location markers",
        group=error_group,
    )
    add_invertible_flag(
        "--no-color-output",
        dest="color_output",
        default=True,
        help="Do not colorize error messages",
        group=error_group,
    )
    add_invertible_flag(
        "--no-error-summary",
        dest="error_summary",
        default=True,
        help="Do not show error stats summary",
        group=error_group,
    )
    add_invertible_flag(
        "--show-absolute-path",
        default=False,
        help="Show absolute paths to files",
        group=error_group,
    )
    error_group.add_argument(
        "--soft-error-limit",
        default=defaults.MANY_ERRORS_THRESHOLD,
        type=int,
        dest="many_errors_threshold",
        help=argparse.SUPPRESS,
    )

    incremental_group = parser.add_argument_group(
        title="Incremental mode",
        description="Adjust how mypy incrementally type checks and caches modules. "
        "Mypy caches type information about modules into a cache to "
        "let you speed up future invocations of mypy. Also see "
        "mypy's daemon mode: "
        "mypy.readthedocs.io/en/stable/mypy_daemon.html#mypy-daemon",
    )
    incremental_group.add_argument(
        "-i", "--incremental", action="store_true", help=argparse.SUPPRESS
    )
    incremental_group.add_argument(
        "--no-incremental",
        action="store_false",
        dest="incremental",
        help="Disable module cache (inverse: --incremental)",
    )
    incremental_group.add_argument(
        "--cache-dir",
        action="store",
        metavar="DIR",
        help="Store module cache info in the given folder in incremental mode "
        "(defaults to '{}')".format(defaults.CACHE_DIR),
    )
    add_invertible_flag(
        "--sqlite-cache",
        default=False,
        help="Use a sqlite database to store the cache",
        group=incremental_group,
    )
    incremental_group.add_argument(
        "--cache-fine-grained",
        action="store_true",
        help="Include fine-grained dependency information in the cache for the mypy daemon",
    )
    incremental_group.add_argument(
        "--skip-version-check",
        action="store_true",
        help="Allow using cache written by older mypy version",
    )
    incremental_group.add_argument(
        "--skip-cache-mtime-checks",
        action="store_true",
        help="Skip cache internal consistency checks based on mtime",
    )

    internals_group = parser.add_argument_group(
        title="Advanced options", description="Debug and customize mypy internals."
    )
    internals_group.add_argument("--pdb", action="store_true", help="Invoke pdb on fatal error")
    internals_group.add_argument(
        "--show-traceback", "--tb", action="store_true", help="Show traceback on fatal error"
    )
    internals_group.add_argument(
        "--raise-exceptions", action="store_true", help="Raise exception on fatal error"
    )
    internals_group.add_argument(
        "--custom-typing-module",
        metavar="MODULE",
        dest="custom_typing_module",
        help="Use a custom typing module",
    )
    internals_group.add_argument(
        "--old-type-inference", action="store_true", help=argparse.SUPPRESS
    )
    # Deprecated reverse variant of the above.
    internals_group.add_argument(
        "--new-type-inference", action="store_true", help=argparse.SUPPRESS
    )
    internals_group.add_argument(
        "--disable-expression-cache", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--enable-incomplete-feature",
        action="append",
        metavar="{" + ",".join(sorted(INCOMPLETE_FEATURES)) + "}",
        help="Enable support of incomplete/experimental features for early preview",
    )
    internals_group.add_argument(
        "--custom-typeshed-dir", metavar="DIR", help="Use the custom typeshed in DIR"
    )
    add_invertible_flag(
        "--warn-incomplete-stub",
        default=False,
        help="Warn if missing type annotation in typeshed, only relevant with"
        " --disallow-untyped-defs or --disallow-incomplete-defs enabled",
        group=internals_group,
    )
    internals_group.add_argument(
        "--shadow-file",
        nargs=2,
        metavar=("SOURCE_FILE", "SHADOW_FILE"),
        dest="shadow_file",
        action="append",
        help="When encountering SOURCE_FILE, read and type check "
        "the contents of SHADOW_FILE instead.",
    )
    internals_group.add_argument("--fast-exit", action="store_true", help=argparse.SUPPRESS)
    internals_group.add_argument(
        "--no-fast-exit", action="store_false", dest="fast_exit", help=argparse.SUPPRESS
    )
    # This flag is useful for mypy tests, where function bodies may be omitted. Plugin developers
    # may want to use this as well in their tests.
    add_invertible_flag(
        "--allow-empty-bodies", default=False, help=argparse.SUPPRESS, group=internals_group
    )
    # This undocumented feature exports limited line-level dependency information.
    internals_group.add_argument("--export-ref-info", action="store_true", help=argparse.SUPPRESS)

    report_group = parser.add_argument_group(
        title="Report generation", description="Generate a report in the specified format."
    )
    for report_type in sorted(defaults.REPORTER_NAMES):
        if report_type not in {"memory-xml"}:
            report_group.add_argument(
                f"--{report_type.replace('_', '-')}-report",
                metavar="DIR",
                dest=f"special-opts:{report_type}_report",
            )

    # Undocumented mypyc feature: generate annotated HTML source file
    report_group.add_argument(
        "-a", dest="mypyc_annotation_file", type=str, default=None, help=argparse.SUPPRESS
    )
    # Hidden mypyc feature: do not write any C files (keep existing ones and assume they exist).
    # This can be useful when debugging mypyc bugs.
    report_group.add_argument(
        "--skip-c-gen", dest="mypyc_skip_c_generation", action="store_true", help=argparse.SUPPRESS
    )

    other_group = parser.add_argument_group(title="Miscellaneous")
    other_group.add_argument("--quickstart-file", help=argparse.SUPPRESS)
    other_group.add_argument("--junit-xml", help="Write junit.xml to the given file")
    imports_group.add_argument(
        "--junit-format",
        choices=["global", "per_file"],
        default="global",
        help="If --junit-xml is set, specifies format. global: single test with all errors; per_file: one test entry per file with failures",
    )
    other_group.add_argument(
        "--find-occurrences",
        metavar="CLASS.MEMBER",
        dest="special-opts:find_occurrences",
        help="Print out all usages of a class member (experimental)",
    )
    other_group.add_argument(
        "--scripts-are-modules",
        action="store_true",
        help="Script x becomes module x instead of __main__",
    )

    add_invertible_flag(
        "--install-types",
        default=False,
        strict_flag=False,
        help="Install detected missing library stub packages using pip",
        group=other_group,
    )
    add_invertible_flag(
        "--non-interactive",
        default=False,
        strict_flag=False,
        help=(
            "Install stubs without asking for confirmation and hide "
            + "errors, with --install-types"
        ),
        group=other_group,
        inverse="--interactive",
    )

    if server_options:
        # TODO: This flag is superfluous; remove after a short transition (2018-03-16)
        other_group.add_argument(
            "--experimental",
            action="store_true",
            dest="fine_grained_incremental",
            help="Enable fine-grained incremental mode",
        )
        other_group.add_argument(
            "--use-fine-grained-cache",
            action="store_true",
            help="Use the cache in fine-grained incremental mode",
        )

    # hidden options
    parser.add_argument(
        "--stats", action="store_true", dest="dump_type_stats", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--inferstats", action="store_true", dest="dump_inference_stats", help=argparse.SUPPRESS
    )
    parser.add_argument("--dump-build-stats", action="store_true", help=argparse.SUPPRESS)
    # Dump timing stats for each processed file into the given output file
    parser.add_argument("--timing-stats", dest="timing_stats", help=argparse.SUPPRESS)
    # Dump per line type checking timing stats for each processed file into the given
    # output file. Only total time spent in each top level expression will be shown.
    # Times are show in microseconds.
    parser.add_argument(
        "--line-checking-stats", dest="line_checking_stats", help=argparse.SUPPRESS
    )
    # --debug-cache will disable any cache-related compressions/optimizations,
    # which will make the cache writing process output pretty-printed JSON (which
    # is easier to debug).
    parser.add_argument("--debug-cache", action="store_true", help=argparse.SUPPRESS)
    # --dump-deps will dump all fine-grained dependencies to stdout
    parser.add_argument("--dump-deps", action="store_true", help=argparse.SUPPRESS)
    # --dump-graph will dump the contents of the graph of SCCs and exit.
    parser.add_argument("--dump-graph", action="store_true", help=argparse.SUPPRESS)
    # --semantic-analysis-only does exactly that.
    parser.add_argument("--semantic-analysis-only", action="store_true", help=argparse.SUPPRESS)
    # Some tests use this to tell mypy that we are running a test.
    parser.add_argument("--test-env", action="store_true", help=argparse.SUPPRESS)
    # --local-partial-types disallows partial types spanning module top level and a function
    # (implicitly defined in fine-grained incremental mode)
    add_invertible_flag("--local-partial-types", default=False, help=argparse.SUPPRESS)
    # --logical-deps adds some more dependencies that are not semantically needed, but
    # may be helpful to determine relative importance of classes and functions for overall
    # type precision in a code base. It also _removes_ some deps, so this flag should be never
    # used except for generating code stats. This also automatically enables --cache-fine-grained.
    # NOTE: This is an experimental option that may be modified or removed at any time.
    parser.add_argument("--logical-deps", action="store_true", help=argparse.SUPPRESS)
    # --bazel changes some behaviors for use with Bazel (https://bazel.build).
    parser.add_argument("--bazel", action="store_true", help=argparse.SUPPRESS)
    # --package-root adds a directory below which directories are considered
    # packages even without __init__.py.  May be repeated.
    parser.add_argument(
        "--package-root", metavar="ROOT", action="append", default=[], help=argparse.SUPPRESS
    )
    # --cache-map FILE ... gives a mapping from source files to cache files.
    # Each triple of arguments is a source file, a cache meta file, and a cache data file.
    # Modules not mentioned in the file will go through cache_dir.
    # Must be followed by another flag or by '--' (and then only file args may follow).
    parser.add_argument(
        "--cache-map", nargs="+", dest="special-opts:cache_map", help=argparse.SUPPRESS
    )
    # --debug-serialize will run tree.serialize() even if cache generation is disabled.
    # Useful for mypy_primer to detect serialize errors earlier.
    parser.add_argument("--debug-serialize", action="store_true", help=argparse.SUPPRESS)

    parser.add_argument(
        "--disable-bytearray-promotion", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--disable-memoryview-promotion", action="store_true", help=argparse.SUPPRESS
    )
    # This flag is deprecated, it has been moved to --extra-checks
    parser.add_argument("--strict-concatenate", action="store_true", help=argparse.SUPPRESS)

    # options specifying code to check
    code_group = parser.add_argument_group(
        title="Running code",
        description="Specify the code you want to type check. For more details, see "
        "mypy.readthedocs.io/en/stable/running_mypy.html#running-mypy",
    )
    add_invertible_flag(
        "--explicit-package-bases",
        default=False,
        help="Use current directory and MYPYPATH to determine module names of files passed",
        group=code_group,
    )
    add_invertible_flag(
        "--fast-module-lookup", default=False, help=argparse.SUPPRESS, group=code_group
    )
    code_group.add_argument(
        "--exclude",
        action="append",
        metavar="PATTERN",
        default=[],
        help=(
            "Regular expression to match file names, directory names or paths which mypy should "
            "ignore while recursively discovering files to check, e.g. --exclude '/setup\\.py$'. "
            "May be specified more than once, eg. --exclude a --exclude b"
        ),
    )
    add_invertible_flag(
        "--exclude-gitignore",
        default=False,
        help=(
            "Use .gitignore file(s) to exclude files from checking "
            "(in addition to any explicit --exclude if present)"
        ),
        group=code_group,
    )
    code_group.add_argument(
        "-m",
        "--module",
        action="append",
        metavar="MODULE",
        default=[],
        dest="special-opts:modules",
        help="Type-check module; can repeat for more modules",
    )
    code_group.add_argument(
        "-p",
        "--package",
        action="append",
        metavar="PACKAGE",
        default=[],
        dest="special-opts:packages",
        help="Type-check package recursively; can be repeated",
    )
    code_group.add_argument(
        "-c",
        "--command",
        action="append",
        metavar="PROGRAM_TEXT",
        dest="special-opts:command",
        help="Type-check program passed in as string",
    )
    code_group.add_argument(
        metavar="files",
        nargs="*",
        dest="special-opts:files",
        help="Type-check given files or directories",
    )

    # Parse arguments once into a dummy namespace so we can get the
    # filename for the config file and know if the user requested all strict options.
    dummy = argparse.Namespace()
    parser.parse_args(args, dummy)
    config_file = dummy.config_file
    # Don't explicitly test if "config_file is not None" for this check.
    # This lets `--config-file=` (an empty string) be used to disable all config files.
    if config_file and not os.path.exists(config_file):
        parser.error(f"Cannot find config file '{config_file}'")

    options = Options()
    strict_option_set = False

    def set_strict_flags() -> None:
        nonlocal strict_option_set
        strict_option_set = True
        for dest, value in strict_flag_assignments:
            setattr(options, dest, value)

    # Parse config file first, so command line can override.
    parse_config_file(options, set_strict_flags, config_file, stdout, stderr)

    # Set strict flags before parsing (if strict mode enabled), so other command
    # line options can override.
    if getattr(dummy, "special-opts:strict"):
        set_strict_flags()

    # Override cache_dir if provided in the environment
    environ_cache_dir = os.getenv("MYPY_CACHE_DIR", "")
    if environ_cache_dir.strip():
        options.cache_dir = environ_cache_dir
    options.cache_dir = os.path.expanduser(options.cache_dir)

    # Parse command line for real, using a split namespace.
    special_opts = argparse.Namespace()
    parser.parse_args(args, SplitNamespace(options, special_opts, "special-opts:"))

    # The python_version is either the default, which can be overridden via a config file,
    # or stored in special_opts and is passed via the command line.
    options.python_version = special_opts.python_version or options.python_version
    if options.python_version < (3,):
        parser.error(
            "Mypy no longer supports checking Python 2 code. "
            "Consider pinning to mypy<0.980 if you need to check Python 2 code."
        )
    try:
        infer_python_executable(options, special_opts)
    except PythonExecutableInferenceError as e:
        parser.error(str(e))

    if special_opts.no_executable or options.no_site_packages:
        options.python_executable = None

    # Paths listed in the config file will be ignored if any paths, modules or packages
    # are passed on the command line.
    if not (special_opts.files or special_opts.packages or special_opts.modules):
        if options.files:
            special_opts.files = options.files
        if options.packages:
            special_opts.packages = options.packages
        if options.modules:
            special_opts.modules = options.modules

    # Check for invalid argument combinations.
    if require_targets:
        code_methods = sum(
            bool(c)
            for c in [
                special_opts.modules + special_opts.packages,
                special_opts.command,
                special_opts.files,
            ]
        )
        if code_methods == 0 and not options.install_types:
            parser.error("Missing target module, package, files, or command.")
        elif code_methods > 1:
            parser.error("May only specify one of: module/package, files, or command.")
    if options.explicit_package_bases and not options.namespace_packages:
        parser.error(
            "Can only use --explicit-package-bases with --namespace-packages, since otherwise "
            "examining __init__.py's is sufficient to determine module names for files"
        )

    # Check for overlapping `--always-true` and `--always-false` flags.
    overlap = set(options.always_true) & set(options.always_false)
    if overlap:
        parser.error(
            "You can't make a variable always true and always false (%s)"
            % ", ".join(sorted(overlap))
        )

    validate_package_allow_list(options.untyped_calls_exclude)
    validate_package_allow_list(options.deprecated_calls_exclude)

    options.process_error_codes(error_callback=parser.error)
    options.process_incomplete_features(error_callback=parser.error, warning_callback=print)

    # Compute absolute path for custom typeshed (if present).
    if options.custom_typeshed_dir is not None:
        options.abs_custom_typeshed_dir = os.path.abspath(options.custom_typeshed_dir)

    # Set build flags.
    if special_opts.find_occurrences:
        _find_occurrences = tuple(special_opts.find_occurrences.split("."))
        if len(_find_occurrences) < 2:
            parser.error("Can only find occurrences of class members.")
        if len(_find_occurrences) != 2:
            parser.error("Can only find occurrences of non-nested class members.")
        state.find_occurrences = _find_occurrences

    # Set reports.
    for flag, val in vars(special_opts).items():
        if flag.endswith("_report") and val is not None:
            report_type = flag[:-7].replace("_", "-")
            report_dir = val
            options.report_dirs[report_type] = report_dir

    # Process --package-root.
    if options.package_root:
        process_package_roots(fscache, parser, options)

    # Process --cache-map.
    if special_opts.cache_map:
        if options.sqlite_cache:
            parser.error("--cache-map is incompatible with --sqlite-cache")

        process_cache_map(parser, special_opts, options)

    # Process --strict-bytes
    options.process_strict_bytes()

    # An explicitly specified cache_fine_grained implies local_partial_types
    # (because otherwise the cache is not compatible with dmypy)
    if options.cache_fine_grained:
        options.local_partial_types = True

    #  Implicitly show column numbers if error location end is shown
    if options.show_error_end:
        options.show_column_numbers = True

    # Let logical_deps imply cache_fine_grained (otherwise the former is useless).
    if options.logical_deps:
        options.cache_fine_grained = True

    if options.new_type_inference:
        print(
            "Warning: --new-type-inference flag is deprecated;"
            " new type inference algorithm is already enabled by default"
        )

    if options.strict_concatenate and not strict_option_set:
        print("Warning: --strict-concatenate is deprecated; use --extra-checks instead")

    if options.force_uppercase_builtins:
        print("Warning: --force-uppercase-builtins is deprecated; mypy only supports Python 3.9+")

    # Set target.
    if special_opts.modules + special_opts.packages:
        options.build_type = BuildType.MODULE
        sys_path, _ = get_search_dirs(options.python_executable)
        search_paths = SearchPaths(
            (os.getcwd(),), tuple(mypy_path() + options.mypy_path), tuple(sys_path), ()
        )
        targets = []
        # TODO: use the same cache that the BuildManager will
        cache = FindModuleCache(search_paths, fscache, options)
        for p in special_opts.packages:
            if os.sep in p or os.altsep and os.altsep in p:
                fail(f"Package name '{p}' cannot have a slash in it.", stderr, options)
            p_targets = cache.find_modules_recursive(p)
            if not p_targets:
                reason = cache.find_module(p)
                if reason is ModuleNotFoundReason.FOUND_WITHOUT_TYPE_HINTS:
                    fail(
                        f"Package '{p}' cannot be type checked due to missing py.typed marker. See https://mypy.readthedocs.io/en/stable/installed_packages.html for more details",
                        stderr,
                        options,
                    )
                else:
                    fail(f"Can't find package '{p}'", stderr, options)
            targets.extend(p_targets)
        for m in special_opts.modules:
            targets.append(BuildSource(None, m, None))
        return targets, options
    elif special_opts.command:
        options.build_type = BuildType.PROGRAM_TEXT
        targets = [BuildSource(None, None, "\n".join(special_opts.command))]
        return targets, options
    else:
        try:
            targets = create_source_list(special_opts.files, options, fscache)
        # Variable named e2 instead of e to work around mypyc bug #620
        # which causes issues when using the same variable to catch
        # exceptions of different types.
        except InvalidSourceList as e2:
            fail(str(e2), stderr, options)
        return targets, options


def process_package_roots(
    fscache: FileSystemCache | None, parser: argparse.ArgumentParser, options: Options
) -> None:
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
            parser.error(f"Package root cannot be absolute: {root!r}")
        drive, root = os.path.splitdrive(root)
        if drive and drive != current_drive:
            parser.error(f"Package root must be on current drive: {drive + root!r}")
        # Empty package root is always okay.
        if root:
            root = os.path.relpath(root)  # Normalize the heck out of it.
            if not root.endswith(os.sep):
                root = root + os.sep
            if root.startswith(dotdotslash):
                parser.error(f"Package root cannot be above current directory: {root!r}")
            if root in trivial_paths:
                root = ""
        package_root.append(root)
    options.package_root = package_root
    # Pass the package root on the filesystem cache.
    fscache.set_package_root(package_root)


def process_cache_map(
    parser: argparse.ArgumentParser, special_opts: argparse.Namespace, options: Options
) -> None:
    """Validate cache_map and copy into options.cache_map."""
    n = len(special_opts.cache_map)
    if n % 3 != 0:
        parser.error("--cache-map requires one or more triples (see source)")
    for i in range(0, n, 3):
        source, meta_file, data_file = special_opts.cache_map[i : i + 3]
        if source in options.cache_map:
            parser.error(f"Duplicate --cache-map source {source})")
        if not source.endswith(".py") and not source.endswith(".pyi"):
            parser.error(f"Invalid --cache-map source {source} (triple[0] must be *.py[i])")
        if not meta_file.endswith(".meta.json"):
            parser.error(
                "Invalid --cache-map meta_file %s (triple[1] must be *.meta.json)" % meta_file
            )
        if not data_file.endswith(".data.json"):
            parser.error(
                "Invalid --cache-map data_file %s (triple[2] must be *.data.json)" % data_file
            )
        options.cache_map[source] = (meta_file, data_file)


def maybe_write_junit_xml(
    td: float,
    serious: bool,
    all_messages: list[str],
    messages_by_file: dict[str | None, list[str]],
    options: Options,
) -> None:
    if options.junit_xml:
        py_version = f"{options.python_version[0]}_{options.python_version[1]}"
        if options.junit_format == "global":
            util.write_junit_xml(
                td,
                serious,
                {None: all_messages} if all_messages else {},
                options.junit_xml,
                py_version,
                options.platform,
            )
        else:
            # per_file
            util.write_junit_xml(
                td, serious, messages_by_file, options.junit_xml, py_version, options.platform
            )


def fail(msg: str, stderr: TextIO, options: Options) -> NoReturn:
    """Fail with a serious error."""
    stderr.write(f"{msg}\n")
    maybe_write_junit_xml(
        0.0, serious=True, all_messages=[msg], messages_by_file={None: [msg]}, options=options
    )
    sys.exit(2)


def read_types_packages_to_install(cache_dir: str, after_run: bool) -> list[str]:
    if not os.path.isdir(cache_dir):
        if not after_run:
            sys.stderr.write(
                "error: Can't determine which types to install with no files to check "
                + "(and no cache from previous mypy run)\n"
            )
        else:
            sys.stderr.write(
                "error: --install-types failed (an error blocked analysis of which types to install)\n"
            )
    fnam = build.missing_stubs_file(cache_dir)
    if not os.path.isfile(fnam):
        # No missing stubs.
        return []
    with open(fnam) as f:
        return [line.strip() for line in f]


def install_types(
    formatter: util.FancyFormatter,
    options: Options,
    *,
    after_run: bool = False,
    non_interactive: bool = False,
) -> bool:
    """Install stub packages using pip if some missing stubs were detected."""
    packages = read_types_packages_to_install(options.cache_dir, after_run)
    if not packages:
        # If there are no missing stubs, generate no output.
        return False
    if after_run and not non_interactive:
        print()
    print("Installing missing stub packages:")
    assert options.python_executable, "Python executable required to install types"
    cmd = [options.python_executable, "-m", "pip", "install"] + packages
    print(formatter.style(" ".join(cmd), "none", bold=True))
    print()
    if not non_interactive:
        x = input("Install? [yN] ")
        if not x.strip() or not x.lower().startswith("y"):
            print(formatter.style("mypy: Skipping installation", "red", bold=True))
            sys.exit(2)
        print()
    subprocess.run(cmd)
    return True
