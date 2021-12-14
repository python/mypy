#!/usr/bin/env python3
"""Script for applying a cache diff.

With some infrastructure, this can allow for distributing small cache diffs to users in
many cases instead of full cache artifacts.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mypy.metastore import MetadataStore, FilesystemMetadataStore, SqliteMetadataStore


def make_cache(input_dir: str, sqlite: bool) -> MetadataStore:
    if sqlite:
        return SqliteMetadataStore(input_dir)
    else:
        return FilesystemMetadataStore(input_dir)


def apply_diff(cache_dir: str, diff_file: str, sqlite: bool = False) -> None:
    cache = make_cache(cache_dir, sqlite)
    with open(diff_file, "r") as f:
        diff = json.load(f)

    old_deps = json.loads(cache.read("@deps.meta.json"))

    for file, data in diff.items():
        if data is None:
            cache.remove(file)
        else:
            cache.write(file, data)
            if file.endswith('.meta.json') and "@deps" not in file:
                meta = json.loads(data)
                old_deps["snapshot"][meta["id"]] = meta["hash"]

    cache.write("@deps.meta.json", json.dumps(old_deps))

    cache.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sqlite', action='store_true', default=False,
                        help='Use a sqlite cache')
    parser.add_argument('cache_dir',
                        help="Directory for the cache")
    parser.add_argument('diff',
                        help="Cache diff file")
    args = parser.parse_args()

    apply_diff(args.cache_dir, args.diff, args.sqlite)


if __name__ == '__main__':
    main()
