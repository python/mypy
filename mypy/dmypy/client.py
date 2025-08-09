"""Client for mypy daemon mode.

This manages a daemon process which keeps useful state in memory
rather than having to read it back from disk on each run.
"""

from __future__ import annotations

import argparse
from argparse import Namespace
import base64
import json
import os
import pickle
import sys
import time
import traceback
from collections.abc import Mapping
from typing import Any, Callable, NoReturn, cast
from functools import partial
from textwrap import dedent

from mypy.dmypy.dmypy_os import alive, kill
from mypy.dmypy.util import DEFAULT_STATUS_FILE, receive, send
from mypy.ipc import IPCClient, IPCException
from mypy.main import RECURSION_LIMIT
from mypy.util import check_python_version, get_terminal_width, should_force_color
from mypy.version import __version__



class AugmentedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog: str, **kwargs: Any) -> None:
        super().__init__(prog=prog, max_help_position=30, **kwargs)


# Typing subparsers as Any because I'm lazy to figure out its type name :)
def _subparser_adder(subparsers: Any, *args: Any, **kwargs: Any) -> argparse.ArgumentParser:
    func = kwargs["action"]
    if "formatter_class" not in kwargs:
        kwargs["formatter_class"] = argparse.RawDescriptionHelpFormatter
    kwargs["description"] = dedent(func.__doc__)
    del kwargs["action"]
    p = cast(argparse.ArgumentParser, subparsers.add_parser(*args, **kwargs))
    p.set_defaults(action=func)
    return p


parser: argparse.ArgumentParser  # Initialized in init_parser which is called below

