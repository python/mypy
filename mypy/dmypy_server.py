"""Client for mypy daemon mode.

Highly experimental!  Only supports UNIX-like systems.

This manages a daemon process which keeps useful state in memory
to enable fine-grained incremental reprocessing of changes.
"""

import gc
import io
import json
import os
import socket
import sys
import time
import traceback

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import mypy.build
import mypy.errors
import mypy.main
from mypy.server.update import FineGrainedBuildManager
from mypy.dmypy_util import STATUS_FILE, receive
from mypy.gclogger import GcLogger
from mypy.fscache import FileSystemCache
from mypy.fswatcher import FileSystemWatcher, FileData
from mypy.options import Options


def daemonize(func: Callable[[], None], log_file: Optional[str] = None) -> int:
    """Arrange to call func() in a grandchild of the current process.

    Return 0 for success, exit status for failure, negative if
    subprocess killed by signal.
    """
    # See https://stackoverflow.com/questions/473620/how-do-you-create-a-daemon-in-python
    sys.stdout.flush()
    sys.stderr.flush()
    pid = os.fork()
    if pid:
        # Parent process: wait for child in case things go bad there.
        npid, sts = os.waitpid(pid, 0)
        sig = sts & 0xff
        if sig:
            print("Child killed by signal", sig)
            return -sig
        sts = sts >> 8
        if sts:
            print("Child exit status", sts)
        return sts
    # Child process: do a bunch of UNIX stuff and then fork a grandchild.
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
            # Child is done, exit to parent.
            os._exit(0)
        # Grandchild: run the server.
        if log_file:
            sys.stdout = sys.stderr = open(log_file, 'a', buffering=1)
            fd = sys.stdout.fileno()
            os.dup2(fd, 2)
            os.dup2(fd, 1)
        func()
    finally:
        # Make sure we never get back into the caller.
        os._exit(1)


# Server code.

SOCKET_NAME = 'dmypy.sock'  # In current directory.


def process_start_options(flags: List[str]) -> Options:
    import mypy.main
    sources, options = mypy.main.process_options(['-i'] + flags,
                                                 require_targets=False,
                                                 server_options=True)
    if sources:
        sys.exit("dmypy: start/restart does not accept sources")
    if options.report_dirs:
        sys.exit("dmypy: start/restart cannot generate reports")
    if options.junit_xml:
        sys.exit("dmypy: start/restart does not support --junit-xml; "
                 "pass it to check/recheck instead")
    if not options.incremental:
        sys.exit("dmypy: start/restart should not disable incremental mode")
    if options.quick_and_dirty:
        sys.exit("dmypy: start/restart should not specify quick_and_dirty mode")
    if options.use_fine_grained_cache and not options.fine_grained_incremental:
        sys.exit("dmypy: fine-grained cache can only be used in experimental mode")
    # Our file change tracking can't yet handle changes to files that aren't
    # specified in the sources list.
    if options.follow_imports not in ('skip', 'error'):
        sys.exit("dmypy: follow-imports must be 'skip' or 'error'")
    return options


