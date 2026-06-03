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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed


def winsorized_paired_stats(
    diffs: list[float], *, trim_frac: float = 0.1, conf: float = 0.95
) -> dict[str, float]:
    """Robust summary of a list of per-round paired differences.

    Point estimate: trimmed mean (drop ``trim_frac`` of values from each end), so a
    single outlier round cannot drag the estimate.

    Error bar: the Tukey-McLaughlin standard error of the trimmed mean, built from the
    *Winsorized* variance. The tails are clamped to the boundary kept-value rather than
    deleted -- deleting them and taking the ordinary variance of the survivors would
    understate the error bar (it would measure only how calm the middle is, discarding
    the fact that the tails were wild). The ``(1 - 2*trim_frac)`` divisor rescales for
    the compression Winsorizing introduces.

    Returns trimmed-mean estimate, median, the 95% CI half-width, and the kept count.
    A normal-approx critical value is used (fine for the n>=~30 runs this is used with).
    """
    n = len(diffs)
    s = sorted(diffs)
    g = int(n * trim_frac)  # number trimmed from each end
    median = statistics.median(s)
    if n < 2 or n - 2 * g < 2:
        est = statistics.mean(s)
        return {"est": est, "median": median, "ci": 0.0, "kept": float(n)}
    kept = s[g : n - g]
    est = statistics.mean(kept)
    # Winsorize: clamp the g smallest up to kept[0], the g largest down to kept[-1].
    wins = [kept[0]] * g + kept + [kept[-1]] * g
    wvar = statistics.variance(wins)  # sample Winsorized variance (df = n-1)
    se = (wvar**0.5) / ((1 - 2 * trim_frac) * (n**0.5))
    z = statistics.NormalDist().inv_cdf(0.5 + conf / 2)
    return {"est": est, "median": median, "ci": z * se, "kept": float(len(kept))}


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
    compiled_dir: str,
    check_dir: str,
    *,
    incremental: bool,
    code: str | None,
    foreign: bool | None,
    metric: str = "wall",
    workers1: bool = False,
) -> float:
    cache_dir = os.path.join(compiled_dir, ".mypy_cache")
    if os.path.isdir(cache_dir) and not incremental:
        shutil.rmtree(cache_dir)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(compiled_dir)
    env["PYTHONHASHSEED"] = "1"
    if workers1:
        env["MYPY_NUM_WORKERS"] = "1"
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

    def run() -> None:
        # Ignore errors, since some commits being measured may generate additional errors.
        if foreign:
            subprocess.run(cmd, cwd=check_dir, env=env)
        else:
            subprocess.run(cmd, cwd=compiled_dir, env=env)

    if metric == "wall":
        stopwatch_func_w: Callable[[], float] = lambda: time.time()
        delta_func_w: Callable[[float, float], float] = lambda t0, t1: t1 - t0

        v0_w = stopwatch_func_w()  # capture
        run()
        v1_w = stopwatch_func_w()  # capture
        return delta_func_w(v0_w, v1_w)
    elif metric == "cpu":
        if sys.platform == "win32":
            raise NotImplementedError("--metric cpu is not implemented on Windows")
        import resource  # type: ignore[unreachable]
        from resource import struct_rusage as rusage  # type: ignore[attr-defined]

        stopwatch_func_c: Callable[[], rusage] = lambda: resource.getrusage(
            resource.RUSAGE_CHILDREN
        )
        delta_func_c: Callable[[rusage, rusage], float] = lambda r0, r1: (
            r1.ru_utime - r0.ru_utime
        ) + (r1.ru_stime - r0.ru_stime)

        v0_c = stopwatch_func_c()  # capture
        run()
        v1_c = stopwatch_func_c()  # capture
        return delta_func_c(v0_c, v1_c)
    else:
        raise AssertionError(f"Unrecognized metric: {metric!r}")


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
        "--warmup-runs",
        metavar="N",
        default=1,
        type=int,
        help="set number of leading warmup runs to discard (default=1)",
    )
    parser.add_argument(
        "--cache-binaries",
        default=False,
        action="store_true",
        help="cache each commit's compiled clone under "
        + "<script_dir>/perf_compare/binaries/<commit> and restore from there on later runs, "
        + "skipping the ~5-min clone+compile. Off by default so it doesn't silently consume "
        + "disk. Caveat: the cache is keyed by the commit string you pass, so reuse stable SHAs "
        + "(a moving ref like a branch name or HEAD can serve a stale build -- delete the cache "
        + "dir if in doubt).",
    )
    parser.add_argument(
        "--metric",
        choices=["wall", "cpu"],
        default="wall",
        help="quantity to measure per run: 'wall' (wall-clock, default) or 'cpu' (user+sys "
        + "CPU time of the type-check process). 'cpu' is much less sensitive to background "
        + "interference and scheduling, so it tightens the per-run distribution.",
    )
    parser.add_argument(
        "--workers1",
        default=False,
        action="store_true",
        help="run selfcheck with a single mypy worker (MYPY_NUM_WORKERS=1) to "
        + "decrease variance in measurements. "
        + "Strongly recommended when --metric=cpu. "
        + "When omitted, uses mypy's default worker count.",
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
    baseline_commit: str = commits[0]
    warmup_runs: int = args.warmup_runs
    measurement_runs: int = args.num_runs
    num_runs: int = measurement_runs + warmup_runs
    max_workers: int = args.j
    code: str | None = args.c
    foreign_repo: str | None = args.r
    metric: str = args.metric
    workers1: bool = args.workers1
    cache_binaries: bool = args.cache_binaries

    if not (os.path.isdir(".git") and os.path.isdir("mypyc")):
        sys.exit("error: You must run this script from the mypy repo root")

    archive_root = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "perf_compare", "binaries"
    )

    target_dirs = []
    dirs_to_compile = []
    for i, commit in enumerate(commits):
        target_dir = f"mypy.{i}.tmpdir"
        target_dirs.append(target_dir)
        if not dont_setup:
            archive = os.path.join(archive_root, commit)
            if cache_binaries and os.path.isdir(archive):
                print(f"restore: copying {archive} -> {target_dir} (skipping clone+compile)")
                if os.path.isdir(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(archive, target_dir, symlinks=True)
            else:
                clone(target_dir, commit)
                dirs_to_compile.append(target_dir)

    if foreign_repo:
        check_dir = "mypy.foreign.tmpdir"
        if not dont_setup:
            clone(check_dir, None, foreign_repo)
    else:
        check_dir = "mypy.self.tmpdir"
        if not dont_setup:
            clone(check_dir, commits[0])

    if not dont_setup and dirs_to_compile:
        heading("Compiling mypy")
        print("(This will take a while...)")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(build_mypy, target_dir, multi_file)
                for target_dir in dirs_to_compile
            ]
            for future in as_completed(futures):
                future.result()

        print(f"Finished compiling mypy ({len(dirs_to_compile)} builds)")
    elif not dont_setup:
        print("All targets restored from archive; skipping compile step.")

    workers_desc = "workers: 1" if workers1 else "workers: default"
    key_options_desc = f"(metric: {metric}-time, {workers_desc})"
    heading(f"Performing measurements {key_options_desc}")

    results: dict[str, list[float]] = {}
    for n in range(num_runs):
        if n < warmup_runs:
            print(f"Warmup {n + 1}/{warmup_runs}...")
        else:
            print(f"Run {n - warmup_runs + 1}/{num_runs - warmup_runs}...")
        items = list(enumerate(commits))
        random.shuffle(items)
        for i, commit in items:
            tt = run_benchmark(
                target_dirs[i],
                check_dir,
                incremental=incremental,
                code=code,
                foreign=bool(foreign_repo),
                metric=metric,
                workers1=workers1,
            )
            # Don't record the leading warm-up runs
            if n >= warmup_runs:
                print(f"{commit}: t={tt:.3f}s")
                results.setdefault(commit, []).append(tt)

    print()
    heading(f"Results {key_options_desc}")
    first_mean = -1.0
    first_median = -1.0
    for commit in commits:
        mean = statistics.mean(results[commit])
        median = statistics.median(results[commit])
        # pstdev (instead of stdev) is used here primarily to accommodate the case where num_runs=1
        s = statistics.pstdev(results[commit]) if len(results[commit]) > 1 else 0
        if first_mean < 0:
            delta_mean = "0.0%"
            first_mean = mean
            delta_median = "0.0%"
            first_median = median
        else:
            d1 = (mean / first_mean) - 1
            delta_mean = f"{d1:+.1%}"
            d2 = (median / first_median) - 1
            delta_median = f"{d2:+.1%}"
        print(
            f"{commit:<25} mean {mean:.3f}s ({delta_mean}) | stdev {s:.3f}s | "
            f"median {median:.3f}s ({delta_median})"
        )

    # Paired per-round differences vs the baseline commit. Each round runs every commit
    # once, so results[commit][k] is round k for every commit -- the differences are
    # already matched. Differencing cancels round-level common-mode noise (a throttle or
    # background-process spike that round slows every commit together), which is the bulk
    # of the variance on a laptop. See winsorized_paired_stats for the robust estimator.
    base_runs = results[baseline_commit]
    base_center = statistics.median(base_runs)
    heading(f"Paired deltas vs {baseline_commit} (per-round diffs; median +/- 95% CI)")
    for commit in commits:
        if commit == baseline_commit:
            print(f"{commit:<25} baseline")
            continue
        diffs = [c - b for c, b in zip(results[commit], base_runs)]
        st = winsorized_paired_stats(diffs)
        ci_ms = st["ci"] * 1000
        median_ms = st["median"] * 1000
        pct = (st["median"] / base_center * 100) if base_center else 0.0
        print(f"{commit:<25} median {median_ms:+7.1f}ms  +/-{ci_ms:4.1f}  ({pct:+.2f}%)")

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

    # Archive compiled clones before cleanup, keyed by commit, so later runs can
    # restore them instead of recompiling. Skip if destination already exists.
    if cache_binaries:
        os.makedirs(archive_root, exist_ok=True)
        for target_dir, commit in zip(target_dirs, commits):
            dest = os.path.join(archive_root, commit)
            if os.path.isdir(dest):
                print(f"archive: {dest} already exists, skipping")
            else:
                print(f"archive: copying {target_dir} -> {dest}")
                shutil.copytree(target_dir, dest, symlinks=True)

    shutil.rmtree(check_dir)
    for target_dir in target_dirs:
        shutil.rmtree(target_dir)


if __name__ == "__main__":
    main()
