#!/usr/bin/env python3
"""
Parse source files and print the abstract syntax trees.
"""

from __future__ import annotations

import argparse
import sys

from mypy import defaults
from mypy.errors import CompileError, Errors
from mypy.options import Options
from mypy.parse import parse


def dump(fname: str, python_version: tuple[int, int], quiet: bool = False) -> None:
    options = Options()
    options.python_version = python_version
    with open(fname, "rb") as f:
        s = f.read()
        tree = parse(s, fname, None, errors=Errors(options), options=options)
        if not quiet:
            print(tree)


def main() -> None:
    # Parse a file and dump the AST (or display errors).
    parser = argparse.ArgumentParser(
        description="Parse source files and print the abstract syntax tree (AST)."
    )
    parser.add_argument("--quiet", action="store_true", help="do not print AST")
    parser.add_argument("FILE", nargs="*", help="files to parse")
    args = parser.parse_args()

    status = 0
    for fname in args.FILE:
        try:
            dump(fname, defaults.PYTHON3_VERSION, args.quiet)
        except CompileError as e:
            for msg in e.messages:
                sys.stderr.write("%s\n" % msg)
            status = 1
    sys.exit(status)


if __name__ == "__main__":
    main()
