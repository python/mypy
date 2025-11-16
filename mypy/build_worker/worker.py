from __future__ import annotations

import argparse
import base64
import gc
import json
import os
import pickle
import platform
import sys
import time

from mypy.build import (
    SCC,
    BuildManager,
    load_graph,
    load_plugins,
    process_stale_scc,
    receive,
    send,
)
from mypy.errors import Errors, CompileError
from mypy.fscache import FileSystemCache
from mypy.ipc import IPCServer
from mypy.main import RECURSION_LIMIT
from mypy.modulefinder import BuildSource, BuildSourceSet, compute_search_paths
from mypy.options import Options
from mypy.util import read_py_file
from mypy.version import __version__

parser = argparse.ArgumentParser(prog="mypy_worker", description="Mypy build worker")
parser.add_argument("--status-file", help="status file to communicate worker details")
parser.add_argument("--options-data", help="serialized mypy options")

CONNECTION_NAME = "build_worker"


def main(argv: list[str]) -> None:
    # Set recursion limit consistent with mypy/main.py
    sys.setrecursionlimit(RECURSION_LIMIT)
    if platform.python_implementation() == "CPython":
        gc.set_threshold(200 * 1000, 30, 30)

    args = parser.parse_args(argv)

    options_dict = pickle.loads(base64.b64decode(args.options_data))
    options_obj = Options()
    options = options_obj.apply_changes(options_dict)

    status_file = args.status_file
    server = IPCServer(CONNECTION_NAME, 10)

    with open(status_file, "w") as f:
        json.dump({"pid": os.getpid(), "connection_name": server.connection_name}, f)
        f.write("\n")

    with server:
        data = receive(server)
        sources = [BuildSource(*st) for st in data["sources"]]

        data_dir = os.path.dirname(os.path.dirname(__file__))
        fscache = FileSystemCache()
        search_paths = compute_search_paths(sources, options, data_dir, None)

        source_set = BuildSourceSet(sources)
        cached_read = fscache.read
        errors = Errors(options, read_source=lambda path: read_py_file(path, cached_read))
        plugin, snapshot = load_plugins(options, errors, sys.stdout, [])

        def flush_errors(filename: str | None, new_messages: list[str], is_serious: bool) -> None:
            pass

        manager = BuildManager(
            data_dir,
            search_paths,
            ignore_prefix=os.getcwd(),
            source_set=source_set,
            reports=None,
            options=options,
            version_id=__version__,
            plugin=plugin,
            plugins_snapshot=snapshot,
            errors=errors,
            error_formatter=None,
            flush_errors=flush_errors,
            fscache=fscache,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        gc.disable()
        graph = load_graph(sources, manager)
        gc.freeze()
        gc.unfreeze()
        gc.enable()

        for id in graph:
            manager.import_map[id] = set(graph[id].dependencies + graph[id].suppressed)
        send(server, {"status": "ok"})

        data = receive(server)
        sccs = [SCC(set(mod_ids), scc_id, deps) for (mod_ids, scc_id, deps) in data["sccs"]]

        manager.scc_by_id = {scc.id: scc for scc in sccs}
        manager.top_order = [scc.id for scc in sccs]

        send(server, {"status": "ok"})

        while True:
            data = receive(server)
            if "final" in data:
                manager.dump_stats()
                break
            scc_id = data["scc_id"]
            scc = manager.scc_by_id[scc_id]
            t0 = time.time()
            try:
                result = process_stale_scc(graph, scc, manager)
            except CompileError as e:
                blocker = {
                    "messages": e.messages,
                    "use_stdout": e.use_stdout,
                    "module_with_blocker": e.module_with_blocker,
                }
                send(server, {"scc_id": scc_id, "blocker": blocker})
            else:
                send(server, {"scc_id": scc_id, "result": result})
            manager.add_stats(total_process_stale_time=time.time() - t0, stale_sccs_processed=1)

    server.cleanup()


def console_entry() -> None:
    main(sys.argv[1:])
