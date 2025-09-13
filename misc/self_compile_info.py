"""Print list of files compiled when compiling self (mypy and mypyc)."""

import argparse
import sys
from typing import Any

import setuptools

import mypyc.build


class FakeExtension:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


def fake_mypycify(args: list[str], **kwargs: Any) -> list[FakeExtension]:
    for target in sorted(args):
        if not target.startswith("-"):
            print(target)
    return [FakeExtension()]


def fake_setup(*args: Any, **kwargs: Any) -> Any:
    pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print list of files compiled when compiling self. Run in repository root."
    )
    parser.parse_args()

    # Prepare fake state for running setup.py.
    mypyc.build.mypycify = fake_mypycify  # type: ignore[assignment]
    setuptools.Extension = FakeExtension  # type: ignore[misc, assignment]
    setuptools.setup = fake_setup
    sys.argv = [sys.argv[0], "--use-mypyc"]

    # Run setup.py at the root of the repository.
    import setup  # noqa: F401


if __name__ == "__main__":
    main()
