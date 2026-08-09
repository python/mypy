"""Cherry-pick a commit from typeshed.

Usage:

  python3 misc/cherry-pick-typeshed.py --typeshed-dir dir hash
"""

from __future__ import annotations

import argparse
import os.path
import re
import subprocess
import sys
import tempfile


def parse_commit_title(diff: str) -> str:
    m = re.search("\n    ([^ ].*)", diff)
    assert m is not None, "Could not parse diff"
    return m.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--typeshed-dir", help="location of typeshed", metavar="dir", required=True
    )
    parser.add_argument("commit", help="typeshed commit hash to cherry-pick")
    args = parser.parse_args()
    typeshed_dir = args.typeshed_dir
    commit = args.commit

    if not os.path.isdir(typeshed_dir):
        sys.exit(f"error: {typeshed_dir} does not exist")
    if not re.match("[0-9a-fA-F]+$", commit):
        sys.exit(f"error: Invalid commit {commit!r}")

    if not os.path.exists("mypy") or not os.path.exists("mypyc"):
        sys.exit("error: This script must be run at the mypy repository root directory")

    with tempfile.TemporaryDirectory() as d:
        diff_file = os.path.join(d, "diff")
        out = subprocess.run(
            ["git", "show", commit], capture_output=True, text=True, check=True, cwd=typeshed_dir
        )
        with open(diff_file, "w") as f:
            f.write(out.stdout)
        subprocess.run(
            [
                "git",
                "apply",
                "--index",
                "--directory=mypy/typeshed",
                "--exclude=**/tests/**",
                "--exclude=**/test_cases/**",
                diff_file,
            ],
            check=True,
        )

        title = parse_commit_title(out.stdout)
        subprocess.run(["git", "commit", "-m", f"Typeshed cherry-pick: {title}"], check=True)

    print()
    print(f"Cherry-picked commit {commit} from {typeshed_dir}")


if __name__ == "__main__":
    main()
