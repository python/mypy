"""Client for mypy daemon mode.

Highly experimental!  Only supports UNIX-like systems.

This manages a daemon process which keeps useful state in memory
rather than having to read it back from disk on each run.
"""

import argparse
import io
import json
import os
import signal
import socket
import sys
import time

from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple, TypeVar
from mypy_extensions import NoReturn

import mypy.build
import mypy.errors
import mypy.main

# Argument parser.  Subparsers are tied to action functions by the
# @action(subparse) decorator.

parser = argparse.ArgumentParser(description="Client for mymy daemon mode",
                                 fromfile_prefix_chars='@')
parser.set_defaults(action=None)
subparsers = parser.add_subparsers()

start_parser = subparsers.add_parser('start', help="Start daemon")
start_parser.add_argument('flags', metavar='FLAG', nargs='*', type=str,
                          help="Regular mypy flags (precede with --)")

status_parser = subparsers.add_parser('status', help="Show daemon status")

stop_parser = subparsers.add_parser('stop', help="Stop daemon (asks it politely to go away)")

kill_parser = subparsers.add_parser('kill', help="Kill daemon (kills the process)")

restart_parser = subparsers.add_parser('restart',
    help="Restart daemon (stop or kill followed by start)")
restart_parser.add_argument('flags', metavar='FLAG', nargs='*', type=str,
                            help="Regular mypy flags (precede with --)")

check_parser = subparsers.add_parser('check', help="Check some files (requires running daemon)")
check_parser.add_argument('files', metavar='FILE', nargs='+', help="File (or directory) to check")

recheck_parser = subparsers.add_parser('recheck',
    help="Check the same files as the most previous  check run (requires running daemon)")

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
        daemonize(Server(args.flags).serve)
    else:
        sys.exit("Daemon is still alive")


@action(status_parser)
def do_status(args: argparse.Namespace) -> None:
    """Print daemon status.

    This verifies that it is responsive to requests.
    """
    pid, sockname = get_status()
    print("pid: %d" % pid)
    print("sockname: %s" % sockname)
    try:
        status = request('status')
    except Exception as err:
        print("Daemon is stuck; consider %s kill" % sys.argv[0])
    else:
        print("Status response:", status)


@action(stop_parser)
def do_stop(args: argparse.Namespace) -> None:
    """Stop daemon politely (via a request)."""
    try:
        status = request('stop')
    except Exception as err:
        sys.exit("Daemon is stuck; consider %s kill" % sys.argv[0])
    else:
        if status:
            print("Stop response:", status)
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
        status = request('stop')
    except SystemExit:
        pass
    else:
        if status:
            sys.exit("Status: %s" % str(status))
        else:
            print("Daemon stopped")
    daemonize(Server(args.flags).serve)


@action(check_parser)
def do_check(args: argparse.Namespace) -> None:
    """Ask the daemon to check a list of files."""
    response = request('check', files=args.files)
    check_output(response)


@action(recheck_parser)
def do_recheck(args: argparse.Namespace) -> None:
    """Ask the daemon to check the same list of files it checked most recently.

    This doesn't work across daemon restarts.
    """
    response = request('recheck')
    check_output(response)


def check_output(response: Dict[str, Any]) -> None:
    """Print the output from a check or recheck command."""
    try:
        out, err, status = response['out'], response['err'], response['status']
    except KeyError:
        sys.exit("Response: %s" % str(response))
    sys.stdout.write(out)
    sys.stderr.write(err)
    sys.exit(status)


@action(hang_parser)
def do_hang(args: argparse.Namespace) -> None:
    """Hang for 100 seconds, as a debug hack."""
    request('hang')


@action(daemon_parser)
def do_daemon(args: argparse.Namespace) -> None:
    """Serve requests in the foreground."""
    Server(args.flags).serve()


@action(help_parser)
def do_help(args: argparse.Namespace) -> None:
    """Print full help (same as dmypy --help)."""
    parser.print_help()


# Client-side infrastructure.

STATUS_FILE = 'dmypy.json'

def request(command: str, **kwds: object) -> Dict[str, Any]:
    """Send a request to the daemon."""
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
    if not os.path.isfile(STATUS_FILE):
        raise SystemExit("No status file found")
    with open(STATUS_FILE) as f:
        try:
            data = json.load(f)
        except Exception as err:
            raise SystemExit("Malformed status file")
    if not isinstance(data, dict) or 'pid' not in data:
        raise SystemExit("Invalid status file")
    pid = data['pid']
    sockname = data['sockname']
    try:
        os.kill(pid, 0)
    except OSError as err:
        raise SystemExit("Daemon has died")
    return pid, sockname


def daemonize(func: Callable[[], NoReturn]) -> None:
    """Arrange to call func() in a grandchild of the current process."""
    # See https://stackoverflow.com/questions/473620/how-do-you-create-a-daemon-in-python
    sys.stdout.flush()
    sys.stderr.flush()
    pid = os.fork()
    if pid:
        print("Daemon started")
        return
    # Child
    try:
        os.setsid()  # Detach controlling terminal
        os.umask(0o27)
        devnull = os.open('/dev/null', os.O_RDWR)
        os.dup2(devnull, 0)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        os.close(devnull)
        pid = os.fork()
        if pid:
            os._exit(0)
        # Grandchild
        func()
    finally:
        # Make sure we never get back into the caller.
        os._exit(1)


