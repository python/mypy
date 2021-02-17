"""Sync stdlib stubs from typeshed.

Usage:

  python3 misc/sync-typeshed.py [--commit hash] [--typeshed-dir dir]

By default, sync to the latest typeshed commit.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from typing import Optional


def check_state() -> None:
    if not os.path.isfile('README.md'):
        sys.exit('error: The current working directory must be the mypy repository root')
    out = subprocess.check_output(['git', 'status', '-s', os.path.join('mypy', 'typeshed')])
    if out:
        # If there are local changes under mypy/typeshed, they would be lost.
        sys.exit('error: Output of "git status -s mypy/typeshed" must be empty')


def update_typeshed(typeshed_dir: str, commit: Optional[str]) -> str:
    """Update contents of local typeshed copy.

    Return the normalized typeshed commit hash.
    """
    assert os.path.isdir(os.path.join(typeshed_dir, 'stdlib'))
    assert os.path.isdir(os.path.join(typeshed_dir, 'stubs'))
    if commit:
        subprocess.run(['git', 'checkout', commit], check=True, cwd=typeshed_dir)
    commit = git_head_commit(typeshed_dir)
    stub_dir = os.path.join('mypy', 'typeshed', 'stdlib')
    # Remove existing stubs.
    shutil.rmtree(stub_dir)
    # Copy new stdlib stubs.
    shutil.copytree(os.path.join(typeshed_dir, 'stdlib'), stub_dir)
    return commit


def git_head_commit(repo: str) -> str:
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo).decode('ascii')
    return commit.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--commit", default=None,
        help="Typeshed commit (default to latest master if using a repository clone)"
    )
    parser.add_argument(
        "--typeshed-dir", default=None,
        help="Location of typeshed (default to a temporary repository clone)"
    )
    args = parser.parse_args()
    check_state()
    print('Update contents of mypy/typeshed/stdlib from typeshed? [yN] ', end='')
    answer = input()
    if answer.lower() != 'y':
        sys.exit('Aborting')

    if not args.typeshed_dir:
        # Clone typeshed repo if no directory given.
        with tempfile.TemporaryDirectory() as tempdir:
            print('Cloning typeshed in {}...'.format(tempdir))
            subprocess.run(['git', 'clone', 'https://github.com/python/typeshed.git'],
                           check=True, cwd=tempdir)
            repo = os.path.join(tempdir, 'typeshed')
            commit = update_typeshed(repo, args.commit)
    else:
        commit = update_typeshed(args.typeshed_dir, args.commit)

    assert commit

    # Create a commit
    message = textwrap.dedent("""\
        Sync typeshed

        Source commit:
        https://github.com/python/typeshed/commit/{commit}
        """.format(commit=commit))
    subprocess.run(['git', 'add', '--all', os.path.join('mypy', 'typeshed')], check=True)
    subprocess.run(['git', 'commit', '-m', message], check=True)
    print('Created typeshed sync commit.')


if __name__ == '__main__':
    main()
