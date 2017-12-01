"""Client for mypy daemon mode.

Highly experimental!  Only supports UNIX-like systems.

This manages a daemon process which keeps useful state in memory
rather than having to read it back from disk on each run.
"""

import argparse
import json
import os
import signal
import socket
import sys
import time

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, TypeVar

from mypy.dmypy_util import STATUS_FILE, receive

# Argument parser.  Subparsers are tied to action functions by the
# @action(subparse) decorator.

parser = argparse.ArgumentParser(description="Client for mypy daemon mode",
                                 fromfile_prefix_chars='@')
parser.set_defaults(action=None)
subparsers = parser.add_subparsers()

start_parser = subparsers.add_parser('start', help="Start daemon")
start_parser.add_argument('--log-file', metavar='FILE', type=str,
                          help="Direct daemon stdout/stderr to FILE")
start_parser.add_argument('flags', metavar='FLAG', nargs='*', type=str,
                          help="Regular mypy flags (precede with --)")

status_parser = subparsers.add_parser('status', help="Show daemon status")

stop_parser = subparsers.add_parser('stop', help="Stop daemon (asks it politely to go away)")

kill_parser = subparsers.add_parser('kill', help="Kill daemon (kills the process)")

restart_parser = subparsers.add_parser('restart',
    help="Restart daemon (stop or kill followed by start)")
restart_parser.add_argument('--log-file', metavar='FILE', type=str,
                            help="Direct daemon stdout/stderr to FILE")
restart_parser.add_argument('flags', metavar='FLAG', nargs='*', type=str,
                            help="Regular mypy flags (precede with --)")

check_parser = subparsers.add_parser('check', help="Check some files (requires running daemon)")
check_parser.add_argument('-q', '--quiet', action='store_true',
                          help="Suppress instrumentation stats")
check_parser.add_argument('files', metavar='FILE', nargs='+', help="File (or directory) to check")

recheck_parser = subparsers.add_parser('recheck',
    help="Check the same files as the most previous  check run (requires running daemon)")
recheck_parser.add_argument('-q', '--quiet', action='store_true',
                            help="Suppress instrumentation stats")

hang_parser = subparsers.add_parser('hang', help="Hang for 100 seconds")

daemon_parser = subparsers.add_parser('daemon', help="Run daemon in foreground")
daemon_parser.add_argument('flags', metavar='FLAG', nargs='*', type=str,
                           help="Regular mypy flags (precede with --)")

help_parser = subparsers.add_parser('help')


def main() -> None:
    """The code is top-down."""
    args = parser.parse_args()
    if not args.action:
        parser.print_usage()
    else:
        args.action(args)


ActionFunction = Callable[[argparse.Namespace], None]


def action(subparser: argparse.ArgumentParser) -> Callable[[ActionFunction], None]:
    """Decorator to tie an action function to a subparser."""
    def register(func: ActionFunction) -> None:
        subparser.set_defaults(action=func)
    return register


# Action functions (run in client from command line).
# TODO: Use a separate exception instead of SystemExit to indicate failures.

@action(start_parser)
def do_start(args: argparse.Namespace) -> None:
    """Start daemon (it must not already be running).

    This is where mypy flags are set.  Setting flags is a bit awkward;
    you have to use e.g.:

      dmypy start -- --strict

    since we don't want to duplicate mypy's huge list of flags.
    """
    try:
        pid, sockname = get_status()
    except SystemExit as err:
        # Lazy import so this import doesn't slow down other commands.
        from mypy.dmypy_server import daemonize, Server
        if daemonize(Server(args.flags).serve, args.log_file):
            sys.exit(1)
        wait_for_server()
    else:
        sys.exit("Daemon is still alive")


@action(status_parser)
def do_status(args: argparse.Namespace) -> None:
    """Print daemon status.

    This verifies that it is responsive to requests.
    """
    status = read_status()
    show_stats(status)
    check_status(status)
    try:
        response = request('status')
    except Exception as err:
        print("Daemon is stuck; consider %s kill" % sys.argv[0])
        raise
    else:
        show_stats(response)


@action(stop_parser)
def do_stop(args: argparse.Namespace) -> None:
    """Stop daemon politely (via a request)."""
    try:
        response = request('stop')
    except Exception as err:
        sys.exit("Daemon is stuck; consider %s kill" % sys.argv[0])
    else:
        if response:
            print("Stop response:", response)
        else:
            print("Daemon stopped")


@action(kill_parser)
def do_kill(args: argparse.Namespace) -> None:
    """Kill daemon rudely (by killing the process)."""
    pid, sockname = get_status()
    try:
        os.kill(pid, signal.SIGKILL)
    except os.error as err:
        sys.exit(str(err))
    else:
        print("Daemon killed")