# Called after all action functions are defined
def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dmypy",
        description="Client for mypy daemon mode",
        fromfile_prefix_chars="@")
    if sys.version_info >= (3, 14):
        parser.color = True  # Set as init arg in 3.14

    parser.set_defaults(action=None)
    parser.add_argument("--status-file", default=DEFAULT_STATUS_FILE,
                        help="status file to retrieve daemon details")
    parser.add_argument("-V", "--version", action="version", version="%(prog)s " + __version__,
                        help="Show program's version number and exit")

    subparsers = parser.add_subparsers()
    add_subparser = partial(_subparser_adder, subparsers)

    p = add_subparser("start", action=start_action,
                      help="Start daemon (exits with error if already running)")
    p.add_argument("--log-file", metavar="FILE", type=str,
                   help="Direct daemon stdout/stderr to FILE")
    p.add_argument("--timeout", metavar="TIMEOUT", type=int,
                   help="Server shutdown timeout (in seconds)")
    p.add_argument("--ok-if-running", action="store_true",
                   help="Don't exit with error if daemon is already running")
    p.add_argument("flags", metavar="FLAG", nargs="*", type=str,
                   help="Regular mypy flags (precede with --)")

    p = add_subparser("restart", action=restart_action,
                      help="Restart daemon (stop or kill followed by start)")
    p.add_argument("--log-file", metavar="FILE", type=str,
                   help="Direct daemon stdout/stderr to FILE")
    p.add_argument("--timeout", metavar="TIMEOUT", type=int,
                   help="Server shutdown timeout (in seconds)")
    p.add_argument("flags", metavar="FLAG", nargs="*", type=str,
                   help="Regular mypy flags (precede with --)")

    p = add_subparser("status", action=status_action,
                      help="Show daemon status")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Print detailed status")
    p.add_argument("--fswatcher-dump-file",
                   help="Collect information about the current file state")

    add_subparser("stop", action=stop_action,
                  help="Stop daemon (asks it politely to go away)")

    add_subparser("kill", action=kill_action,
                  help="Kill daemon (kills the process)")

    p = add_subparser("check", action=check_action, formatter_class=AugmentedHelpFormatter,
                      help="Check some files (requires daemon)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Print detailed status")
    p.add_argument("-q", "--quiet", action="store_true",
                   help=argparse.SUPPRESS)  # Deprecated
    p.add_argument("--junit-xml",
                   help="Write junit.xml to the given file")
    p.add_argument("--perf-stats-file",
                   help="write performance information to the given file")
    p.add_argument("files", metavar="FILE", nargs="+",
                   help="File (or directory) to check")
    p.add_argument("--export-types", action="store_true",
                   help="Store types of all expressions in a shared location (useful for inspections)")

    p = add_subparser("run", action=run_action, formatter_class=AugmentedHelpFormatter,
                      help="Check some files, [re]starting daemon if necessary")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Print detailed status")
    p.add_argument("--junit-xml",
                   help="Write junit.xml to the given file")
    p.add_argument("--perf-stats-file",
                   help="write performance information to the given file")
    p.add_argument("--timeout", metavar="TIMEOUT", type=int,
                   help="Server shutdown timeout (in seconds)")
    p.add_argument("--log-file", metavar="FILE", type=str,
                   help="Direct daemon stdout/stderr to FILE")
    p.add_argument("--export-types", action="store_true",
                   help="Store types of all expressions in a shared location (useful for inspections)")
    p.add_argument("flags", metavar="ARG", nargs="*", type=str,
                   help="Regular mypy flags and files (precede with --)")

    p = add_subparser("recheck", action=recheck_action, formatter_class=AugmentedHelpFormatter,
                      help="Re-check the previous list of files, with optional modifications (requires daemon)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Print detailed status")
    p.add_argument("-q", "--quiet", action="store_true",
                   help=argparse.SUPPRESS)  # Deprecated
    p.add_argument("--junit-xml",
                   help="Write junit.xml to the given file")
    p.add_argument("--perf-stats-file",
                   help="write performance information to the given file")
    p.add_argument("--export-types", action="store_true",
                   help="Store types of all expressions in a shared location (useful for inspections)")
    p.add_argument("--update", metavar="FILE", nargs="*",
                   help="Files in the run to add or check again (default: all from previous run)")
    p.add_argument("--remove", metavar="FILE", nargs="*",
                   help="Files to remove from the run")

    p = add_subparser("suggest", action=suggest_action,
                      help="Suggest a signature or show call sites for a specific function")
    p.add_argument("function", metavar="FUNCTION", type=str,
                   help="Function specified as '[package.]module.[class.]function'")
    p.add_argument("--json", action="store_true",
                   help="Produce json that pyannotate can use to apply a suggestion")
    p.add_argument("--no-errors", action="store_true",
                   help="Only produce suggestions that cause no errors")
    p.add_argument("--no-any", action="store_true",
                   help="Only produce suggestions that don't contain Any")
    p.add_argument("--flex-any", type=float,
                   help="Allow anys in types if they go above a certain score (scores are from 0-1)")
    p.add_argument("--callsites", action="store_true",
                   help="Find callsites instead of suggesting a type")
    p.add_argument("--use-fixme", metavar="NAME", type=str,
                   help="A dummy name to use instead of Any for types that can't be inferred")
    p.add_argument("--max-guesses", type=int,
                   help="Set the maximum number of types to try for a function (default 64)")

    p = add_subparser("inspect", action=inspect_action,
                      help="Locate and statically inspect expression(s)")
    p.add_argument("location", metavar="LOCATION", type=str,
                   help="Location specified as path/to/file.py:line:column[:end_line:end_column]."
                        " If position is given (i.e. only line and column), this will return all"
                        " enclosing expressions")
    p.add_argument("--show", metavar="INSPECTION", type=str, default="type",
                   choices=["type", "attrs", "definition"],
                   help="What kind of inspection to run")
    p.add_argument("--verbose", "-v", action="count", default=0,
                   help="Increase verbosity of the type string representation (can be repeated)")
    p.add_argument("--limit", metavar="NUM", type=int, default=0,
                   help="Return at most NUM innermost expressions (if position is given); 0 means no limit")
    p.add_argument("--include-span", action="store_true",
                   help="Prepend each inspection result with the span of corresponding expression"
                        ' (e.g. 1:2:3:4:"int")')
    p.add_argument("--include-kind", action="store_true",
                   help="Prepend each inspection result with the kind of corresponding expression"
                        ' (e.g. NameExpr:"int")')
    p.add_argument("--include-object-attrs", action="store_true",
                   help='Include attributes of "object" in "attrs" inspection')
    p.add_argument("--union-attrs", action="store_true",
                   help="Include attributes valid for some of possible expression types"
                        " (by default an intersection is returned)")
    p.add_argument("--force-reload", action="store_true",
                   help="Re-parse and re-type-check file before inspection (may be slow)")

    add_subparser("hang", action=hang_action,
                  help="Hang for 100 seconds")

    p = add_subparser("daemon", action=daemon_action,
                      help="Run daemon in foreground")
    p.add_argument("--timeout", metavar="TIMEOUT", type=int,
                   help="Server shutdown timeout (in seconds)")
    p.add_argument("--log-file", metavar="FILE", type=str,
                   help="Direct daemon stdout/stderr to FILE")
    p.add_argument("flags", metavar="FLAG", nargs="*", type=str,
                   help="Regular mypy flags (precede with --)")
    p.add_argument("--options-data",
                   help=argparse.SUPPRESS)  # Used in server.py

    add_subparser("help", action=help_action)

    return parser


