"""Mypy type checker command line tool."""

import argparse
import fnmatch
import os
import re
import sys
import time

from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from mypy import build
from mypy import defaults
from mypy import util
from mypy.build import BuildSource, BuildResult, PYTHON_EXTENSIONS
from mypy.errors import CompileError
from mypy.options import Options, BuildType, process_options, parse_version
from mypy.report import reporter_classes


def main(script_path: str, args: List[str] = None) -> None:
    """Main entry point to the type checker.

    Args:
        script_path: Path to the 'mypy' script (used for finding data files).
        args: Custom command-line arguments.  If not given, sys.argv[1:] will
        be used.
    """
    t0 = time.time()
    if script_path:
        bin_dir = find_bin_directory(script_path)
    else:
        bin_dir = None
    sys.setrecursionlimit(2 ** 14)
    if args is None:
        args = sys.argv[1:]
    sources, options = process_options(args)
    serious = False
    try:
        res = type_check_only(sources, bin_dir, options)
        a = res.errors
    except CompileError as e:
        a = e.messages
        if not e.use_stdout:
            serious = True
    if options.junit_xml:
        t1 = time.time()
        util.write_junit_xml(t1 - t0, serious, a, options.junit_xml)
    if a:
        f = sys.stderr if serious else sys.stdout
        try:
            for m in a:
                f.write(m + '\n')
        except BrokenPipeError:
            pass
        sys.exit(1)


def find_bin_directory(script_path: str) -> str:
    """Find the directory that contains this script.

    This is used by build to find stubs and other data files.
    """
    # Follow up to 5 symbolic links (cap to avoid cycles).
    for i in range(5):
        if os.path.islink(script_path):
            script_path = readlinkabs(script_path)
        else:
            break
    return os.path.dirname(script_path)


def readlinkabs(link: str) -> str:
    """Return an absolute path to symbolic link destination."""
    # Adapted from code by Greg Smith.
    assert os.path.islink(link)
    path = os.readlink(link)
    if os.path.isabs(path):
        return path
    return os.path.join(os.path.dirname(link), path)


def type_check_only(sources: List[BuildSource], bin_dir: str, options: Options) -> BuildResult:
    # Type-check the program and dependencies and translate to Python.
    return build.build(sources=sources,
                       bin_dir=bin_dir,
                       options=options)
