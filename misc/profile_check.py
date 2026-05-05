"""Compile mypy using mypyc and profile type checking using perf.

By default does a self check.

Notes:
 - Only Linux is supported for now (TODO: add support for other profilers)
 - The profile is collected at C level
   - It includes C functions compiled by mypyc and CPython runtime functions
 - The names of mypy functions are mangled to C names, but usually it's clear what they mean
   - Generally CPyDef_ prefix for native functions and CPyPy_ prefix for wrapper functions
 - It's important to compile CPython using special flags (see below) to get good results
 - Generally use the latest Python feature release (or the most recent beta if supported by mypyc)
 - The tool prints a command that can be used to analyze the profile afterwards

You may need to adjust kernel parameters temporarily, e.g. this (note that this has security
implications):

  sudo sysctl kernel.perf_event_paranoid=-1

This is the recommended way to configure CPython for profiling:

  ./configure \
      --enable-optimizations \
      --with-lto \
      CFLAGS="-O2 -g -fno-omit-frame-pointer"
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

# Use these C compiler flags when compiling mypy (important). Note that it's strongly recommended
# to also compile CPython using similar flags, but we don't enforce it in this script.
CFLAGS = "-O2 -fno-omit-frame-pointer -g"

# Generated files, including binaries, go under this directory to avoid overwriting user state.
TARGET_DIR = "mypy.profile.tmpdir"


def _profile_type_check(target_dir: str, code: str | None) -> None:
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
    cmdline = ["perf", "record", "-g"] + check_cmd
    t0 = time.time()
    subprocess.run(cmdline, cwd=target_dir, check=True)
    elapsed = time.time() - t0
    print(f"{elapsed:.2f}s elapsed")


def profile_type_check(target_dir: str, code: str | None) -> None:
    try:
        _profile_type_check(target_dir, code)
    except subprocess.CalledProcessError:
        print("\nProfiling failed! You may missing some permissions.")
        print("\nThis may help (note that it has security implications):")
        print("  sudo sysctl kernel.perf_event_paranoid=-1")
        sys.exit(1)


def check_requirements() -> None:
    if sys.platform != "linux":
        # TODO: How to make this work on other platforms?
        sys.exit("error: Only Linux is supported")
    else:  # fun fact/todo: we have to use else here, because of https://github.com/python/mypy/issues/10773
        try:
            subprocess.run(["perf", "-h"], capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("error: The 'perf' profiler is not installed")
            sys.exit(1)

        try:
            subprocess.run(["clang", "--version"], capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("error: The clang compiler is not installed")
            sys.exit(1)

        if not os.path.isfile("mypy_self_check.ini"):
            print("error: Run this in the mypy repository root")
            sys.exit(1)


def main() -> None:
    check_requirements()

    parser = argparse.ArgumentParser(
        description="Compile mypy and profile type checking using 'perf' (by default, self check)."
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
        help="profile type checking Python code fragment instead of mypy self-check",
    )
    args = parser.parse_args()
    multi_file: bool = args.multi_file
    skip_compile: bool = args.skip_compile
    code: str | None = args.c

    target_dir = TARGET_DIR

    if not skip_compile:
        clone(target_dir, "HEAD")

        print(f"Building mypy in {target_dir}...")
        build_mypy(target_dir, multi_file, cflags=CFLAGS)
    elif not os.path.isdir(target_dir):
        sys.exit("error: Can't find compile mypy from previous run -- can't use --skip-compile")

    profile_type_check(target_dir, code)

    print()
    print('NOTE: Compile CPython using CFLAGS="-O2 -g -fno-omit-frame-pointer" for good results')
    print()
    print("CPU profile collected. You can now analyze the profile:")
    print(f"  perf report -i {target_dir}/perf.data ")


if __name__ == "__main__":
    main()
