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
            --repo-url https://github.com/python/mypy.git \\
            --file-path mypy

You can chose to run this script against a specific commit id or against the
last n commits.

To run this script against the last 30 commits:

    python3 misc/incremental_checker.py last 30

To run this script starting from the commit id 2a432b:

    python3 misc/incremental_checker.py commit 2a432b

You can also choose to run against a random path through the commits:

    python3 misc/incremental_checker.py --random 10 last 30
"""

from typing import Any, Dict, List, Optional, Tuple, TypeVar

from argparse import (ArgumentParser, RawDescriptionHelpFormatter,
                      ArgumentDefaultsHelpFormatter, Namespace)
import base64
import json
import os
import random
import shutil
import subprocess
import sys
import textwrap
import time


CACHE_PATH = ".incremental_checker_cache.json"
MYPY_REPO_URL = "https://github.com/python/mypy.git"
MYPY_TARGET_FILE = "mypy"

JsonDict = Dict[str, Any]


def print_offset(text: str, indent_length: int = 4) -> None:
    print()
    print(textwrap.indent(text, ' ' * indent_length))
    print()


def delete_folder(folder_path: str) -> None:
    if os.path.islink(folder_path):
        os.remove(folder_path)
    elif os.path.exists(folder_path):
        shutil.rmtree(folder_path)


def execute(command: List[str], fail_on_error: bool = True,
            cwd: str = None) -> Tuple[str, str, int]:
    proc = subprocess.Popen(
        ' '.join(command),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=True,
        cwd=cwd)
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


def initialize_repo(repo_url: Optional[str], repo_dir: Optional[str], temp_repo_path: str,
                    branch: str) -> None:
    if repo_dir is None:
        assert repo_url is not None
        print("Cloning repo {0} to {1}".format(repo_url, temp_repo_path))
        execute(["git", "clone", repo_url, temp_repo_path])
    else:
        assert repo_url is None
        print("Linking repo {0} to {1}".format(repo_dir, temp_repo_path))
        execute(["ln", "-s", repo_dir, temp_repo_path])
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


def get_nth_commit(repo_folder_path, n: int) -> Tuple[str, str]:
    print("Fetching last {} commits (or all, if there are fewer commits than n)".format(n))
    return get_commits(repo_folder_path, '-{}'.format(n))[0]


def run_mypy(target_file_path: Optional[str],
             mypy_cache_path: str,
             mypy_script: Optional[str],
             incremental: bool = True,
             quick: bool = False,
             verbose: bool = False,
             cwd: Optional[str] = None) -> Tuple[float, str]:
    """Runs mypy against `target_file_path` and returns what mypy prints to stdout as a string.

    If `incremental` is set to True, this function will use store and retrieve all caching data
    inside `mypy_cache_path`. If `verbose` is set to True, this function will pass the "-v -v"
    flags to mypy to make it output debugging information.

    If `quick` is set to True, use the quick mode. It implies `incremental`.
    """
    if mypy_script is None:
        command = ["python3", "-m", "mypy"]
    else:
        command = [mypy_script]
    command.extend(["--cache-dir", mypy_cache_path])
    command.append('--show-traceback')
    if incremental:
        command.append("--incremental")
    if quick:
        command.append("--quick")
    if verbose:
        command.extend(["-v", "-v"])
    if target_file_path is not None:
        command.append(target_file_path)
    start = time.time()
    output, stderr, _ = execute(command, False, cwd=cwd)
    if stderr != "":
        if output:
            output = stderr + '\n' + output
        else:
            output = stderr
    runtime = time.time() - start
    return runtime, output


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
                 all_commit_ids: List[str],
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
        index = all_commit_ids.index(commit_id)
        if commit_id in cache:
            print('Skipping commit (already cached): {} (#{}): "{}"'.format(
                commit_id, index, message))
        else:
            print('Caching expected output for commit {} (#{}): "{}"'.format(
                commit_id, index, message))
            execute(["git", "-C", temp_repo_path, "checkout", commit_id])
            runtime, output = run_mypy(target_file_path, mypy_cache_path, mypy_script,
                                       incremental=False, cwd=temp_repo_path)
            cache[commit_id] = {'runtime': runtime, 'output': output}
            if output == "":
                print("    Clean output ({:.3f} sec)".format(runtime))
            else:
                print("    Output ({:.3f} sec)".format(runtime))
                print_offset(output, 8)
    print()


def test_incremental(commits: List[Tuple[str, str]],
                     all_commit_ids: List[str],
                     cache: JsonDict,
                     temp_repo_path: str,
                     target_file_path: Optional[str],
                     mypy_cache_path: str,
                     mypy_script: Optional[str],
                     quick: bool) -> None:
    """Runs incremental mode on all `commits` to verify the output matches the expected output.

    This function runs mypy on the `target_file_path` inside the `temp_repo_path`. The
    expected output must be stored inside of the given `cache`.
    """
    print("Note: first commit is evaluated twice to warm up cache")
    commits = [commits[0]] + commits
    for commit_id, message in commits:
        index = all_commit_ids.index(commit_id)
        print('Now testing commit {} (#{}): "{}"'.format(commit_id, index, message))
        execute(["git", "-C", temp_repo_path, "checkout", commit_id])
        runtime, output = run_mypy(target_file_path, mypy_cache_path, mypy_script,
                                   incremental=True, quick=quick, cwd=temp_repo_path)
        expected_runtime = cache[commit_id]['runtime']  # type: float
        expected_output = cache[commit_id]['output']  # type: str
        if quick:
            # Quick mode can generate different output from normal mode, so only
            # look for crashes.
            fail = 'Traceback (most recent call last)' in output or 'INTERNAL ERROR' in output
        else:
            fail = output != expected_output
        if fail:
            print("    Output does not match expected result!")
            print("    Expected output ({:.3f} sec):".format(expected_runtime))
            expected_output = expected_output.strip()
            if not expected_output:
                expected_output = '<empty>'
            print_offset(expected_output, 8)
            print("    Actual output: ({:.3f} sec):".format(runtime))
            print_offset(output.strip(), 8)
        else:
            print("    OK")
            print("    Incremental: {:.3f} sec".format(runtime))
            print("    Original:    {:.3f} sec".format(expected_runtime))


def cleanup(temp_repo_path: str, mypy_cache_path: str) -> None:
    delete_folder(temp_repo_path)
    delete_folder(mypy_cache_path)


T = TypeVar('T')


def biased_sample(items: List[T], sample_size: int) -> List[T]:
    """Return a biased random sample of commits.

    Bias towards returning items close to each other in the sequence,
    but also jump across the whole commit range.
    """
    result = []
    n = len(items)
    index = random.randrange(n)
    near_range = 5
    for _ in range(sample_size):
        result.append(items[index])
        # Bias towards short jumps since they are more likely to not invalidate
        # large parts of the program.
        step_type = random.choice(['near'] * 2 + ['far'] * 1)
        if step_type == 'near':
            start = max(0, index - near_range)
            stop = min(n, index + near_range + 1)
            index = random.choice([i for i in range(start, stop) if i != index])
        else:
            index = random.randrange(n)
    return result


def test_repo(target_repo_url: Optional[str], target_repo_dir: Optional[str],
              temp_repo_path: str, target_file_path: Optional[str],
              mypy_path: str, incremental_cache_path: str, mypy_cache_path: str,
              range_type: str, range_start: str, branch: str,
              quick: bool, params: Optional[Namespace] = None) -> None:
    """Tests incremental mode against the repo specified in `target_repo_url`.

    This algorithm runs in five main stages:

    1.  Clones `target_repo_url` into the `temp_repo_path` folder locally,
        checking out the specified `branch` if applicable (or links
        `target_repo_dir` to `temp_repo_path`).
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
    assert target_repo_url or target_repo_dir
    # Stage 1: Clone repo and get ready to being testing
    ensure_environment_is_ready(mypy_path, temp_repo_path, mypy_cache_path)
    initialize_repo(target_repo_url, target_repo_dir, temp_repo_path, branch)

    # Stage 2: Get all commits we want to test
    if range_type == "last":
        start_commit = get_nth_commit(temp_repo_path, int(range_start))[0]
    elif range_type == "commit":
        start_commit = range_start
    else:
        raise RuntimeError("Invalid option: {}".format(range_type))
    commits = get_commits_starting_at(temp_repo_path, start_commit)
    all_commit_ids = [commit_id for commit_id, _ in commits]
    if params is not None and params.random:
        seed = params.seed or base64.urlsafe_b64encode(os.urandom(15)).decode('ascii')
        random.seed(seed)
        commits = biased_sample(commits, params.random)
        print("Sampled down to %d commits using random seed %s" % (len(commits), seed))

    # Stage 3: Find and cache expected results for each commit (without incremental mode)
    cache = load_cache(incremental_cache_path)
    mypy_script = os.path.join(target_repo_dir, params.mypy_script) if params else None
    set_expected(commits, all_commit_ids, cache, temp_repo_path, target_file_path, mypy_cache_path,
                 mypy_script=mypy_script)
    save_cache(cache, incremental_cache_path)

    # Stage 4: Rewind and re-run mypy (with incremental or quick mode enabled)
    test_incremental(commits, all_commit_ids, cache, temp_repo_path, target_file_path,
                     mypy_cache_path, mypy_script=mypy_script, quick=quick)

    # Stage 5: Remove temp files
    cleanup(temp_repo_path, mypy_cache_path)


