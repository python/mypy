"""Tests for the parallel build worker startup and cleanup paths."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from unittest import TestCase, mock, skipUnless

from mypy import build
from mypy.modulefinder import BuildSource
from mypy.options import Options


class FakePopen:
    """A stand-in for ``subprocess.Popen`` that never manages to start up.

    The process stays alive until it is terminated, and never writes a status
    file, so the coordinator always gives up on it (this is exactly the situation
    in https://github.com/python/mypy/issues/21974, where concurrent invocations
    starve the workers of CPU while they are starting up).
    """

    def __init__(self, command: list[str], **kwargs: object) -> None:
        self.command = command
        self.pid = 12345
        self.alive = True
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        if not self.alive:
            return 0
        raise subprocess.TimeoutExpired(cmd=self.command, timeout=timeout or 0.0)

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def kill(self) -> None:
        self.killed = True
        self.alive = False

    def poll(self) -> int | None:
        return 0 if not self.alive else None


class WorkerCleanupSuite(TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self._status_file = os.path.join(self._tmp_dir.name, ".mypy_worker.abc.0.json")

    def _build_with_never_starting_worker(self) -> tuple[FakePopen, list[tuple[str, int | None]]]:
        """Run a parallel build whose worker never comes up.

        Returns the fake worker process together with the sequence of paths that
        were unlinked, each paired with ``proc.poll()`` at that moment.
        """
        proc = FakePopen([sys.executable])
        unlinked: list[tuple[str, int | None]] = []
        real_unlink = os.unlink

        options_data_path: list[str] = []

        class TrackingWorkerClient(build.WorkerClient):
            def __init__(
                self, status_file: str, options_data: str, env: Mapping[str, str]
            ) -> None:
                options_data_path.append(options_data)
                super().__init__(status_file, options_data, env)

        def tracking_unlink(path: str) -> None:
            unlinked.append((path, proc.poll()))
            real_unlink(path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            options = Options()
            options.cache_dir = os.path.join(tmp_dir, ".mypy_cache")
            options.num_workers = 1
            options.incremental = True
            options.use_builtins_fixtures = True

            with (
                mock.patch.object(build, "WorkerClient", TrackingWorkerClient),
                mock.patch("mypy.build.subprocess.Popen", side_effect=lambda *a, **kw: proc),
                mock.patch.object(build, "WORKER_START_TIMEOUT", 0.02),
                mock.patch.object(build, "WORKER_START_INTERVAL", 0.005),
                mock.patch.object(build, "WORKER_SHUTDOWN_TIMEOUT", 0.02),
                mock.patch("mypy.build.os.unlink", side_effect=tracking_unlink),
            ):
                with self.assertRaises(OSError):
                    build.build(
                        sources=[BuildSource(os.path.join(tmp_dir, "main.py"), "main", "x = 1\n")],
                        options=options,
                    )

        return proc, unlinked

    def test_worker_is_reaped_before_options_file_is_deleted(self) -> None:
        """The serialized options file must outlive the worker subprocess.

        A worker that is still starting up reads the options file after the
        coordinator has given up on it; deleting it first makes the worker crash
        with a confusing ``FileNotFoundError``.
        """
        proc, unlinked = self._build_with_never_starting_worker()

        options_unlinks = [poll for path, poll in unlinked if ".worker_options." in path]
        self.assertEqual(len(options_unlinks), 1)
        # The process must be dead by the time its options file goes away.
        self.assertIsNotNone(options_unlinks[0])
        self.assertTrue(proc.terminated)

    def _make_client(self, proc: FakePopen, connected: bool) -> build.WorkerClient:
        """Build a ``WorkerClient`` whose subprocess is ``proc``.

        We go through the real constructor (rather than ``__new__``) so the tests also
        work against the mypyc-compiled interpreter, which does not let ``__init__``
        be skipped.
        """
        status_file = self._status_file
        with mock.patch("mypy.build.subprocess.Popen", side_effect=lambda *a, **kw: proc):
            client = build.WorkerClient(status_file, os.devnull, os.environ.copy())
        client.connected = connected
        client.proc = proc  # type: ignore[assignment]
        return client

    def test_close_removes_leftover_status_file(self) -> None:
        """A stale status file from a worker that never started is cleaned up."""
        proc = FakePopen([sys.executable])
        client = self._make_client(proc, connected=False)

        with open(client.status_file, "w") as f:
            f.write("{}")

        client.close()

        self.assertFalse(os.path.exists(client.status_file))

    def test_close_terminates_unconnected_worker_and_reaps_it(self) -> None:
        """``close()`` must not return while an unconnected worker is still running."""
        proc = FakePopen([sys.executable])
        client = self._make_client(proc, connected=False)

        client.close()

        self.assertTrue(proc.terminated)
        self.assertFalse(proc.alive)

    @skipUnless(sys.platform != "win32", "SIGTERM behaviour is POSIX-specific")
    def test_close_kills_worker_that_ignores_termination(self) -> None:
        class StubbornPopen(FakePopen):
            def terminate(self) -> None:
                # Ignore SIGTERM, like a worker stuck in a C extension.
                self.terminated = True

        proc = StubbornPopen([sys.executable])
        client = self._make_client(proc, connected=False)

        client.close()

        self.assertTrue(proc.terminated)
        self.assertTrue(proc.killed)
        self.assertFalse(proc.alive)
