#!/usr/bin/env python3
"""
This file compares the output and runtime of running normal vs incremental mode
on the history of any arbitrary git repo as a way of performing a sanity check
to make sure incremental mode is working correctly and efficiently.

It does so by first running mypy without incremental mode on the specified range
of commits to find the expected result, then rewinds back to the first commit and
re-runs mypy on the commits with incremental mode enabled to make sure it returns
the same results.

This script will download and test the official mypy repo by default. Running:

    python3 misc/incremental_checker.py last 30

is equivalent to running

    python3 misc/incremental_checker.py last 30 \\
            --repo_url https://github.com/python/mypy.git \\
            --file-path mypy

You can chose to run this script against a specific commit id or against the
last n commits.

To run this script against the last 30 commits:

    python3 misc/incremental_checker.py last 30

To run this script starting from the commit id 2a432b:

    python3 misc/incremental_checker.py commit 2a432b
"""

from typing import Any, Dict, List, Optional, Tuple

from argparse import ArgumentParser, RawDescriptionHelpFormatter, Namespace
import base64
import json
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time


CACHE_PATH = ".incremental_checker_cache.json"
MYPY_REPO_URL = "https://github.com/python/mypy.git"
MYPY_TARGET_FILE = "mypy"
DAEMON_CMD = ["python3", "-m", "mypy.dmypy"]

JsonDict = Dict[str, Any]


def print_offset(text: str, indent_length: int = 4) -> None:
    print()
    print(textwrap.indent(text, ' ' * indent_length))
    print()


def delete_folder(folder_path: str) -> None:
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)


def execute(command: List[str], fail_on_error: bool = True) -> Tuple[str, str, int]:
    proc = subprocess.Popen(
        ' '.join(command),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=True)
    stdout_bytes, stderr_bytes = proc.communicate()  # type: Tuple[bytes, bytes]
    stdout, stderr = stdout_bytes.decode('utf-8'), stderr_bytes.decode('utf-8')
    if fail_on_error and proc.returncode != 0:
        print('EXECUTED COMMAND:', repr(command))
        print('RETURN CODE:', proc.returncode)
        print()
        print('STDOUT:')
        print_offset(stdout)
        print('STDERR:')
        print_offset(stderr)
        raise RuntimeError('Unexpected error from external tool.')
    return stdout, stderr, proc.returncode


def ensure_environment_is_ready(mypy_path: str, temp_repo_path: str, mypy_cache_path: str) -> None:
    os.chdir(mypy_path)
    delete_folder(temp_repo_path)
    delete_folder(mypy_cache_path)


def initialize_repo(repo_url: str, temp_repo_path: str, branch: str) -> None:
    print("Cloning repo {0} to {1}".format(repo_url, temp_repo_path))
    execute(["git", "clone", repo_url, temp_repo_path])
    if branch is not None:
        print("Checking out branch {}".format(branch))
        execute(["git", "-C", temp_repo_path, "checkout", branch])


def get_commits(repo_folder_path: str, commit_range: str) -> List[Tuple[str, str]]:
    raw_data, _stderr, _errcode = execute([
        "git", "-C", repo_folder_path, "log", "--reverse", "--oneline", commit_range])
    output = []
    for line in raw_data.strip().split('\n'):
        commit_id, _, message = line.partition(' ')
        output.append((commit_id, message))
    return output


def get_commits_starting_at(repo_folder_path: str, start_commit: str) -> List[Tuple[str, str]]:
    print("Fetching commits starting at {0}".format(start_commit))
    return get_commits(repo_folder_path, '{0}^..HEAD'.format(start_commit))


def get_nth_commit(repo_folder_path: str, n: int) -> Tuple[str, str]:
    print("Fetching last {} commits (or all, if there are fewer commits than n)".format(n))
    return get_commits(repo_folder_path, '-{}'.format(n))[0]


