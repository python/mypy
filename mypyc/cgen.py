"""Generate mypyc C code and machine-readable build metadata, without setuptools.

Usage:

    $ python -m mypyc cgen [--target-dir DIR] [--output-file FILE] SOURCE...

This runs mypyc's frontend and C generation and writes all generated C
files (group sources, runtime library, shims) into --target-dir. It then
emits a JSON description of the extensions to build, either to
--output-file or to stdout. The JSON is meant to be consumed by a build
system (meson, cmake, ...) which performs the actual C compilation itself.

The JSON schema is versioned and currently looks like:

    {
      "schema_version": 1,
      "target_dir": "<absolute path>",
      "extensions": [
        {
          "module": "...",        # full dotted extension module name
          "out_path": "...",      # built file path, relative to the
                                  # installation root (e.g. site-packages),
                                  # including the platform extension suffix
          "sources": [...],       # .c files to compile, relative to target_dir
          "include_dirs": [...],  # absolute paths
          "depends": [...],       # headers to trigger rebuilds, relative to target_dir
          "cflags": [...],        # required flags (warnings, feature macros); no
                                  # optimization or debug levels — those are up
                                  # to the caller's build system
          "link_args": [...]      # may be empty; the caller is always responsible
                                  # for the platform's standard extension linking,
                                  # including the Python.h include directory
        },
        ...
      ]
    }
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os.path

from mypyc.build import (
    ExtensionSpec,
    GeneratedC,
    extension_build_specs,
    generate_c_sources,
    write_file,
)
from mypyc.options import CompilerOptions

SCHEMA_VERSION = 1


@dataclasses.dataclass(frozen=True)
class CgenArgs:
    sources: list[str]
    target_dir: str = "build/mypyc"
    output_file: str | None = None
    multi_file: bool = False
    separate: bool = False


@dataclasses.dataclass(frozen=True)
class ExtensionInfo:
    """One extension to build, as described in the module docstring's JSON schema."""

    module: str
    out_path: str
    sources: list[str]
    include_dirs: list[str]
    depends: list[str]
    cflags: list[str]
    link_args: list[str]


@dataclasses.dataclass(frozen=True)
class BuildInfo:
    schema_version: int
    target_dir: str
    extensions: list[ExtensionInfo]


def build_info(result: GeneratedC, specs: list[ExtensionSpec]) -> BuildInfo:
    target_dir = os.path.abspath(result.target_dir)
    return BuildInfo(
        schema_version=SCHEMA_VERSION,
        target_dir=target_dir,
        extensions=[
            ExtensionInfo(
                module=spec.module,
                out_path=spec.out_path,
                sources=[os.path.relpath(source, target_dir) for source in spec.sources],
                include_dirs=spec.include_dirs,
                depends=[os.path.relpath(dep, target_dir) for dep in spec.depends],
                cflags=spec.cflags,
                link_args=spec.link_args,
            )
            for spec in specs
        ],
    )


def parse_args(argv: list[str] | None = None) -> CgenArgs:
    parser = argparse.ArgumentParser(
        prog="mypyc cgen",
        description="Generate mypyc C code and JSON build metadata for external build systems",
    )
    parser.add_argument("sources", nargs="+", metavar="SOURCE", help="files to compile")
    parser.add_argument(
        "--target-dir",
        default="build/mypyc",
        help="directory to write generated C files to (default: build/mypyc)",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="write the JSON build info to this file instead of stdout",
    )
    parser.add_argument(
        "--multi-file", action="store_true", help="compile each module into its own C source file"
    )
    parser.add_argument(
        "--separate", action="store_true", help="place each module in its own extension module"
    )
    args = parser.parse_args(argv)
    return CgenArgs(
        sources=args.sources,
        target_dir=args.target_dir,
        output_file=args.output_file,
        multi_file=args.multi_file,
        separate=args.separate,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    options = CompilerOptions(
        target_dir=args.target_dir, multi_file=args.multi_file, separate=args.separate
    )
    result = generate_c_sources(args.sources, options)
    # The emitted cflags intentionally exclude optimization and debug levels;
    # the caller's build system controls those.
    specs = extension_build_specs(result)
    info = build_info(result, specs)

    text = json.dumps(dataclasses.asdict(info), indent=2) + "\n"
    if args.output_file:
        write_file(args.output_file, text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
