"""Compile mypy using mypyc with trace logging enabled, and collect a trace.

The trace log can be used to analyze low-level performance bottlenecks.

By default does a self check as the workload.

This works on all supported platforms, unlike some of our other performance tools.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time

from perf_compare import build_mypy, clone

# Generated files, including binaries, go under this directory to avoid overwriting user state.
TARGET_DIR = "mypy.log_trace.tmpdir"


def perform_type_check(target_dir: str, code: str | None) -> None:
    cache_dir = os.path.join(target_dir, ".mypy_cache")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    args = []
    if code is None:
        args.extend(["--config-file", "mypy_self_check.ini"])
        for pat in "mypy/*.py", "mypy/*/*.py", "mypyc/*.py", "mypyc/test/*.py":
            args.extend(glob.glob(pat))
    else:
        args.extend(["-c", code])
    check_cmd = ["python", "-m", "mypy"] + args
    t0 = time.time()
    subprocess.run(check_cmd, cwd=target_dir, check=True)
    elapsed = time.time() - t0
    print(f"{elapsed:.2f}s elapsed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile mypy and collect a trace log while type checking (by default, self check)."
    )
    parser.add_argument(
        "--multi-file",
        action="store_true",
        help="compile mypy into one C file per module (to reduce RAM use during compilation)",
    )
    parser.add_argument(
        "--skip-compile", action="store_true", help="use compiled mypy from previous run"
    )
    parser.add_argument(
        "-c",
        metavar="CODE",
        default=None,
        type=str,
        help="type check Python code fragment instead of mypy self-check",
    )
    args = parser.parse_args()
    multi_file: bool = args.multi_file
    skip_compile: bool = args.skip_compile
    code: str | None = args.c

    target_dir = TARGET_DIR

    if not skip_compile:
        clone(target_dir, "HEAD")

        print(f"Building mypy in {target_dir} with trace logging enabled...")
        build_mypy(target_dir, multi_file, log_trace=True, opt_level="0")
    elif not os.path.isdir(target_dir):
        sys.exit("error: Can't find compile mypy from previous run -- can't use --skip-compile")

    perform_type_check(target_dir, code)

    trace_fnam = os.path.join(target_dir, "mypyc_trace.txt")
    print(f"Generated event trace log in {trace_fnam}")


if __name__ == "__main__":
    main()