def main() -> None:
    parser = ArgumentParser(
        prog='incremental_checker',
        description=__doc__,
        formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument("range_type", metavar="START_TYPE", choices=["last", "commit"],
                        help="must be one of 'last' or 'commit'")
    parser.add_argument("range_start", metavar="COMMIT_ID_OR_NUMBER",
                        help="the commit id to start from, or the number of "
                        "commits to move back (see above)")
    parser.add_argument("-r", "--repo-url", metavar="URL",
                        help="the repo to clone and run tests on")
    parser.add_argument("-d", "--repo-dir", metavar="DIR",
                        help=("the repository directory to run tests on; alternative to --repo-url"
                              " (local changes will be lost!)"))
    parser.add_argument("-f", "--file-path", metavar="FILE",
                        help="the name of the file or directory to typecheck")
    parser.add_argument("--cache-path", default=CACHE_PATH, metavar="DIR",
                        help="sets a custom location to store cache data")
    parser.add_argument("--branch", default=None, metavar="NAME",
                        help="check out and test a custom branch"
                        "uses the default if not specified")
    parser.add_argument("--random", type=int, help="use a random commit path of size SAMPLE")
    parser.add_argument("--seed", type=str, help="random seed")
    parser.add_argument("--mypy-script", type=str, metavar="PATH",
                        help=("use alternate mypy run script (if not absolute, "
                              "relative to repository root)"))
    parser.add_argument("--quick", action='store_true',
                        help="use quick mode (can't verify output -- only look for crashes)")

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

    if not params.repo_dir:
        if params.repo_url:
            repo_url = params.repo_url
        else:
            repo_url = MYPY_REPO_URL
        repo_dir = None
    elif not params.repo_url:
        repo_url = None
        repo_dir = os.path.abspath(params.repo_dir)
    else:
        sys.exit('Error: Specify only one of -r/--repo-url or -d/--repo-dir')

    # The particular file or package to typecheck inside the repo.
    target_file_path = None
    if params.file_path:
        target_file_path = os.path.abspath(os.path.join(temp_repo_path, params.file_path))
    elif not params.repo_dir and not params.repo_url:
        # Automatically infer target file if defaulting to the mypy repo.
        target_file_path = MYPY_TARGET_FILE

    # The path to where the incremental checker cache data is stored.
    incremental_cache_path = os.path.abspath(params.cache_path)

    # The path to store the mypy incremental mode cache data
    mypy_cache_path = os.path.abspath(os.path.join(mypy_path, "misc", ".mypy_cache"))

    print("Assuming mypy is located at {0}".format(mypy_path))
    print("Temp repo will be cloned at {0}".format(temp_repo_path))
    print("Testing file/dir located at {0}".format(target_file_path))
    print("Using cache data located at {0}".format(incremental_cache_path))
    print()

    test_repo(params.repo_url, params.repo_dir, temp_repo_path, target_file_path,
              mypy_path, incremental_cache_path, mypy_cache_path,
              params.range_type, params.range_start, params.branch,
              params.quick, params)


if __name__ == '__main__':
    main()
