#! /usr/bin/env python

"""Compare performance of mypyc-compiled mypy between one or more commits/branches.

Simple usage:

  python misc/perf_compare.py master my-branch ...

What this does:

 * Create a temp clone of the mypy repo for each target commit to measure
 * Checkout a target commit in each of the clones
 * Compile mypyc in each of the clones *in parallel*
 * Create another temp clone of the first provided revision (or, with -r, a foreign repo) as the code to check
 * Self check with each of the compiled mypys N times
 * Report the average runtimes and relative performance
 * Remove the temp clones
"""

from __future__ import annotations

import argparse
import glob
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def heading(s: str) -> None:
    print()
    print(f"=== {s} ===")
    print()


def build_mypy(
    target_dir: str,
    multi_file: bool,
    *,
    cflags: str | None = None,
    log_trace: bool = False,
    opt_level: str = "2",
) -> None:
    env = os.environ.copy()
    env["CC"] = "clang"
    env["MYPYC_OPT_LEVEL"] = opt_level
    env["PYTHONHASHSEED"] = "1"
    if multi_file:
        env["MYPYC_MULTI_FILE"] = "1"
    if log_trace:
        env["MYPYC_LOG_TRACE"] = "1"
    if cflags is not None:
        env["CFLAGS"] = cflags
    cmd = [sys.executable, "setup.py", "--use-mypyc", "build_ext", "--inplace"]
    subprocess.run(cmd, env=env, check=True, cwd=target_dir)


def clone(target_dir: str, commit: str | None, repo_source: str | None = None) -> None:
    source_name = repo_source or "mypy"
    heading(f"Cloning {source_name} to {target_dir}")
    if repo_source is None:
        repo_source = os.getcwd()
    if os.path.isdir(target_dir):
        print(f"{target_dir} exists: deleting")
        shutil.rmtree(target_dir)
    subprocess.run(["git", "clone", repo_source, target_dir], check=True)
    if commit:
        subprocess.run(["git", "checkout", commit], check=True, cwd=target_dir)


def edit_python_file(fnam: str) -> None:
    with open(fnam) as f:
        data = f.read()
    data += "\n#"
    with open(fnam, "w") as f:
        f.write(data)


def run_benchmark(
    compiled_dir: str, check_dir: str, *, incremental: bool, code: str | None, foreign: bool | None
) -> float:
    cache_dir = os.path.join(compiled_dir, ".mypy_cache")
    if os.path.isdir(cache_dir) and not incremental:
        shutil.rmtree(cache_dir)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(compiled_dir)
    env["PYTHONHASHSEED"] = "1"
    abschk = os.path.abspath(check_dir)
    cmd = [sys.executable, "-m", "mypy"]
    if code:
        cmd += ["-c", code]
    elif foreign:
        pass
    else:
        cmd += ["--config-file", os.path.join(abschk, "mypy_self_check.ini")]
        cmd += glob.glob(os.path.join(abschk, "mypy/*.py"))
        cmd += glob.glob(os.path.join(abschk, "mypy/*/*.py"))
        if incremental:
            # Update a few files to force non-trivial incremental run
            edit_python_file(os.path.join(abschk, "mypy/__main__.py"))
            edit_python_file(os.path.join(abschk, "mypy/test/testcheck.py"))
    t0 = time.time()
    # Ignore errors, since some commits being measured may generate additional errors.
    if foreign:
        subprocess.run(cmd, cwd=check_dir, env=env)
    else:
        subprocess.run(cmd, cwd=compiled_dir, env=env)
    return time.time() - t0


