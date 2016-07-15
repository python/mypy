#!/usr/bin/env python
"""
This file compares the output and runtime of running normal vs
incremental mode on the history of any arbitrary git repo as a
way of performing a sanity check to make sure incremental mode
is working correctly and efficiently.

This script will, by default, run all tests against mypy's repo.
"""

from typing import Any, Dict, List, Tuple

from argparse import ArgumentParser, RawDescriptionHelpFormatter, ArgumentDefaultsHelpFormatter
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time


LOOK_BACK = 30
CACHE_PATH = ".incremental_checker_cache.json"
MYPY_REPO_URL = "https://github.com/python/mypy.git"
MYPY_MODULE_NAME = "mypy"

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
        print("RETURN CODE:", proc.returncode)
        print()
        print('STDOUT:')
        print_offset(stdout)
        print('STDERR:')
        print_offset(stderr)
        raise Exception("Unexpected error from external tool.")
    return stdout, stderr, proc.returncode


def initialize_repo(repo_url: str, folder_path: str, branch: str) -> None:
    print("Cloning repo {0} to {1}".format(repo_url, folder_path))
    delete_folder(folder_path)
    delete_folder("misc/.mypy_cache")
    execute(["git", "clone", repo_url, folder_path])
    if branch is not None:
        execute(["git", "-C", folder_path, "checkout", branch])


def get_commits(repo_folder_name: str, commit_range: str) -> List[Tuple[str, str]]:
    raw_data,_ , _ = execute([
        "git", "-C", repo_folder_name, "log", "--reverse", "--oneline", commit_range])
    output = []
    for line in raw_data.strip().split('\n'):
        commit_id, _, message = line.partition(' ')
        output.append((commit_id, message))
    return output


def get_commits_starting_at(repo_folder_name: str, start_commit: str) -> List[Tuple[str, str]]:
    print("Fetching commits starting at {0}".format(start_commit))
    return get_commits(repo_folder_name, '{0}^..HEAD'.format(start_commit))


def get_nth_commit(repo_folder_name, n: int) -> Tuple[str, str]:
    print("Fetching last {}th commit (or earliest)".format(n))
    return get_commits(repo_folder_name, '-{}'.format(n))[0]


def run_mypy(target: str,
             incremental: bool = True,
             verbose: bool = False) -> Tuple[float, str]:
    command = ["python3", "-m", "mypy", "--cache-dir", "misc/.mypy_cache"]
    if incremental:
        command.append("--incremental")
    if verbose:
        command.extend(["-v", "-v"])
    command.append(target)
    start = time.time()
    output, stderr, _ = execute(command, False)
    if stderr != "":
        output = stderr
    delta = time.time() - start
    return delta, output


def load_cache(cache_path: str = CACHE_PATH) -> JsonDict:
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as stream:
            return json.load(stream)
    else:
        return {}


def save_cache(cache: JsonDict, cache_path: str = CACHE_PATH) -> None:
    with open(cache_path, 'w') as stream:
        json.dump(cache, stream, indent=2)


def set_expected(commits: List[Tuple[str, str]],
                 cache: JsonDict,
                 repo_name: str,
                 target: str) -> None:
    for commit_id, message in commits:
        if commit_id in cache:
            print('Skipping commit (already cached): {0}: "{1}"'.format(commit_id, message))
        else:
            print('Caching expected output for commit {0}: "{1}"'.format(commit_id, message))
            execute(["git", "-C", repo_name, "checkout", commit_id])
            delta, output = run_mypy(target, incremental=False)
            cache[commit_id] = {'delta': delta, 'output': output}
            if output == "":
                print("    Clean output ({:.3f} sec)".format(delta))
            else:
                print("    Output ({:.3f} sec)".format(delta))
                print_offset(output, 8)
    print()


def test_incremental(commits: List[Tuple[str, str]],
                     cache: JsonDict,
                     repo_name,
                     target: str) -> None:
    print("Note: first commit is evaluated twice to warm up cache")
    commits = [commits[0]] + commits
    for commit_id, message in commits:
        print('Now testing commit {0}: "{1}"'.format(commit_id, message))
        execute(["git", "-C", repo_name, "checkout", commit_id])
        delta, output = run_mypy(target)
        expected_delta = cache[commit_id]['delta']  # type: float
        expected_output = cache[commit_id]['output']  # type: str
        if output != expected_output:
            print("    Output does not match expected result!")
            print("    Expected output ({:.3f} sec):".format(expected_delta))
            print_offset(expected_output, 8)
            print("    Actual output: ({:.3f} sec):".format(delta))
            print_offset(output, 8)
        else:
            print("    Output matches expected result!")
            print("    Incremental: {:.3f} sec".format(delta))
            print("    Original:    {:.3f} sec".format(expected_delta))


def cleanup(folder_path: str) -> None:
    print("Cleanup: deleting {}".format(folder_path))
    delete_folder(folder_path)
    delete_folder("misc/.mypy_cache")


def test_repo(target_repo_url: str, module_name: str, start_commit: str,
              branch: str, cache_path: str) -> None:
    repo_folder_name = "tmp_repo"
    target = os.path.join(repo_folder_name, module_name)

    # Assume we're starting in misc
    os.chdir("..")
    initialize_repo(target_repo_url, repo_folder_name, branch)

    if start_commit is None:
        start_commit = get_nth_commit(repo_folder_name, LOOK_BACK)[0]
    commits = get_commits_starting_at(repo_folder_name, start_commit)

    cache = load_cache(cache_path)
    set_expected(commits, cache, repo_folder_name, target)
    save_cache(cache, cache_path)

    test_incremental(commits, cache, repo_folder_name, target)

    cleanup(repo_folder_name)


def main() -> None:
    help_factory = (lambda prog: RawDescriptionHelpFormatter(prog=prog, max_help_position=32))
    parser = ArgumentParser(
        prog='incremental_checker',
        description=__doc__,
        formatter_class=help_factory)

    parser.add_argument("-r", "--repo_url", default=MYPY_REPO_URL, metavar="URL",
                        help="the repo to clone and run tests on")
    parser.add_argument("-m", "--module-name", default=MYPY_MODULE_NAME, metavar="NAME",
                        help="the name of the module to typecheck")
    parser.add_argument("-C", "--commit-id", default=None, metavar="ID",
                        help="the commit id to start from "
                        "(starts {} commits back if missing)".format(LOOK_BACK))
    parser.add_argument("--cache-path", default=CACHE_PATH, metavar="DIR",
                        help="sets a custom location to store cache data")
    parser.add_argument("--branch", default=None, metavar="NAME",
                        help="check out and test a custom branch"
                        "uses the default if not specified")

    params = parser.parse_args(sys.argv[1:])
    cache_path = os.path.abspath(params.cache_path)
    test_repo(params.repo_url, params.module_name, params.commit_id, params.branch, cache_path)


if __name__ == '__main__':
    main()
