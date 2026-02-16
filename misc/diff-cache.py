#!/usr/bin/env python3
"""Produce a diff between mypy caches.

With some infrastructure, this can allow for distributing small cache diffs to users in
many cases instead of full cache artifacts.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from collections import defaultdict
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from librt.internal import ReadBuffer, WriteBuffer

from mypy.cache import CacheMeta
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


def normalize_meta(meta: CacheMeta) -> None:
    """Normalize a CacheMeta instance to avoid spurious diffs.

    Zero out mtimes and sort dependencies deterministically.
    """
    meta.mtime = 0
    meta.data_mtime = 0
    all_deps = list(zip(meta.dependencies + meta.suppressed, meta.dep_prios, meta.dep_lines))
    num_deps = len(meta.dependencies)
    sorted_deps = sorted(all_deps[:num_deps])
    sorted_supp = sorted(all_deps[num_deps:])
    if sorted_deps:
        deps, prios1, lines1 = zip(*sorted_deps)
        meta.dependencies = list(deps)
        prios1 = list(prios1)
        lines1 = list(lines1)
    else:
        meta.dependencies = []
        prios1 = []
        lines1 = []
    if sorted_supp:
        supp, prios2, lines2 = zip(*sorted_supp)
        meta.suppressed = list(supp)
        prios2 = list(prios2)
        lines2 = list(lines2)
    else:
        meta.suppressed = []
        prios2 = []
        lines2 = []
    meta.dep_prios = prios1 + prios2
    meta.dep_lines = lines1 + lines2


def serialize_meta_ff(meta: CacheMeta, version_prefix: bytes) -> bytes:
    """Serialize a CacheMeta instance back to fixed format binary."""
    buf = WriteBuffer()
    meta.write(buf)
    return version_prefix + buf.getvalue()


def normalize_json_meta(obj: dict[str, Any]) -> None:
    """Normalize a JSON meta dict to avoid spurious diffs.

    Zero out mtimes and sort dependencies deterministically.
    """
    obj["mtime"] = 0
    obj["data_mtime"] = 0
    if "dependencies" in obj:
        all_deps: list[str] = obj["dependencies"] + obj["suppressed"]
        num_deps = len(obj["dependencies"])
        thing = list(zip(all_deps, obj["dep_prios"], obj["dep_lines"]))
        sorted_deps = sorted(thing[:num_deps])
        sorted_supp = sorted(thing[num_deps:])
        if sorted_deps:
            deps, prios1, lines1 = zip(*sorted_deps)
        else:
            deps, prios1, lines1 = (), (), ()
        if sorted_supp:
            supp, prios2, lines2 = zip(*sorted_supp)
        else:
            supp, prios2, lines2 = (), (), ()
        obj["dependencies"] = deps
        obj["suppressed"] = supp
        obj["dep_prios"] = prios1 + prios2
        obj["dep_lines"] = lines1 + lines2


def load(cache: MetadataStore, s: str) -> Any:
    """Load and normalize a cache entry.

    Returns:
      - For .meta.ff: normalized binary bytes (with version prefix)
      - For .data.ff: raw binary bytes
      - For .meta.json/.data.json/.deps.json: parsed and normalized dict/list
    """
    data = cache.read(s)
    if s.endswith(".meta.ff"):
        version_prefix = data[:2]
        buf = ReadBuffer(data[2:])
        meta = CacheMeta.read(buf, data_file="")
        if meta is None:
            # Can't deserialize (e.g. different mypy version). Fall back to
            # raw bytes -- we lose mtime normalization but the diff stays correct.
            return data
        normalize_meta(meta)
        return serialize_meta_ff(meta, version_prefix)
    if s.endswith(".data.ff"):
        return data
    obj = json_loads(data)
    if s.endswith(".meta.json"):
        normalize_json_meta(obj)
    if s.endswith(".deps.json"):
        # For deps files, sort the deps to avoid spurious mismatches
        for v in obj.values():
            v.sort()
    return obj


def encode_for_diff(s: str, obj: object) -> str:
    """Encode a cache entry value for inclusion in the JSON diff.

    Fixed format binary entries are base64-encoded, JSON entries are
    re-serialized as JSON strings.
    """
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode()
    return json_dumps(obj).decode()


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

    updates: dict[str, str | None] = {}

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
                    updates[s] = encode_for_diff(s, obj2)
                else:
                    updates[s] = None
            elif obj2:
                # This is a deps file, with json data
                assert ".deps." in s
                merge_deps(deps1, obj1)
                merge_deps(deps2, obj2)
        else:
            hits += 1
            type_hits[typ] += 1

    cache1_all_set = set(cache1_all)
    for s in cache2.list_all():
        if s not in cache1_all_set:
            raw = cache2.read(s)
            if s.endswith(".ff"):
                updates[s] = base64.b64encode(raw).decode()
            else:
                updates[s] = raw.decode()

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
    updates["@root.deps.json"] = json_dumps(new_deps_json).decode()

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
