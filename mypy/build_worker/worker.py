"""
Mypy parallel build worker.

The protocol of communication with the coordinator is as following:
* Read (pickled) build options from command line.
* Populate status file with pid and socket address.
* Receive build sources from coordinator.
* Load graph using the sources, and send ack to coordinator.
* Receive SCC structure from coordinator, and ack it.
* Receive an SCC id from coordinator, process it, and send back the results.
* When prompted by coordinator (with a scc_id=None message), cleanup and shutdown.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import pickle
import platform
import sys
import time
from typing import NamedTuple

from librt.base64 import b64decode

from mypy import util
from mypy.build import (
    AckMessage,
    BuildManager,
    GraphMessage,
    SccRequestMessage,
    SccResponseMessage,
    SccsDataMessage,
    SourcesDataMessage,
    load_graph,
    load_plugins,
    process_stale_scc,
)
from mypy.defaults import RECURSION_LIMIT, WORKER_CONNECTION_TIMEOUT
from mypy.errors import CompileError, Errors, report_internal_error
from mypy.fscache import FileSystemCache
from mypy.ipc import IPCException, IPCServer, receive, send
from mypy.modulefinder import BuildSource, BuildSourceSet, compute_search_paths
from mypy.options import Options
from mypy.util import read_py_file
from mypy.version import __version__

parser = argparse.ArgumentParser(prog="mypy_worker", description="Mypy build worker")
parser.add_argument("--status-file", help="status file to communicate worker details")
parser.add_argument("--options-data", help="serialized mypy options")

CONNECTION_NAME = "build_worker"


class ServerContext(NamedTuple):
    options: Options
    disable_error_code: list[str]
    enable_error_code: list[str]
    errors: Errors
    fscache: FileSystemCache


def main(argv: list[str]) -> None:
    # Set recursion limit and GC thresholds consistent with mypy/main.py
    sys.setrecursionlimit(RECURSION_LIMIT)
    if platform.python_implementation() == "CPython":
        gc.set_threshold(200 * 1000, 30, 30)

    args = parser.parse_args(argv)

    # This mimics how daemon receives the options. Note we need to postpone
    # processing error codes after plugins are loaded, because plugins can add
    # custom error codes.
    options_dict = pickle.loads(b64decode(args.options_data))
    options_obj = Options()
    disable_error_code = options_dict.pop("disable_error_code", [])
    enable_error_code = options_dict.pop("enable_error_code", [])
    options = options_obj.apply_changes(options_dict)

    status_file = args.status_file
    server = IPCServer(CONNECTION_NAME, WORKER_CONNECTION_TIMEOUT)

    try:
        with open(status_file, "w") as f:
            json.dump({"pid": os.getpid(), "connection_name": server.connection_name}, f)
            f.write("\n")
    except Exception as exc:
        print(f"Error writing status file {status_file}:", exc)
        raise

    fscache = FileSystemCache()
    cached_read = fscache.read
    errors = Errors(options, read_source=lambda path: read_py_file(path, cached_read))

    ctx = ServerContext(options, disable_error_code, enable_error_code, errors, fscache)
    try:
        with server:
            serve(server, ctx)
    except (OSError, IPCException) as exc:
        if options.verbosity >= 1:
            print("Error communicating with coordinator:", exc)
    except Exception as exc:
        report_internal_error(exc, errors.file, 0, errors, options)
    finally:
        server.cleanup()

    if options.fast_exit:
        # Exit fast if allowed, since coordinator is waiting on us.
        util.hard_exit(0)


def serve(server: IPCServer, ctx: ServerContext) -> None:
    """Main server loop of the worker.

    Receive initial state from the coordinator, then process each
    SCC checking request and reply to client (coordinator). See module
    docstring for more details on the protocol.
    """
    sources = SourcesDataMessage.read(receive(server)).sources
    manager = setup_worker_manager(sources, ctx)
    if manager is None:
        return

    # Mirror the GC freeze hack in the coordinator.
    if platform.python_implementation() == "CPython":
        gc.disable()
    try:
        graph = load_graph(sources, manager)
    except CompileError:
        # CompileError during loading will be reported by the coordinator.
        return
    if platform.python_implementation() == "CPython":
        gc.freeze()
        gc.unfreeze()
        gc.enable()
    for id in graph:
        manager.import_map[id] = graph[id].dependencies_set
    # Ignore errors during local graph loading to check that receiving
    # early errors from coordinator works correctly.
    manager.errors.reset()

    # Notify worker we are done loading graph.
    send(server, AckMessage())

    # Compare worker graph and coordinator, with parallel parser we will only use the latter.
    graph_data = GraphMessage.read(receive(server), manager)
    assert set(manager.missing_modules) == graph_data.missing_modules
    coordinator_graph = graph_data.graph
    assert coordinator_graph.keys() == graph.keys()
    for id in graph:
        assert graph[id].dependencies_set == coordinator_graph[id].dependencies_set
        assert graph[id].suppressed_set == coordinator_graph[id].suppressed_set
    send(server, AckMessage())

    sccs = SccsDataMessage.read(receive(server)).sccs
    manager.scc_by_id = {scc.id: scc for scc in sccs}
    manager.top_order = [scc.id for scc in sccs]

    # Notify coordinator we are ready to process SCCs.
    send(server, AckMessage())
    while True:
        scc_message = SccRequestMessage.read(receive(server))
        scc_id = scc_message.scc_id
        if scc_id is None:
            manager.dump_stats()
            break
        scc = manager.scc_by_id[scc_id]
        t0 = time.time()
        try:
            for id in scc.mod_ids:
                state = graph[id]
                # Extra if below is needed only because we are using local graph.
                # TODO: clone options when switching to coordinator graph.
                if state.tree is None:
                    # Parse early to get errors related data, such as ignored
                    # and skipped lines before replaying the errors.
                    state.parse_file()
                else:
                    state.setup_errors()
                if id in scc_message.import_errors:
                    manager.errors.set_file(state.xpath, id, state.options)
                    for err_info in scc_message.import_errors[id]:
                        manager.errors.add_error_info(err_info)
            result = process_stale_scc(graph, scc, manager, from_cache=graph_data.from_cache)
            # We must commit after each SCC, otherwise we break --sqlite-cache.
            manager.metastore.commit()
        except CompileError as blocker:
            send(server, SccResponseMessage(scc_id=scc_id, blocker=blocker))
        else:
            send(server, SccResponseMessage(scc_id=scc_id, result=result))
        manager.add_stats(total_process_stale_time=time.time() - t0, stale_sccs_processed=1)


def setup_worker_manager(sources: list[BuildSource], ctx: ServerContext) -> BuildManager | None:
    data_dir = os.path.dirname(os.path.dirname(__file__))
    # This is used for testing only now.
    alt_lib_path = os.environ.get("MYPY_ALT_LIB_PATH")
    search_paths = compute_search_paths(sources, ctx.options, data_dir, alt_lib_path)

    source_set = BuildSourceSet(sources)
    try:
        plugin, snapshot = load_plugins(ctx.options, ctx.errors, sys.stdout, [])
    except CompileError:
        # CompileError while importing plugins will be reported by the coordinator.
        return None

    # Process the rest of the options when plugins are loaded.
    options = ctx.options
    options.disable_error_code = ctx.disable_error_code
    options.enable_error_code = ctx.enable_error_code
    options.process_error_codes(error_callback=lambda msg: None)

    def flush_errors(filename: str | None, new_messages: list[str], is_serious: bool) -> None:
        # We never flush errors in the worker, we send them back to coordinator.
        pass

    return BuildManager(
        data_dir,
        search_paths,
        ignore_prefix=os.getcwd(),
        source_set=source_set,
        reports=None,
        options=options,
        version_id=__version__,
        plugin=plugin,
        plugins_snapshot=snapshot,
        errors=ctx.errors,
        error_formatter=None,
        flush_errors=flush_errors,
        fscache=ctx.fscache,
        stdout=sys.stdout,
        stderr=sys.stderr,
        parallel_worker=True,
    )


def console_entry() -> None:
    main(sys.argv[1:])
