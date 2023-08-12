#!/usr/bin/env python3
"""Script for converting between cache formats.

We support a filesystem tree based cache and a sqlite based cache.
See mypy/metastore.py for details.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse

from mypy.metastore import FilesystemMetadataStore, MetadataStore, SqliteMetadataStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--to-sqlite",
        action="store_true",
        default=False,
        help="Convert to a sqlite cache (default: convert from)",
    )
    parser.add_argument(
        "--output_dir",
        action="store",
        default=None,
        help="Output cache location (default: same as input)",
    )
    parser.add_argument("input_dir", help="Input directory for the cache")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir
    assert os.path.isdir(output_dir), f"{output_dir} is not a directory"
    if args.to_sqlite:
        input: MetadataStore = FilesystemMetadataStore(input_dir)
        output: MetadataStore = SqliteMetadataStore(output_dir)
    else:
        fnam = os.path.join(input_dir, "cache.db")
        msg = f"{fnam} does not exist"
        if not re.match(r"[0-9]+\.[0-9]+$", os.path.basename(input_dir)):
            msg += f" (are you missing Python version at the end, e.g. {input_dir}/3.11)"
        assert os.path.isfile(fnam), msg
        input, output = SqliteMetadataStore(input_dir), FilesystemMetadataStore(output_dir)

    for s in input.list_all():
        if s.endswith(".json"):
            assert output.write(
                s, input.read(s), input.getmtime(s)
            ), f"Failed to write cache file {s}!"
    output.commit()


if __name__ == "__main__":
    main()