def run_mypy(target_file_path: Optional[str],
             mypy_cache_path: str,
             mypy_script: Optional[str],
             *,
             incremental: bool = False,
             daemon: bool = False,
             verbose: bool = False) -> Tuple[float, str, Dict[str, Any]]:
    """Runs mypy against `target_file_path` and returns what mypy prints to stdout as a string.

    If `incremental` is set to True, this function will use store and retrieve all caching data
    inside `mypy_cache_path`. If `verbose` is set to True, this function will pass the "-v -v"
    flags to mypy to make it output debugging information.

    If `daemon` is True, we use daemon mode; the daemon must be started and stopped by the caller.
    """
    stats = {}  # type: Dict[str, Any]
    if daemon:
        command = DAEMON_CMD + ["check", "-v"]
    else:
        if mypy_script is None:
            command = ["python3", "-m", "mypy"]
        else:
            command = [mypy_script]
        command.extend(["--cache-dir", mypy_cache_path])
        if incremental:
            command.append("--incremental")
        if verbose:
            command.extend(["-v", "-v"])
    if target_file_path is not None:
        command.append(target_file_path)
    start = time.time()
    output, stderr, _ = execute(command, False)
    if stderr != "":
        output = stderr
    else:
        if daemon:
            output, stats = filter_daemon_stats(output)
    runtime = time.time() - start
    return runtime, output, stats


def filter_daemon_stats(output: str) -> Tuple[str, Dict[str, Any]]:
    stats = {}  # type: Dict[str, Any]
    lines = output.splitlines()
    output_lines = []
    for line in lines:
        m = re.match(r'(\w+)\s+:\s+(.*)', line)
        if m:
            key, value = m.groups()
            stats[key] = value
        else:
            output_lines.append(line)
    if output_lines:
        output_lines.append('\n')
    return '\n'.join(output_lines), stats


def start_daemon(mypy_cache_path: str) -> None:
    cmd = DAEMON_CMD + ["restart", "--log-file", "./@incr-chk-logs", "--", "--cache-dir", mypy_cache_path]
    execute(cmd)


def stop_daemon() -> None:
    execute(DAEMON_CMD + ["stop"])


def load_cache(incremental_cache_path: str = CACHE_PATH) -> JsonDict:
    if os.path.exists(incremental_cache_path):
        with open(incremental_cache_path, 'r') as stream:
            return json.load(stream)
    else:
        return {}


def save_cache(cache: JsonDict, incremental_cache_path: str = CACHE_PATH) -> None:
    with open(incremental_cache_path, 'w') as stream:
        json.dump(cache, stream, indent=2)


def set_expected(commits: List[Tuple[str, str]],
                 cache: JsonDict,
                 temp_repo_path: str,
                 target_file_path: Optional[str],
                 mypy_cache_path: str,
                 mypy_script: Optional[str]) -> None:
    """Populates the given `cache` with the expected results for all of the given `commits`.

    This function runs mypy on the `target_file_path` inside the `temp_repo_path`, and stores
    the result in the `cache`.

    If `cache` already contains results for a particular commit, this function will
    skip evaluating that commit and move on to the next."""
    for commit_id, message in commits:
        if commit_id in cache:
            print('Skipping commit (already cached): {0}: "{1}"'.format(commit_id, message))
        else:
            print('Caching expected output for commit {0}: "{1}"'.format(commit_id, message))
            execute(["git", "-C", temp_repo_path, "checkout", commit_id])
            runtime, output, stats = run_mypy(target_file_path, mypy_cache_path, mypy_script,
                                              incremental=False)
            cache[commit_id] = {'runtime': runtime, 'output': output}
            if output == "":
                print("    Clean output ({:.3f} sec)".format(runtime))
            else:
                print("    Output ({:.3f} sec)".format(runtime))
                print_offset(output, 8)
    print()


