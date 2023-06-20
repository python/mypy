import shlex
import subprocess
import sys
import textwrap
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mypy.test.config import test_data_prefix


@dataclass
class PytestResult:
    source: str
    source_updated: str
    stdout: str
    stderr: str


def strip_source(s: str) -> str:
    return textwrap.dedent(s).lstrip()


def run_pytest(
    data_suite: str,
    *,
    data_file_prefix: str,
    node_prefix: str,
    extra_args: Iterable[str],
    max_attempts: int,
) -> PytestResult:
    """
    Runs a suite of data test cases through pytest until either tests pass
    or until a maximum number of attempts (needed for incremental tests).
    """
    p_test_data = Path(test_data_prefix)
    p_root = p_test_data.parent.parent
    p = p_test_data / f"{data_file_prefix}-meta-{uuid.uuid4()}.test"
    assert not p.exists()
    data_suite = strip_source(data_suite)
    try:
        p.write_text(data_suite)

        test_nodeid = f"{node_prefix}::{p.name}"
        extra_args = [sys.executable, "-m", "pytest", "-n", "0", "-s", *extra_args, test_nodeid]
        if sys.version_info >= (3, 8):
            cmd = shlex.join(extra_args)
        else:
            cmd = " ".join(extra_args)
        for i in range(max_attempts - 1, -1, -1):
            print(f">> {cmd}")
            proc = subprocess.run(extra_args, capture_output=True, check=False, cwd=p_root)
            if proc.returncode == 0:
                break
            prefix = "NESTED PYTEST STDOUT"
            for line in proc.stdout.decode().splitlines():
                print(f"{prefix}: {line}")
                prefix = " " * len(prefix)
            prefix = "NESTED PYTEST STDERR"
            for line in proc.stderr.decode().splitlines():
                print(f"{prefix}: {line}")
                prefix = " " * len(prefix)
            print(f"Exit code {proc.returncode} ({i} attempts remaining)")

        return PytestResult(
            source=data_suite,
            source_updated=p.read_text(),
            stdout=proc.stdout.decode(),
            stderr=proc.stderr.decode(),
        )
    finally:
        p.unlink()


def run_type_check_suite(
    data_suite: str, *, extra_args: Iterable[str], max_attempts: int
) -> PytestResult:
    return run_pytest(
        data_suite,
        data_file_prefix="check",
        node_prefix="mypy/test/testcheck.py::TypeCheckSuite",
        extra_args=extra_args,
        max_attempts=max_attempts,
    )
