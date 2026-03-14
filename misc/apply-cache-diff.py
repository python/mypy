#!/usr/bin/env python3
"""Script for applying a cache diff.

With some infrastructure, this can allow for distributing small cache diffs to users in
many cases instead of full cache artifacts.

Use diff-cache.py to generate a cache diff.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from librt import base64
from librt.internal import ReadBuffer

from mypy.cache import CacheMeta
from mypy.metastore import FilesystemMetadataStore, MetadataStore, SqliteMetadataStore
from mypy.util import json_dumps, json_loads


def make_cache(input_dir: str, sqlite: bool) -> MetadataStore:
    if sqlite:
        return SqliteMetadataStore(input_dir)
    else:
        return FilesystemMetadataStore(input_dir)


def apply_diff(cache_dir: str, diff_file: str, sqlite: bool = False) -> None:
    cache = make_cache(cache_dir, sqlite)
    with open(diff_file, "rb") as f:
        diff = json_loads(f.read())

    old_deps = json_loads(cache.read("@deps.meta.json"))

    for file, data in diff.items():
        if data is None:
            cache.remove(file)
        else:
            if file.endswith(".ff"):
                data_bytes = base64.b64decode(data)
            else:
                data_bytes = data.encode() if isinstance(data, str) else data
            cache.write(file, data_bytes)
            if file.endswith(".meta.ff") and "@deps" not in file:
                buf = ReadBuffer(data_bytes[2:])
                meta = CacheMeta.read(buf, data_file="")
                assert meta is not None
                old_deps["snapshot"][meta.id] = meta.hash
            elif file.endswith(".meta.json") and "@deps" not in file:
                meta_dict = json_loads(data_bytes)
                old_deps["snapshot"][meta_dict["id"]] = meta_dict["hash"]

    cache.write("@deps.meta.json", json_dumps(old_deps))

    cache.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", action="store_true", default=False, help="Use a sqlite cache")
    parser.add_argument("cache_dir", help="Directory for the cache")
    parser.add_argument("diff", help="Cache diff file")
    args = parser.parse_args()

    apply_diff(args.cache_dir, args.diff, args.sqlite)


if __name__ == "__main__":
    main()