@action(restart_parser)
def do_restart(args: argparse.Namespace) -> None:
    """Restart daemon.

    We first try to stop it politely if it's running.  This also sets
    mypy flags (and has the same issues as start).
    """
    try:
        response = request('stop')
    except SystemExit:
        pass
    else:
        if response:
            sys.exit("Status: %s" % str(response))
        else:
            print("Daemon stopped")
    # Lazy import so this import doesn't slow down other commands.
    from mypy.dmypy_server import daemonize, Server
    if daemonize(Server(args.flags).serve, args.log_file):
        sys.exit(1)
    wait_for_server()


def wait_for_server(timeout: float = 5.0) -> None:
    """Wait until the server is up.

    Exit if it doesn't happen within the timeout.
    """
    endtime = time.time() + timeout
    while time.time() < endtime:
        try:
            data = read_status()
        except SystemExit:
            # If the file isn't there yet, retry later.
            time.sleep(0.1)
            continue
        # If the file's content is bogus or the process is dead, fail.
        pid, sockname = check_status(data)
        print("Daemon started")
        return
    sys.exit("Timed out waiting for daemon to start")


@action(check_parser)
def do_check(args: argparse.Namespace) -> None:
    """Ask the daemon to check a list of files."""
    t0 = time.time()
    response = request('check', files=args.files)
    t1 = time.time()
    response['roundtrip_time'] = t1 - t0
    check_output(response, args.quiet)


@action(recheck_parser)
def do_recheck(args: argparse.Namespace) -> None:
    """Ask the daemon to check the same list of files it checked most recently.

    This doesn't work across daemon restarts.
    """
    t0 = time.time()
    response = request('recheck')
    t1 = time.time()
    response['roundtrip_time'] = t1 - t0
    check_output(response, args.quiet)


def check_output(response: Dict[str, Any], quiet: bool) -> None:
    """Print the output from a check or recheck command."""
    try:
        out, err, status = response['out'], response['err'], response['status']
    except KeyError:
        sys.exit("Response: %s" % str(response))
    sys.stdout.write(out)
    sys.stderr.write(err)
    if not quiet:
        show_stats(response)
    if status:
        sys.exit(status)


def show_stats(response: Mapping[str, object]) -> None:
    for key, value in sorted(response.items()):
        if key not in ('out', 'err'):
            print("%-24s: %10s" % (key, "%.3f" % value if isinstance(value, float) else value))


@action(hang_parser)
def do_hang(args: argparse.Namespace) -> None:
    """Hang for 100 seconds, as a debug hack."""
    request('hang')


@action(daemon_parser)
def do_daemon(args: argparse.Namespace) -> None:
    """Serve requests in the foreground."""
    # Lazy import so this import doesn't slow down other commands.
    from mypy.dmypy_server import Server
    Server(args.flags).serve()


@action(help_parser)
def do_help(args: argparse.Namespace) -> None:
    """Print full help (same as dmypy --help)."""
    parser.print_help()


# Client-side infrastructure.


def request(command: str, **kwds: object) -> Dict[str, Any]:
    """Send a request to the daemon.

    Return the JSON dict with the response.
    """
    args = dict(kwds)
    if command:
        args.update(command=command)
    data = json.dumps(args)
    pid, sockname = get_status()
    sock = socket.socket(socket.AF_UNIX)
    sock.connect(sockname)
    sock.sendall(data.encode('utf8'))
    sock.shutdown(socket.SHUT_WR)
    try:
        response = receive(sock)
    except OSError as err:
        return {'error': str(err)}
    else:
        return response
    finally:
        sock.close()


def get_status() -> Tuple[int, str]:
    """Read status file and check if the process is alive.

    Return (pid, sockname) on success.

    Raise SystemExit(<message>) if something's wrong.
    """
    data = read_status()
    return check_status(data)


def check_status(data: Dict[str, Any]) -> Tuple[int, str]:
    """Check if the process is alive.

    Return (pid, sockname) on success.

    Raise SystemExit(<message>) if something's wrong.
    """
    if 'pid' not in data:
        raise SystemExit("Invalid status file (no pid field)")
    pid = data['pid']
    if not isinstance(pid, int):
        raise SystemExit("pid field is not an int")
    try:
        os.kill(pid, 0)
    except OSError as err:
        raise SystemExit("Daemon has died")
    if 'sockname' not in data:
        raise SystemExit("Invalid status file (no sockname field)")
    sockname = data['sockname']
    if not isinstance(sockname, str):
        raise SystemExit("sockname field is not a string")
    return pid, sockname


def read_status() -> Dict[str, object]:
    """Read status file."""
    if not os.path.isfile(STATUS_FILE):
        raise SystemExit("No status file found")
    with open(STATUS_FILE) as f:
        try:
            data = json.load(f)
        except Exception as err:
            raise SystemExit("Malformed status file (not JSON)")
    if not isinstance(data, dict):
        raise SystemExit("Invalid status file (not a dict)")
    return data


# Run main().

if __name__ == '__main__':
    main()
