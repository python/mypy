"""Regression test for https://github.com/python/mypy/issues/21974.

A parallel build worker subprocess that never manages to connect (e.g.
because concurrent mypy invocations sharing a host starve it of CPU while it
is starting up) must be confirmed dead before the coordinator deletes the
shared ``.worker_options.<id>.data`` file, otherwise the worker can crash
with ``FileNotFoundError`` while it is still trying to read that file.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from unittest import TestCase, mock

from mypy import build
from mypy.modulefinder import BuildSource
from mypy.options import Options


class WorkerCleanupSuite(TestCase):
    def test_cleanup_waits_for_unconnected_worker_before_removing_options_file(self) -> None:
        real_popen = subprocess.Popen
        real_unlink = os.unlink

        created_workers: list[build.WorkerClient] = []
        options_data_path: dict[str, str] = {}
        observed: dict[str, int | None] = {}

        class TrackingWorkerClient(build.WorkerClient):
            def __init__(
                self, status_file: str, options_data: str, env: Mapping[str, str]
            ) -> None:
                options_data_path["path"] = options_data
                super().__init__(status_file, options_data, env)
                created_workers.append(self)

        def fake_popen(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
            # Simulate a worker subprocess that is too starved of CPU (by other
            # concurrent mypy invocations) to write its status file before the
            # coordinator stops waiting for it.
            return real_popen([sys.executable, "-c", "import time; time.sleep(5)"])

        def tracking_unlink(path: str) -> None:
            if path == options_data_path.get("path") and created_workers:
                observed["poll_at_unlink"] = created_workers[0].proc.poll()
            real_unlink(path)

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                options = Options()
                options.cache_dir = os.path.join(tmp_dir, ".mypy_cache")
                options.num_workers = 1
                options.incremental = True

                with (
                    mock.patch.object(build, "WorkerClient", TrackingWorkerClient),
                    mock.patch("mypy.build.subprocess.Popen", side_effect=fake_popen),
                    mock.patch.object(build, "WORKER_START_TIMEOUT", 0.05),
                    mock.patch.object(build, "WORKER_START_INTERVAL", 0.01),
                    mock.patch("mypy.build.os.unlink", side_effect=tracking_unlink),
                ):
                    with self.assertRaises(OSError):
                        build.build(
                            sources=[BuildSource("main", None, "x = 1\n")], options=options
                        )
        finally:
            for wc in created_workers:
                if wc.proc.poll() is None:
                    wc.proc.kill()
                    wc.proc.wait()

        assert "poll_at_unlink" in observed, "options_data file was never removed"
        assert observed["poll_at_unlink"] is not None, (
            "options_data file was deleted while an unconnected worker process "
            "was still running -- it could still be reading the file"
        )