# Server code.

SOCKET_NAME = 'dmypy.sock'  # In current directory.

class Server:

    # NOTE: the instance is constructed in the parent process but
    # serve() is called in the grandchild (by daemonize()).

    def __init__(self, flags: List[str]) -> None:
        """Initialize the server with the desired mypy flags."""
        sources, options = mypy.main.process_options(['-i'] + flags, False)
        if sources:
            sys.exit("dmypy: start/restart does not accept sources")
        if options.report_dirs:
            sys.exit("dmypy: start/restart cannot generate reports")
        if not options.incremental:
            sys.exit("dmypy: start/restart should not disable incremental mode")
        if options.quick_and_dirty:
            sys.exit("dmypy: start/restart should not specify quick_and_dirty mode")
        self.options = options
        ## os.stat = mypy.main.stat_proxy  # XXX

    def serve(self) -> NoReturn:
        """Serve a single request, synchronously (no thread or fork)."""
        sock = self.create_listening_socket()
        with open(STATUS_FILE, 'w') as f:
            json.dump({'pid': os.getpid(), 'sockname': sock.getsockname()}, f)
            f.write('\n')  # I like my JSON with trailing newline
        while True:
            conn, addr = sock.accept()
            data = receive(conn)
            resp = None  # type: Dict[str, Any]
            if 'command' not in data:
                resp = {'error': "No command found in request"}
            else:
                command = data['command']
                if not isinstance(command, str):
                    resp = {'error': "Command is not a string"}
                else:
                    command = data.pop('command')
                resp = self.run_command(command, data)
            try:
                conn.sendall(json.dumps(resp).encode('utf8'))
            except OSError as err:
                pass  # Maybe the client hung up
            conn.close()
            if command == 'stop':
                sock.close()
                sys.exit(0)

    def create_listening_socket(self) -> socket.socket:
        """Create the socket and set it up for listening."""
        self.sockname = os.path.abspath(SOCKET_NAME)
        if os.path.exists(self.sockname):
            os.unlink(self.sockname)
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(self.sockname)
        sock.listen(1)
        return sock

    def run_command(self, command: str, data: Mapping[str, object]) -> Dict[str, object]:
        """Run a specific command from the registry."""
        key = 'cmd_' + command
        method = getattr(self.__class__, key, None)
        if method is None:
            return {'error': "Unrecognized command '%s'" % command}
        else:
            return method(self, **data)

    # Command functions (run in the server via RPC).

    def cmd_status(self) -> Dict[str, object]:
        """Return daemon status."""
        return {'status': "I'm alive!"}


    def cmd_stop(self) -> Dict[str, object]:
        """Stop daemon."""
        os.unlink(self.sockname)
        os.unlink(STATUS_FILE)
        return {}

    last_sources = None

    def cmd_check(self, files: Sequence[str]) -> Dict[str, object]:
        """Check a list of files."""
        # TODO: Move this into check(), in case one of the args is a directory.
        # Capture stdout/stderr and catch SystemExit while processing the source list.
        save_stdout = sys.stdout
        save_stderr = sys.stderr
        try:
            sys.stdout = stdout = io.StringIO()
            sys.stderr = stderr = io.StringIO()
            self.last_sources = mypy.main.create_source_list(files, self.options)
        except SystemExit as err:
            return {'out': stdout.getvalue(), 'err': stderr.getvalue(), 'status': err.code}
        finally:
            sys.stdout = save_stdout
            sys.stderr = save_stderr
        return self.check()

    def cmd_recheck(self) -> Dict[str, object]:
        """Check the same list of files we checked most recently."""
        if not self.last_sources:
            return {'error': "Command 'recheck' is only valid after a 'check' command"}
        return self.check()

    saved_cache = {}  # type: mypy.build.SavedCache

    def check(self) -> Dict[str, object]:
        try:
            # saved_cache is mutated in place.
            res = mypy.build.build(self.last_sources, self.options, saved_cache=self.saved_cache)
            msgs = res.errors
        except mypy.errors.CompileError as err:
            msgs = err.messages
        if msgs:
            msgs.append("")
            return {'out': "\n".join(msgs), 'err': "", 'status': 1}
        else:
            return {'out': "", 'err': "", 'status': 0}

    def cmd_hang(self) -> Dict[str, object]:
        """Hang for 100 seconds, as a debug hack."""
        time.sleep(100)
        return {}


# Network utilities.

def receive(sock: socket.socket) -> Any:
    """Receive data from a socket until EOF."""
    bdata = bytearray()
    while True:
        more = sock.recv(100000)
        if not more:
            break
        bdata.extend(more)
    if not bdata:
        raise OSError("No data received")
    return json.loads(bdata)


# Run main().

if __name__ == '__main__':
    main()