# The code is top-down.

def main(argv: list[str]) -> None:
    check_python_version("dmypy")

    # set recursion limit consistent with mypy/main.py
    sys.setrecursionlimit(RECURSION_LIMIT)

    args = parser.parse_args(argv)
    if not args.action:
        parser.print_usage()
    else:
        try:
            args.action(args)
        except BadStatus as err:
            fail(err.args[0])
        except Exception:
            # We do this explicitly to avoid exceptions percolating up
            # through mypy.api invocations
            traceback.print_exc()
            sys.exit(2)


class BadStatus(Exception):
    """Exception raised when there is something wrong with the status file.

    For example:
    - No status file found
    - Status file malformed
    - Process whose pid is in the status file does not exist
    """


def fail(msg: str) -> NoReturn:
    print(msg, file=sys.stderr)
    sys.exit(2)


# Action functions (run in client from command line).


def start_action(args: Namespace) -> None:
    """Start daemon (it must not already be running).

    This is where mypy flags are set from the command line.

    Setting mypy flags (not daemon flags) is a bit awkward; you have to use e.g.:

        dmypy start -- --strict

    since we don't want to duplicate mypy's huge list of flags.
    """
    try:
        get_status(args.status_file)
    except BadStatus:
        # Bad or missing status file or dead process; good to start.
        pass
    else:
        fail("Daemon is still alive")
    start_server(args)


def restart_action(args: Namespace) -> None:
    """Restart daemon (it may or may not be running; but not hanging).

    We first try to stop it politely if it's running.
    """
    restart_server(args)


def run_action(args: Namespace) -> None:
    """Do a check, starting (or restarting) the daemon as necessary

    Restarts the daemon if the running daemon reports that it is
    required (due to a configuration change, for example).

    Setting mypy flags (not daemon flags) is a bit awkward; you have to use e.g.:

        dmypy run -- --strict a.py b.py ...

    since we don't want to duplicate mypy's huge list of flags.
    (The -- is only necessary if flags are specified.)
    """
    if not is_running(args.status_file):
        # Bad or missing status file or dead process; good to start.
        start_server(args, allow_sources=True)
    t0 = time.time()
    response = request(
        args.status_file,
        "run",
        version=__version__,
        args=args.flags,
        export_types=args.export_types,
    )
    # If the daemon signals that a restart is necessary, do it
    if "restart" in response:
        print(f"Restarting: {response['restart']}")
        restart_server(args, allow_sources=True)
        response = request(
            args.status_file,
            "run",
            version=__version__,
            args=args.flags,
            export_types=args.export_types,
        )

    t1 = time.time()
    response["roundtrip_time"] = t1 - t0
    check_output(response, args.verbose, args.junit_xml, args.perf_stats_file)


def status_action(args: Namespace) -> None:
    """Print daemon status.

    This verifies that it is responsive to requests.
    """
    status = read_status(args.status_file)
    if args.verbose:
        show_stats(status)
    # Both check_status() and request() may raise BadStatus,
    # which will be handled by main().
    check_status(status)
    response = request(
        args.status_file, "status", fswatcher_dump_file=args.fswatcher_dump_file, timeout=5
    )
    if args.verbose or "error" in response:
        show_stats(response)
    if "error" in response:
        fail(f"Daemon may be busy processing; if this persists, consider {sys.argv[0]} kill")
    print("Daemon is up and running")


def stop_action(args: Namespace) -> None:
    """Stop daemon via a 'stop' request."""
    # May raise BadStatus, which will be handled by main().
    response = request(args.status_file, "stop", timeout=5)
    if "error" in response:
        show_stats(response)
        fail(f"Daemon may be busy processing; if this persists, consider {sys.argv[0]} kill")
    else:
        print("Daemon stopped")


def kill_action(args: Namespace) -> None:
    """Kill daemon process with SIGKILL."""
    pid, _ = get_status(args.status_file)
    try:
        kill(pid)
    except OSError as err:
        fail(str(err))
    else:
        print("Daemon killed")


def check_action(args: Namespace) -> None:
    """Ask the daemon to check a list of files."""
    t0 = time.time()
    response = request(args.status_file, "check", files=args.files, export_types=args.export_types)
    t1 = time.time()
    response["roundtrip_time"] = t1 - t0
    check_output(response, args.verbose, args.junit_xml, args.perf_stats_file)


