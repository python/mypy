from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Callable
from unittest import TestCase, mock

from librt.internal import ReadBuffer

from mypy.build_worker.worker import read_options_data
from mypy.cache import read_json
from mypy.options import Options


class WorkerSuite(TestCase):
    def _create_transient_open(
        self, failures_before_success: int, payload: bytes
    ) -> tuple[Callable[[str, str], io.BytesIO], list[int]]:
        attempts = [0]

        def fake_open(path: str, mode: str = "rb") -> io.BytesIO:
            attempts[0] += 1
            if attempts[0] <= failures_before_success:
                raise FileNotFoundError("Simulated transient absence")
            return io.BytesIO(payload)

        return fake_open, attempts

    def test_read_options_data_immediate_success(self) -> None:
        """Normal path returns bytes immediately on the first attempt without sleeping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            options_path = os.path.join(tmpdir, "options.data")
            expected_data = b"test_options_data_payload"
            with open(options_path, "wb") as f:
                f.write(expected_data)

            with mock.patch("time.sleep") as mock_sleep:
                data = read_options_data(options_path, timeout=1.0, interval=0.01)
                self.assertEqual(data, expected_data)
                mock_sleep.assert_not_called()

    def test_read_options_data_single_transient_miss(self) -> None:
        """Transient FileNotFoundError recovers on subsequent attempt."""
        expected_data = b"recovered_payload"
        fake_open, attempts = self._create_transient_open(1, expected_data)

        with (
            mock.patch("builtins.open", side_effect=fake_open),
            mock.patch("time.sleep") as mock_sleep,
        ):
            data = read_options_data("dummy_path", timeout=1.0, interval=0.05)
            self.assertEqual(data, expected_data)
            self.assertEqual(attempts[0], 2)
            mock_sleep.assert_called_once_with(0.05)

    def test_read_options_data_multiple_transient_misses(self) -> None:
        """Multiple transient FileNotFoundError misses recover within budget."""
        expected_data = b"recovered_after_multiple"
        fake_open, attempts = self._create_transient_open(3, expected_data)

        with (
            mock.patch("builtins.open", side_effect=fake_open),
            mock.patch("time.sleep") as mock_sleep,
        ):
            data = read_options_data("dummy_path", timeout=2.0, interval=0.02)
            self.assertEqual(data, expected_data)
            self.assertEqual(attempts[0], 4)
            self.assertEqual(mock_sleep.call_count, 3)

    def test_read_options_data_exhaustion(self) -> None:
        """Persistent FileNotFoundError propagates the original error after timeout."""
        current_time = 100.0
        orig_exc = FileNotFoundError("Target file missing")

        def fake_monotonic() -> float:
            return current_time

        def fake_sleep(duration: float) -> None:
            nonlocal current_time
            current_time += duration

        with (
            mock.patch("builtins.open", side_effect=orig_exc),
            mock.patch("time.monotonic", side_effect=fake_monotonic),
            mock.patch("time.sleep", side_effect=fake_sleep) as mock_sleep,
        ):
            with self.assertRaises(FileNotFoundError) as ctx:
                read_options_data("missing_path", timeout=0.1, interval=0.03)
            self.assertIs(ctx.exception, orig_exc)
            # Ensure no sleep was executed after the timeout was exceeded
            self.assertEqual(mock_sleep.call_count, 4)

    def test_read_options_data_zero_timeout(self) -> None:
        """Zero timeout raises on first failure without any sleep."""
        orig_exc = FileNotFoundError("Missing on zero timeout")
        with (
            mock.patch("builtins.open", side_effect=orig_exc),
            mock.patch("time.sleep") as mock_sleep,
        ):
            with self.assertRaises(FileNotFoundError) as ctx:
                read_options_data("missing_path", timeout=0)
            self.assertIs(ctx.exception, orig_exc)
            mock_sleep.assert_not_called()

    def test_read_options_data_permission_error_no_retry(self) -> None:
        """Unrelated OS errors (e.g. PermissionError) propagate immediately without sleeping."""
        with (
            mock.patch("builtins.open", side_effect=PermissionError("Access denied")),
            mock.patch("time.sleep") as mock_sleep,
        ):
            with self.assertRaises(PermissionError):
                read_options_data("restricted_path", timeout=1.0, interval=0.01)
            mock_sleep.assert_not_called()

    def test_read_options_data_corrupted_data_not_masked(self) -> None:
        """Corrupted content is returned as-is and fails parsing, not masked as absence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            options_path = os.path.join(tmpdir, "corrupted.data")
            with open(options_path, "wb") as f:
                f.write(b"not_valid_json_buffer")

            data = read_options_data(options_path, timeout=0.5, interval=0.01)
            self.assertEqual(data, b"not_valid_json_buffer")
            buf = ReadBuffer(data)
            with self.assertRaises(Exception):
                read_json(buf)

    def test_read_options_data_roundtrip_with_options(self) -> None:
        """Verify roundtrip with actual Options.to_bytes() serialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            options_path = os.path.join(tmpdir, "valid.data")
            options = Options()
            options.python_version = (3, 11)
            with open(options_path, "wb") as f:
                f.write(options.to_bytes())

            data = read_options_data(options_path, timeout=0.5, interval=0.01)
            buf = ReadBuffer(data)
            options_dict = read_json(buf)
            recovered = Options().apply_changes(options_dict)
            self.assertEqual(recovered.python_version, (3, 11))
