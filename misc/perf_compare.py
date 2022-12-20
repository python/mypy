"""Compare performance of mypyc-compiled mypy between two or more commits/branches.

Simple usage:

  python misc/perf_compare.py my-branch master

What this does:

 * Create a temp clone of the mypy repo for each target commit
 * Checkout a target commit in each of the clones
 * Compile mypyc in each of the clones in parallel
 * Create another temp clone of the mypy repo as the code to self check
 * Self check with each of the compiled mypys N times
 * Report the average runtimes and relative performance
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time


def build_mypy(target_dir: str) -> None:
    env = os.environ.copy()
    env["CC"] = "clang"
    env["MYPYC_OPT_LEVEL"] = "2"
    cmd = ["python3", "setup.py", "--use-mypyc", "build_ext", "--inplace"]
    subprocess.run(cmd, env=env, check=True, cwd=target_dir)


def clone(target_dir: str, commit: str | None) -> None:
    repo_dir = os.getcwd()
    if os.path.isdir(target_dir):
        print(f"{target_dir} exists: deleting")
        input()
        shutil.rmtree(target_dir)
    print(f"cloning mypy to {target_dir}")
    subprocess.run(["git", "clone", repo_dir, target_dir], check=True)
    if commit:
        subprocess.run(["git", "checkout", commit], check=True, cwd=target_dir)


def run_benchmark(compiled_dir: str, check_dir: str) -> float:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(compiled_dir)
    cmd = ["python3", "-m", "mypy", "--config-file", "mypy_self_check.ini"]
    cmd += glob.glob("mypy/*.py", root_dir=check_dir)
    cmd += glob.glob("mypy/*/*.py", root_dir=check_dir)
    t0 = time.time()
    subprocess.run(cmd, cwd=check_dir, env=env)
    return time.time() - t0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("commit", nargs="+")
    args = parser.parse_args()
    commits = args.commit
    num_bench = 2

    if not os.path.isdir(".git") or not os.path.isdir("mypyc"):
        sys.exit("error: Run this the mypy repo root")

    build_threads = []
    target_dirs = []
    for i, commit in enumerate(commits):
        target_dir = f"mypy.{i}.tmpdir"
        target_dirs.append(target_dir)
        clone(target_dir, commit)
        t = threading.Thread(target=lambda: build_mypy(target_dir))
        t.start()
        build_threads.append(t)

    self_check_dir = "mypy.self.tmpdir"
    clone(self_check_dir, None)

    for t in build_threads:
        t.join()

    print(f"built mypy at {len(commits)} commits")

    results: dict[str, list[float]] = {}
    for i in range(num_bench):
        for i, commit in enumerate(commits):
            tt = run_benchmark(target_dirs[i], self_check_dir)
            results.setdefault(commit, []).append(tt)

    for commit in commits:
        tt = statistics.mean(results[commit])
        print(f"commit: {tt:.1f}s")


if __name__ == "__main__":
    main()