def main() -> None:
    whole_program_time_0 = time.time()
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
        epilog="Remember: you usually want the first argument to this command to be 'master'.",
    )
    parser.add_argument(
        "--incremental",
        default=False,
        action="store_true",
        help="measure incremental run (fully cached)",
    )
    parser.add_argument(
        "--multi-file",
        default=False,
        action="store_true",
        help="compile each mypy module to a separate C file (reduces RAM use)",
    )
    parser.add_argument(
        "--dont-setup",
        default=False,
        action="store_true",
        help="don't make the clones or compile mypy, just run the performance measurement benchmark "
        + "(this will fail unless the clones already exist, such as from a previous run that was canceled before it deleted them)",
    )
    parser.add_argument(
        "--num-runs",
        metavar="N",
        default=15,
        type=int,
        help="set number of measurements to perform (default=15)",
    )
    parser.add_argument(
        "-j",
        metavar="N",
        default=4,
        type=int,
        help="set maximum number of parallel builds (default=4) -- high numbers require a lot of RAM!",
    )
    parser.add_argument(
        "-r",
        metavar="FOREIGN_REPOSITORY",
        default=None,
        type=str,
        help="measure time to typecheck the project at FOREIGN_REPOSITORY instead of mypy self-check; "
        + "the provided value must be the URL or path of a git repo "
        + "(note that this script will take no special steps to *install* the foreign repo, so you will probably get a lot of missing import errors)",
    )
    parser.add_argument(
        "-c",
        metavar="CODE",
        default=None,
        type=str,
        help="measure time to type check Python code fragment instead of mypy self-check",
    )
    parser.add_argument(
        "commit",
        nargs="+",
        help="git revision(s), e.g. branch name or commit id, to measure the performance of",
    )
    args = parser.parse_args()
    incremental: bool = args.incremental
    dont_setup: bool = args.dont_setup
    multi_file: bool = args.multi_file
    commits = args.commit
    num_runs: int = args.num_runs + 1
    max_workers: int = args.j
    code: str | None = args.c
    foreign_repo: str | None = args.r

    if not (os.path.isdir(".git") and os.path.isdir("mypyc")):
        sys.exit("error: You must run this script from the mypy repo root")

    target_dirs = []
    for i, commit in enumerate(commits):
        target_dir = f"mypy.{i}.tmpdir"
        target_dirs.append(target_dir)
        if not dont_setup:
            clone(target_dir, commit)

    if foreign_repo:
        check_dir = "mypy.foreign.tmpdir"
        if not dont_setup:
            clone(check_dir, None, foreign_repo)
    else:
        check_dir = "mypy.self.tmpdir"
        if not dont_setup:
            clone(check_dir, commits[0])

    if not dont_setup:
        heading("Compiling mypy")
        print("(This will take a while...)")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(build_mypy, target_dir, multi_file) for target_dir in target_dirs
            ]
            for future in as_completed(futures):
                future.result()

        print(f"Finished compiling mypy ({len(commits)} builds)")

    heading("Performing measurements")

    results: dict[str, list[float]] = {}
    for n in range(num_runs):
        if n == 0:
            print("Warmup...")
        else:
            print(f"Run {n}/{num_runs - 1}...")
        items = list(enumerate(commits))
        random.shuffle(items)
        for i, commit in items:
            tt = run_benchmark(
                target_dirs[i],
                check_dir,
                incremental=incremental,
                code=code,
                foreign=bool(foreign_repo),
            )
            # Don't record the first warm-up run
            if n > 0:
                print(f"{commit}: t={tt:.3f}s")
                results.setdefault(commit, []).append(tt)

    print()
    heading("Results")
    first = -1.0
    for commit in commits:
        tt = statistics.mean(results[commit])
        # pstdev (instead of stdev) is used here primarily to accommodate the case where num_runs=1
        s = statistics.pstdev(results[commit]) if len(results[commit]) > 1 else 0
        if first < 0:
            delta = "0.0%"
            first = tt
        else:
            d = (tt / first) - 1
            delta = f"{d:+.1%}"
        print(f"{commit:<25} {tt:.3f}s ({delta}) | stdev {s:.3f}s ")

    t = int(time.time() - whole_program_time_0)
    total_time_taken_formatted = ", ".join(
        f"{v} {n if v==1 else n+'s'}"
        for v, n in ((t // 3600, "hour"), (t // 60 % 60, "minute"), (t % 60, "second"))
        if v
    )
    print(
        "Total time taken by the whole benchmarking program (including any setup):",
        total_time_taken_formatted,
    )

    shutil.rmtree(check_dir)
    for target_dir in target_dirs:
        shutil.rmtree(target_dir)


if __name__ == "__main__":
    main()