def test_incremental(commits: List[Tuple[str, str]],
                     cache: JsonDict,
                     temp_repo_path: str,
                     target_file_path: Optional[str],
                     mypy_cache_path: str,
                     *,
                     mypy_script: Optional[str] = None,
                     daemon: bool = False,
                     exit_on_error: bool = False) -> None:
    """Runs incremental mode on all `commits` to verify the output matches the expected output.

    This function runs mypy on the `target_file_path` inside the `temp_repo_path`. The
    expected output must be stored inside of the given `cache`.
    """
    print("Note: first commit is evaluated twice to warm up cache")
    commits = [commits[0]] + commits
    overall_stats = {}  # type: Dict[str, float]
    for commit_id, message in commits:
        print('Now testing commit {0}: "{1}"'.format(commit_id, message))
        execute(["git", "-C", temp_repo_path, "checkout", commit_id])
        runtime, output, stats = run_mypy(target_file_path, mypy_cache_path, mypy_script,
                                          incremental=True, daemon=daemon)
        relevant_stats = combine_stats(overall_stats, stats)
        expected_runtime = cache[commit_id]['runtime']  # type: float
        expected_output = cache[commit_id]['output']  # type: str
        if output != expected_output:
            print("    Output does not match expected result!")
            print("    Expected output ({:.3f} sec):".format(expected_runtime))
            print_offset(expected_output, 8)
            print("    Actual output: ({:.3f} sec):".format(runtime))
            print_offset(output, 8)
            if exit_on_error:
                break
        else:
            print("    Output matches expected result!")
            print("    Incremental: {:.3f} sec".format(runtime))
            print("    Original:    {:.3f} sec".format(expected_runtime))
            if relevant_stats:
                print("    Stats:       {}".format(relevant_stats))
    if overall_stats:
        print("Overall stats:", overall_stats)


def combine_stats(overall_stats: Dict[str, float],
                  new_stats: Dict[str, Any]) -> Dict[str, float]:
    INTERESTING_KEYS = ['build_time', 'gc_time']
    # For now, we only support float keys
    relevant_stats = {}  # type: Dict[str, float]
    for key in INTERESTING_KEYS:
        if key in new_stats:
            value = float(new_stats[key])
            relevant_stats[key] = value
            overall_stats[key] = overall_stats.get(key, 0.0) + value
    return relevant_stats


def cleanup(temp_repo_path: str, mypy_cache_path: str) -> None:
    delete_folder(temp_repo_path)
    delete_folder(mypy_cache_path)


def test_repo(target_repo_url: str, temp_repo_path: str,
              target_file_path: Optional[str],
              mypy_path: str, incremental_cache_path: str, mypy_cache_path: str,
              range_type: str, range_start: str, branch: str,
              params: Namespace) -> None:
    """Tests incremental mode against the repo specified in `target_repo_url`.

    This algorithm runs in five main stages:

    1.  Clones `target_repo_url` into the `temp_repo_path` folder locally,
        checking out the specified `branch` if applicable.
    2.  Examines the repo's history to get the list of all commits to
        to test incremental mode on.
    3.  Runs mypy WITHOUT incremental mode against the `target_file_path` (which is
        assumed to be located inside the `temp_repo_path`), testing each commit
        discovered in stage two.
        -   If the results of running mypy WITHOUT incremental mode on a
            particular commit are already cached inside the `incremental_cache_path`,
            skip that commit to save time.
        -   Cache the results after finishing.
    4.  Rewind back to the first commit, and run mypy WITH incremental mode
        against the `target_file_path` commit-by-commit, and compare to the expected
        results found in stage 3.
    5.  Delete all unnecessary temp files.
    """
    # Stage 1: Clone repo and get ready to being testing
    ensure_environment_is_ready(mypy_path, temp_repo_path, mypy_cache_path)
    initialize_repo(target_repo_url, temp_repo_path, branch)

    # Stage 2: Get all commits we want to test
    if range_type == "last":
        start_commit = get_nth_commit(temp_repo_path, int(range_start))[0]
    elif range_type == "commit":
        start_commit = range_start
    else:
        raise RuntimeError("Invalid option: {}".format(range_type))
    commits = get_commits_starting_at(temp_repo_path, start_commit)
    if params.limit:
        commits = commits[:params.limit]
    if params.sample:
        seed = params.seed or base64.urlsafe_b64encode(os.urandom(15)).decode('ascii')
        random.seed(seed)
        commits = random.sample(commits, params.sample)
        print("Sampled down to %d commits using random seed %s" % (len(commits), seed))

    # Stage 3: Find and cache expected results for each commit (without incremental mode)
    cache = load_cache(incremental_cache_path)
    set_expected(commits, cache, temp_repo_path, target_file_path, mypy_cache_path,
                 mypy_script=params.mypy_script)
    save_cache(cache, incremental_cache_path)

    # Stage 4: Rewind and re-run mypy (with incremental mode enabled)
    if params.daemon:
        print('Starting daemon')
        start_daemon(mypy_cache_path)
    test_incremental(commits, cache, temp_repo_path, target_file_path, mypy_cache_path,
                     mypy_script=params.mypy_script, daemon=params.daemon,
                     exit_on_error=params.exit_on_error)

    # Stage 5: Remove temp files, stop daemon
    if not params.keep_temporary_files:
        cleanup(temp_repo_path, mypy_cache_path)
    if params.daemon:
        print('Stopping daemon')
        stop_daemon()


