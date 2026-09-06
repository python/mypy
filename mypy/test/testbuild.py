from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from mypy import build


class _StuckProcess:
    pid = 1

    def __init__(self) -> None:
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired(["mypy-worker"], timeout or 0.0)
        return 0

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class WorkerTest(unittest.TestCase):
    def test_close_terminates_worker_after_shutdown_timeout(self) -> None:
        process = _StuckProcess()
        with mock.patch.object(subprocess, "Popen", return_value=process):
            worker = build.WorkerClient("worker-status.json", "options", {})
            worker.close()

        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)
        self.assertEqual(process.wait_calls, 2)
