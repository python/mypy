"""Sync stdlib stubs (and a few other files) from typeshed.

Usage:

  python3 misc/sync-typeshed.py [--commit hash] [--typeshed-dir dir]

By default, sync to the latest typeshed commit.
"""

from __future__ import annotations

import argparse
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Mapping

import requests


def check_state() -> None:
    if not os.path.isfile("pyproject.toml") or not os.path.isdir("mypy"):
        sys.exit("error: The current working directory must be the mypy repository root")
    out = subprocess.check_output(["git", "status", "-s", os.path.join("mypy", "typeshed")])
    if out:
        # If there are local changes under mypy/typeshed, they would be lost.
        sys.exit('error: Output of "git status -s mypy/typeshed" must be empty')


def update_typeshed(typeshed_dir: str, commit: str | None) -> str:
    """Update contents of local typeshed copy.

    We maintain our own separate mypy_extensions stubs, since it's
    treated specially by mypy and we make assumptions about what's there.
    We don't sync mypy_extensions stubs here -- this is done manually.

    Return the normalized typeshed commit hash.
    """
    assert os.path.isdir(os.path.join(typeshed_dir, "stdlib"))
    if commit:
        subprocess.run(["git", "checkout", commit], check=True, cwd=typeshed_dir)
    commit = git_head_commit(typeshed_dir)

    stdlib_dir = os.path.join("mypy", "typeshed", "stdlib")
    # Remove existing stubs.
    shutil.rmtree(stdlib_dir)
    # Copy new stdlib stubs.
    shutil.copytree(os.path.join(typeshed_dir, "stdlib"), stdlib_dir)
    shutil.copy(os.path.join(typeshed_dir, "LICENSE"), os.path.join("mypy", "typeshed"))
    return commit


def git_head_commit(repo: str) -> str:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode("ascii")
    return commit.strip()


@functools.cache
def get_github_api_headers() -> Mapping[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    secret = os.environ.get("GITHUB_TOKEN")
    if secret is not None:
        headers["Authorization"] = (
            f"token {secret}" if secret.startswith("ghp") else f"Bearer {secret}"
        )
    return headers


@functools.cache
def get_origin_owner() -> str:
    output = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
    match = re.match(
        r"(git@github.com:|https://github.com/)(?P<owner>[^/]+)/(?P<repo>[^/\s]+)", output
    )
    assert match is not None, f"Couldn't identify origin's owner: {output!r}"
    assert (
        match.group("repo").removesuffix(".git") == "mypy"
    ), f'Unexpected repo: {match.group("repo")!r}'
    return match.group("owner")


def create_or_update_pull_request(*, title: str, body: str, branch_name: str) -> None:
    fork_owner = get_origin_owner()

    with requests.post(
        "https://api.github.com/repos/python/mypy/pulls",
        json={
            "title": title,
            "body": body,
            "head": f"{fork_owner}:{branch_name}",
            "base": "master",
        },
        headers=get_github_api_headers(),
    ) as response:
        resp_json = response.json()
        if response.status_code == 422 and any(
            "A pull request already exists" in e.get("message", "")
            for e in resp_json.get("errors", [])
        ):
            # Find the existing PR
            with requests.get(
                "https://api.github.com/repos/python/mypy/pulls",
                params={"state": "open", "head": f"{fork_owner}:{branch_name}", "base": "master"},
                headers=get_github_api_headers(),
            ) as response:
                response.raise_for_status()
                resp_json = response.json()
                assert len(resp_json) >= 1
                pr_number = resp_json[0]["number"]
            # Update the PR's title and body
            with requests.patch(
                f"https://api.github.com/repos/python/mypy/pulls/{pr_number}",
                json={"title": title, "body": body},
                headers=get_github_api_headers(),
            ) as response:
                response.raise_for_status()
            return
        response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--commit",
        default=None,
        help="Typeshed commit (default to latest main if using a repository clone)",
    )
    parser.add_argument(
        "--typeshed-dir",
        default=None,
        help="Location of typeshed (default to a temporary repository clone)",
    )
    parser.add_argument(
        "--make-pr",
        action="store_true",
        help="Whether to make a PR with the changes (default to no)",
    )
    args = parser.parse_args()

    check_state()

    if args.make_pr:
        if os.environ.get("GITHUB_TOKEN") is None:
            raise ValueError("GITHUB_TOKEN environment variable must be set")

    branch_name = "mypybot/sync-typeshed"
    subprocess.run(["git", "checkout", "-B", branch_name, "origin/master"], check=True)

    if not args.typeshed_dir:
        # Clone typeshed repo if no directory given.
        with tempfile.TemporaryDirectory() as tempdir:
            print(f"Cloning typeshed in {tempdir}...")
            subprocess.run(
                ["git", "clone", "https://github.com/python/typeshed.git"], check=True, cwd=tempdir
            )
            repo = os.path.join(tempdir, "typeshed")
            commit = update_typeshed(repo, args.commit)
    else:
        commit = update_typeshed(args.typeshed_dir, args.commit)

    assert commit

    # Create a commit
    message = textwrap.dedent(
        f"""\
        Sync typeshed

        Source commit:
        https://github.com/python/typeshed/commit/{commit}
        """
    )
    subprocess.run(["git", "add", "--all", os.path.join("mypy", "typeshed")], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)
    print("Created typeshed sync commit.")

    commits_to_cherry_pick = [
        "874afd970",  # LiteralString reverts
        "3a240111e",  # sum reverts
        "f968d6ce0",  # ctypes reverts
    ]
    for commit in commits_to_cherry_pick:
        subprocess.run(["git", "cherry-pick", commit], check=True)
        print(f"Cherry-picked {commit}.")

    if args.make_pr:
        subprocess.run(["git", "push", "--force", "origin", branch_name], check=True)
        print("Pushed commit.")

        warning = "Note that you will need to close and re-open the PR in order to trigger CI."

        create_or_update_pull_request(
            title="Sync typeshed", body=message + "\n" + warning, branch_name=branch_name
        )
        print("Created PR.")


if __name__ == "__main__":
    main()