def main() -> None:
    help_factory = (lambda prog: RawDescriptionHelpFormatter(prog=prog, max_help_position=32))  # type: Any
    parser = ArgumentParser(
        prog='incremental_checker',
        description=__doc__,
        formatter_class=help_factory)

    parser.add_argument("range_type", metavar="START_TYPE", choices=["last", "commit"],
                        help="must be one of 'last' or 'commit'")
    parser.add_argument("range_start", metavar="COMMIT_ID_OR_NUMBER",
                        help="the commit id to start from, or the number of "
                        "commits to move back (see above)")
    parser.add_argument("-r", "--repo_url", default=MYPY_REPO_URL, metavar="URL",
                        help="the repo to clone and run tests on")
    parser.add_argument("-f", "--file-path", default=MYPY_TARGET_FILE, metavar="FILE",
                        help="the name of the file or directory to typecheck")
    parser.add_argument("-x", "--exit-on-error", action='store_true',
                        help="Exits as soon as an error occurs")
    parser.add_argument("--keep-temporary-files", action='store_true',
                        help="Keep temporary files on exit")
    parser.add_argument("--cache-path", default=CACHE_PATH, metavar="DIR",
                        help="sets a custom location to store cache data")
    parser.add_argument("--branch", default=None, metavar="NAME",
                        help="check out and test a custom branch"
                        "uses the default if not specified")
    parser.add_argument("--sample", type=int, help="use a random sample of size SAMPLE")
    parser.add_argument("--seed", type=str, help="random seed")
    parser.add_argument("--limit", type=int,
                        help="maximum number of commits to use (default until end)")
    parser.add_argument("--mypy-script", type=str, help="alternate mypy script to run")
    parser.add_argument("--daemon", action='store_true',
                        help="use mypy daemon instead of incremental (highly experimental)")

    if len(sys.argv[1:]) == 0:
        parser.print_help()
        parser.exit()

    params = parser.parse_args(sys.argv[1:])

    # Make all paths absolute so we avoid having to worry about being in the right folder

    # The path to this specific script (incremental_checker.py).
    script_path = os.path.abspath(sys.argv[0])

    # The path to the mypy repo.
    mypy_path = os.path.abspath(os.path.dirname(os.path.dirname(script_path)))

    # The folder the cloned repo will reside in.
    temp_repo_path = os.path.abspath(os.path.join(mypy_path, "tmp_repo"))

    # The particular file or package to typecheck inside the repo.
    if params.file_path:
        target_file_path = os.path.abspath(os.path.join(temp_repo_path, params.file_path))
    else:
        # Allow `-f ''` to clear target_file_path.
        target_file_path = None

    # The path to where the incremental checker cache data is stored.
    incremental_cache_path = os.path.abspath(params.cache_path)

    # The path to store the mypy incremental mode cache data
    mypy_cache_path = os.path.abspath(os.path.join(mypy_path, "misc", ".mypy_cache"))

    print("Assuming mypy is located at {0}".format(mypy_path))
    print("Temp repo will be cloned at {0}".format(temp_repo_path))
    print("Testing file/dir located at {0}".format(target_file_path))
    print("Using cache data located at {0}".format(incremental_cache_path))
    print()

    test_repo(params.repo_url, temp_repo_path, target_file_path,
              mypy_path, incremental_cache_path, mypy_cache_path,
              params.range_type, params.range_start, params.branch,
              params)


if __name__ == '__main__':
    main()