class Server:

    # NOTE: the instance is constructed in the parent process but
    # serve() is called in the grandchild (by daemonize()).

    def __init__(self, options: Options,
                 timeout: Optional[int] = None,
                 alt_lib_path: Optional[str] = None) -> None:
        """Initialize the server with the desired mypy flags."""
        self.options = options
        self.timeout = timeout
        self.alt_lib_path = alt_lib_path
        self.fine_grained_manager = None  # type: Optional[FineGrainedBuildManager]

        if os.path.isfile(STATUS_FILE):
            os.unlink(STATUS_FILE)

        options.incremental = True
        options.fine_grained_incremental = True
        options.show_traceback = True
        if options.use_fine_grained_cache:
            options.cache_fine_grained = True  # set this so that cache options match
        else:
            options.cache_dir = os.devnull
        # Fine-grained incremental doesn't support general partial types
        # (details in https://github.com/python/mypy/issues/4492)
        options.local_partial_types = True

    def serve(self) -> None:
        """Serve requests, synchronously (no thread or fork)."""
        try:
            sock = self.create_listening_socket()
            if self.timeout is not None:
                sock.settimeout(self.timeout)
            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump({'pid': os.getpid(), 'sockname': sock.getsockname()}, f)
                    f.write('\n')  # I like my JSON with trailing newline
                while True:
                    try:
                        conn, addr = sock.accept()
                    except socket.timeout:
                        print("Exiting due to inactivity.")
                        sys.exit(0)
                    try:
                        data = receive(conn)
                    except OSError as err:
                        conn.close()  # Maybe the client hung up
                        continue
                    resp = {}  # type: Dict[str, Any]
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
            finally:
                os.unlink(STATUS_FILE)
        finally:
            os.unlink(self.sockname)
            exc_info = sys.exc_info()
            if exc_info[0] and exc_info[0] is not SystemExit:
                traceback.print_exception(*exc_info)  # type: ignore

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
        res = {}  # type: Dict[str, object]
        res.update(get_meminfo())
        return res

    def cmd_stop(self) -> Dict[str, object]:
        """Stop daemon."""
        return {}

    last_sources = None  # type: List[mypy.build.BuildSource]

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
        return self.check(self.last_sources)

    def cmd_recheck(self) -> Dict[str, object]:
        """Check the same list of files we checked most recently."""
        if not self.last_sources:
            return {'error': "Command 'recheck' is only valid after a 'check' command"}
        return self.check(self.last_sources)

    def check(self, sources: List[mypy.build.BuildSource]) -> Dict[str, Any]:
        """Check using fine-grained incremental mode."""
        if not self.fine_grained_manager:
            return self.initialize_fine_grained(sources)
        else:
            return self.fine_grained_increment(sources)

    def initialize_fine_grained(self, sources: List[mypy.build.BuildSource]) -> Dict[str, Any]:
        # The file system cache we create gets passed off to
        # BuildManager, and thence to FineGrainedBuildManager, which
        # assumes responsibility for clearing it after updates.
        fscache = FileSystemCache(self.options.python_version)
        self.fswatcher = FileSystemWatcher(fscache)
        self.update_sources(sources)
        try:
            result = mypy.build.build(sources=sources,
                                      options=self.options,
                                      fscache=fscache,
                                      alt_lib_path=self.alt_lib_path)
        except mypy.errors.CompileError as e:
            output = ''.join(s + '\n' for s in e.messages)
            if e.use_stdout:
                out, err = output, ''
            else:
                out, err = '', output
            return {'out': out, 'err': err, 'status': 2}
        messages = result.errors
        self.fine_grained_manager = FineGrainedBuildManager(result)
        self.previous_sources = sources

        # If we are using the fine-grained cache, build hasn't actually done
        # the typechecking on the updated files yet.
        # Run a fine-grained update starting from the cached data
        if result.used_cache:
            # Pull times and hashes out of the saved_cache and stick them into
            # the fswatcher, so we pick up the changes.
            for state in self.fine_grained_manager.graph.values():
                meta = state.meta
                if meta is None: continue
                assert state.path is not None
                self.fswatcher.set_file_data(
                    state.path,
                    FileData(st_mtime=float(meta.mtime), st_size=meta.size, md5=meta.hash))

            changed, removed = self.find_changed(sources)

            # Find anything that has had its dependency list change
            for state in self.fine_grained_manager.graph.values():
                if not state.is_fresh():
                    assert state.path is not None
                    changed.append((state.id, state.path))

            # Run an update
            messages = self.fine_grained_manager.update(changed, removed)
        else:
            # Stores the initial state of sources as a side effect.
            self.fswatcher.find_changed()

        fscache.flush()
        status = 1 if messages else 0
        return {'out': ''.join(s + '\n' for s in messages), 'err': '', 'status': status}

    def fine_grained_increment(self, sources: List[mypy.build.BuildSource]) -> Dict[str, Any]:
        assert self.fine_grained_manager is not None

        t0 = time.time()
        self.update_sources(sources)
        changed, removed = self.find_changed(sources)
        t1 = time.time()
        messages = self.fine_grained_manager.update(changed, removed)
        t2 = time.time()
        self.fine_grained_manager.manager.log(
            "fine-grained increment: find_changed: {:.3f}s, update: {:.3f}s".format(
                t1 - t0, t2 - t1))
        status = 1 if messages else 0
        self.previous_sources = sources
        return {'out': ''.join(s + '\n' for s in messages), 'err': '', 'status': status}

    def update_sources(self, sources: List[mypy.build.BuildSource]) -> None:
        paths = [source.path for source in sources if source.path is not None]
        self.fswatcher.add_watched_paths(paths)

    def find_changed(self, sources: List[mypy.build.BuildSource]) -> Tuple[List[Tuple[str, str]],
                                                                           List[Tuple[str, str]]]:
        changed_paths = self.fswatcher.find_changed()
        changed = [(source.module, source.path)
                   for source in sources
                   if source.path in changed_paths]
        modules = {source.module for source in sources}
        omitted = [source for source in self.previous_sources if source.module not in modules]
        removed = []
        for source in omitted:
            path = source.path
            assert path
            removed.append((source.module, path))
        return changed, removed

    def cmd_hang(self) -> Dict[str, object]:
        """Hang for 100 seconds, as a debug hack."""
        time.sleep(100)
        return {}


# Misc utilities.


MiB = 2**20


def get_meminfo() -> Dict[str, Any]:
    # See https://stackoverflow.com/questions/938733/total-memory-used-by-python-process
    import resource  # Since it doesn't exist on Windows.
    res = {}  # type: Dict[str, Any]
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == 'darwin':
        factor = 1
    else:
        factor = 1024  # Linux
    res['memory_maxrss_mib'] = rusage.ru_maxrss * factor / MiB
    # If we can import psutil, use it for some extra data
    try:
        import psutil  # type: ignore  # It's not in typeshed yet
    except ImportError:
        if sys.platform != 'win32':
            res['memory_psutil_missing'] = (
                'psutil not found, run pip install mypy[dmypy] '
                'to install the needed components for dmypy'
            )
    else:
        process = psutil.Process(os.getpid())
        meminfo = process.memory_info()
        res['memory_rss_mib'] = meminfo.rss / MiB
        res['memory_vms_mib'] = meminfo.vms / MiB
    return res