def recheck_action(args: Namespace) -> None:
    """Ask the daemon to recheck the previous list of files, with optional modifications.

    If at least one of --remove or --update is given, the server will
    update the list of files to check accordingly and assume that any other files
    are unchanged.  If none of these flags are given, the server will call stat()
    on each file last checked to determine its status.

    Files given in --update ought to exist.  Files given in --remove need not exist;
    if they don't they will be ignored.
    The lists may be empty but oughtn't contain duplicates or overlap.

    NOTE: The list of files is lost when the daemon is restarted.
    """
    t0 = time.time()
    if args.remove is not None or args.update is not None:
        response = request(
            args.status_file,
            "recheck",
            export_types=args.export_types,
            remove=args.remove,
            update=args.update,
        )
    else:
        response = request(args.status_file, "recheck", export_types=args.export_types)
    t1 = time.time()
    response["roundtrip_time"] = t1 - t0
    check_output(response, args.verbose, args.junit_xml, args.perf_stats_file)


def suggest_action(args: Namespace) -> None:
    """Ask the daemon for a suggested signature.

    This just prints whatever the daemon reports as output.
    For now it may be closer to a list of call sites.
    """
    response = request(
        args.status_file,
        "suggest",
        function=args.function,
        json=args.json,
        callsites=args.callsites,
        no_errors=args.no_errors,
        no_any=args.no_any,
        flex_any=args.flex_any,
        use_fixme=args.use_fixme,
        max_guesses=args.max_guesses,
    )
    check_output(response, verbose=False, junit_xml=None, perf_stats_file=None)


def inspect_action(args: Namespace) -> None:
    """Ask daemon to print the type of an expression."""
    response = request(
        args.status_file,
        "inspect",
        show=args.show,
        location=args.location,
        verbosity=args.verbose,
        limit=args.limit,
        include_span=args.include_span,
        include_kind=args.include_kind,
        include_object_attrs=args.include_object_attrs,
        union_attrs=args.union_attrs,
        force_reload=args.force_reload,
    )
    check_output(response, verbose=False, junit_xml=None, perf_stats_file=None)


def hang_action(args: Namespace) -> None:
    """Hang for 100 seconds."""
    # Used as a debug hack.
    print(request(args.status_file, "hang", timeout=1))


def daemon_action(args: Namespace) -> None:
    """Serve requests in the foreground."""
    # Lazy import so this import doesn't slow down other commands.
    from mypy.dmypy.server import Server, process_start_options

    if args.log_file:
        sys.stdout = sys.stderr = open(args.log_file, "a", buffering=1)
        fd = sys.stdout.fileno()
        os.dup2(fd, 2)
        os.dup2(fd, 1)

    if args.options_data:
        from mypy.options import Options

        options_dict = pickle.loads(base64.b64decode(args.options_data))
        options_obj = Options()
        options = options_obj.apply_changes(options_dict)
    else:
        options = process_start_options(args.flags, allow_sources=False)

    Server(options, args.status_file, timeout=args.timeout).serve()


def help_action(args: Namespace) -> None:
    """Print full help (same as dmypy --help)."""
    parser.print_help()


parser = init_parser()


def start_server(args: Namespace, allow_sources: bool = False) -> None:
    """Start the server from arguments and wait for it."""
    # Lazy import so this import doesn't slow down other commands.
    from mypy.dmypy.server import daemonize, process_start_options

    start_options = process_start_options(args.flags, allow_sources)
    if daemonize(start_options, args.status_file, timeout=args.timeout, log_file=args.log_file):
        sys.exit(2)
    wait_for_server(args.status_file)


def restart_server(args: Namespace, allow_sources: bool = False) -> None:
    """Restart daemon (it may or may not be running; but not hanging)."""
    try:
        stop_action(args)
    except BadStatus:
        # Bad or missing status file or dead process; good to start.
        pass
    start_server(args, allow_sources)


def wait_for_server(status_file: str, timeout: float = 5.0) -> None:
    """Wait until the server is up.

    Exit if it doesn't happen within the timeout.
    """
    endtime = time.time() + timeout
    while time.time() < endtime:
        try:
            data = read_status(status_file)
        except BadStatus:
            # If the file isn't there yet, retry later.
            time.sleep(0.1)
            continue
        # If the file's content is bogus or the process is dead, fail.
        check_status(data)
        print("Daemon started")
        return
    fail("Timed out waiting for daemon to start")


