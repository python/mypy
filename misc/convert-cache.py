#!/usr/bin/env python3
"""Script for converting between cache formats.

We support a filesystem tree based cache and a sqlite based cache.
See mypy/metastore.py for details.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from mypy.metastore import FilesystemMetadataStore, SqliteMetadataStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--to-sqlite', action='store_true', default=False,
                        help='Convert to a sqlite cache (default: convert from)')
    parser.add_argument('--output_dir', action='store', default=None,
                        help="Output cache location (default: same as input)")
    parser.add_argument('input_dir',
                        help="Input directory for the cache")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir
    if args.to_sqlite:
        input, output = FilesystemMetadataStore(input_dir), SqliteMetadataStore(output_dir)
    else:
        input, output = SqliteMetadataStore(input_dir), FilesystemMetadataStore(output_dir)

    for s in input.list_all():
        if s.endswith('.json'):
            assert output.write(s, input.read(s), input.getmtime(s)), "Failed to write cache file!"
    output.commit()


if __name__ == '__main__':
    main()
