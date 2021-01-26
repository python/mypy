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


def check_state() -> None:
    if not os.path.isfile('README.md'):
        sys.exit('error: The current working directory must be the mypy repository root')
    out = subprocess.check_output(['git', 'status', '-s', os.path.join('mypy', 'typeshed')])
    if out:
        # If there are local changes under mypy/typeshed, they would be lost.
        sys.exit('error: Output of "git status -s mypy/typeshed" must be empty')


def update_typeshed(typeshed_dir: str) -> None:
    assert os.path.isdir(os.path.join(typeshed_dir, 'stdlib'))
    assert os.path.isdir(os.path.join(typeshed_dir, 'stubs'))
    stub_dir = os.path.join('mypy', 'typeshed', 'stdlib')
    # Remove existing stubs.
    shutil.rmtree(stub_dir)
    # Copy new stdlib stubs.
    shutil.copytree(os.path.join(typeshed_dir, 'stdlib'), stub_dir)


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

    # TODO: Clone typeshed repo if no directory given
    assert args.typeshed_dir
    update_typeshed(args.typeshed_dir)

    commit = args.commit
    # TODO: If cloning typeshd repo, use master commit
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