def check_output(
    response: dict[str, Any], verbose: bool, junit_xml: str | None, perf_stats_file: str | None
) -> None:
    """Print the output from a check or recheck command.

    Call sys.exit() unless the status code is zero.
    """
    if os.name == "nt":
        # Enable ANSI color codes for Windows cmd using this strange workaround
        # ( see https://github.com/python/cpython/issues/74261 )
        os.system("")
    if "error" in response:
        fail(response["error"])
    try:
        out, err, status_code = response["out"], response["err"], response["status"]
    except KeyError:
        fail(f"Response: {str(response)}")
    sys.stdout.write(out)
    sys.stdout.flush()
    sys.stderr.write(err)
    sys.stderr.flush()
    if verbose:
        show_stats(response)
    if junit_xml:
        # Lazy import so this import doesn't slow things down when not writing junit
        from mypy.util import write_junit_xml

        messages = (out + err).splitlines()
        write_junit_xml(
            response["roundtrip_time"],
            bool(err),
            {None: messages} if messages else {},
            junit_xml,
            response["python_version"],
            response["platform"],
        )
    if perf_stats_file:
        telemetry = response.get("stats", {})
        with open(perf_stats_file, "w") as f:
            json.dump(telemetry, f)

    if status_code:
        sys.exit(status_code)


def show_stats(response: Mapping[str, object]) -> None:
    for key, value in sorted(response.items()):
        if key in ("out", "err", "stdout", "stderr"):
            # Special case text output to display just 40 characters of text
            value = repr(value)[1:-1]
            if len(value) > 50:
                value = f"{value[:40]} ... {len(value)-40} more characters"
            print("%-24s: %s" % (key, value))
            continue
        print("%-24s: %10s" % (key, "%.3f" % value if isinstance(value, float) else value))



# Client-side infrastructure.


def request(
    status_file: str, command: str, *, timeout: int | None = None, **kwds: object
) -> dict[str, Any]:
    """Send a request to the daemon.

    Return the JSON dict with the response.

    Raise BadStatus if there is something wrong with the status file
    or if the process whose pid is in the status file has died.

    Return {'error': <message>} if an IPC operation or receive()
    raised OSError.  This covers cases such as connection refused or
    closed prematurely as well as invalid JSON received.
    """
    response: dict[str, str] = {}
    args = dict(kwds)
    args["command"] = command
    # Tell the server whether this request was initiated from a human-facing terminal,
    # so that it can format the type checking output accordingly.
    args["is_tty"] = sys.stdout.isatty() or should_force_color()
    args["terminal_width"] = get_terminal_width()
    _, name = get_status(status_file)
    try:
        with IPCClient(name, timeout) as client:
            send(client, args)

            final = False
            while not final:
                response = receive(client)
                final = bool(response.pop("final", False))
                # Display debugging output written to stdout/stderr in the server process for convenience.
                # This should not be confused with "out" and "err" fields in the response.
                # Those fields hold the output of the "check" command, and are handled in check_output().
                stdout = response.pop("stdout", None)
                if stdout:
                    sys.stdout.write(stdout)
                stderr = response.pop("stderr", None)
                if stderr:
                    sys.stderr.write(stderr)
    except (OSError, IPCException) as err:
        return {"error": str(err)}
    # TODO: Other errors, e.g. ValueError, UnicodeError

    return response


def get_status(status_file: str) -> tuple[int, str]:
    """Read status file and check if the process is alive.

    Return (pid, connection_name) on success.

    Raise BadStatus if something's wrong.
    """
    data = read_status(status_file)
    return check_status(data)


def check_status(data: dict[str, Any]) -> tuple[int, str]:
    """Check if the process is alive.

    Return (pid, connection_name) on success.

    Raise BadStatus if something's wrong.
    """
    if "pid" not in data:
        raise BadStatus("Invalid status file (no pid field)")
    pid = data["pid"]
    if not isinstance(pid, int):
        raise BadStatus("pid field is not an int")
    if not alive(pid):
        raise BadStatus("Daemon has died")
    if "connection_name" not in data:
        raise BadStatus("Invalid status file (no connection_name field)")
    connection_name = data["connection_name"]
    if not isinstance(connection_name, str):
        raise BadStatus("connection_name field is not a string")
    return pid, connection_name


def read_status(status_file: str) -> dict[str, object]:
    """Read status file.

    Raise BadStatus if the status file doesn't exist or contains
    invalid JSON or the JSON is not a dict.
    """
    if not os.path.isfile(status_file):
        raise BadStatus("No status file found")
    with open(status_file) as f:
        try:
            data = json.load(f)
        except Exception as e:
            raise BadStatus("Malformed status file (not JSON)") from e
    if not isinstance(data, dict):
        raise BadStatus("Invalid status file (not a dict)")
    return data


def is_running(status_file: str) -> bool:
    """Check if the server is running cleanly"""
    try:
        get_status(status_file)
    except BadStatus:
        return False
    return True


# Run main().
def console_entry() -> None:
    main(sys.argv[1:])
