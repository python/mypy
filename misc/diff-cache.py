#!/usr/bin/env python3
"""Produce a diff between mypy caches.

With some infrastructure, this can allow for distributing small cache diffs to users in
many cases instead of full cache artifacts.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mypy.metastore import FilesystemMetadataStore, MetadataStore, SqliteMetadataStore
from mypy.util import json_dumps, json_loads


def make_cache(input_dir: str, sqlite: bool) -> MetadataStore:
    if sqlite:
        return SqliteMetadataStore(input_dir)
    else:
        return FilesystemMetadataStore(input_dir)


def merge_deps(all: dict[str, set[str]], new: dict[str, set[str]]) -> None:
    for k, v in new.items():
        all.setdefault(k, set()).update(v)


def load(cache: MetadataStore, s: str) -> Any:
    data = cache.read(s)
    obj = json_loads(data)
    if s.endswith(".meta.json"):
        # For meta files, zero out the mtimes and sort the
        # dependencies to avoid spurious conflicts
        obj["mtime"] = 0
        obj["data_mtime"] = 0
        if "dependencies" in obj:
            all_deps = obj["dependencies"] + obj["suppressed"]
            num_deps = len(obj["dependencies"])
            thing = list(zip(all_deps, obj["dep_prios"], obj["dep_lines"]))

            def unzip(x: Any) -> Any:
                return zip(*x) if x else ((), (), ())

            obj["dependencies"], prios1, lines1 = unzip(sorted(thing[:num_deps]))
            obj["suppressed"], prios2, lines2 = unzip(sorted(thing[num_deps:]))
            obj["dep_prios"] = prios1 + prios2
            obj["dep_lines"] = lines1 + lines2
    if s.endswith(".deps.json"):
        # For deps files, sort the deps to avoid spurious mismatches
        for v in obj.values():
            v.sort()
    return obj


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", default=False, help="Increase verbosity")
    parser.add_argument("--sqlite", action="store_true", default=False, help="Use a sqlite cache")
    parser.add_argument("input_dir1", help="Input directory for the cache")
    parser.add_argument("input_dir2", help="Input directory for the cache")
    parser.add_argument("output", help="Output file")
    args = parser.parse_args()

    cache1 = make_cache(args.input_dir1, args.sqlite)
    cache2 = make_cache(args.input_dir2, args.sqlite)

    type_misses: dict[str, int] = defaultdict(int)
    type_hits: dict[str, int] = defaultdict(int)

    updates: dict[str, bytes | None] = {}

    deps1: dict[str, set[str]] = {}
    deps2: dict[str, set[str]] = {}

    misses = hits = 0
    cache1_all = list(cache1.list_all())
    for s in cache1_all:
        obj1 = load(cache1, s)
        try:
            obj2 = load(cache2, s)
        except FileNotFoundError:
            obj2 = None

        typ = s.split(".")[-2]
        if obj1 != obj2:
            misses += 1
            type_misses[typ] += 1

            # Collect the dependencies instead of including them directly in the diff
            # so we can produce a much smaller direct diff of them.
            if ".deps." not in s:
                if obj2 is not None:
                    updates[s] = json_dumps(obj2)
                else:
                    updates[s] = None
            elif obj2:
                merge_deps(deps1, obj1)
                merge_deps(deps2, obj2)
        else:
            hits += 1
            type_hits[typ] += 1

    cache1_all_set = set(cache1_all)
    for s in cache2.list_all():
        if s not in cache1_all_set:
            updates[s] = cache2.read(s)

    # Compute what deps have been added and merge them all into the
    # @root deps file.
    new_deps = {k: deps1.get(k, set()) - deps2.get(k, set()) for k in deps2}
    new_deps = {k: v for k, v in new_deps.items() if v}
    try:
        root_deps = load(cache1, "@root.deps.json")
    except FileNotFoundError:
        root_deps = {}
    merge_deps(new_deps, root_deps)

    new_deps_json = {k: list(v) for k, v in new_deps.items() if v}
    updates["@root.deps.json"] = json_dumps(new_deps_json)

    # Drop updates to deps.meta.json for size reasons. The diff
    # applier will manually fix it up.
    updates.pop("./@deps.meta.json", None)
    updates.pop("@deps.meta.json", None)

    ###

    print("Generated incremental cache:", hits, "hits,", misses, "misses")
    if args.verbose:
        print("hits", type_hits)
        print("misses", type_misses)

    with open(args.output, "wb") as f:
        f.write(json_dumps(updates))


if __name__ == "__main__":
    main()
