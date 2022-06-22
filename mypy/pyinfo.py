from __future__ import print_function
"""Utilities to find the site and prefix information of a Python executable, which may be Python 2.

This file MUST remain compatible with Python 2. Since we cannot make any assumptions about the
Python being executed, this module should not use *any* dependencies outside of the standard
library found in Python 2. This file is run each mypy run, so it should be kept as fast as
possible.
"""
import os
import sys
import sysconfig

if __name__ == '__main__':
    sys.path = sys.path[1:]  # we don't want to pick up mypy.types

MYPY = False
if MYPY:
    from typing import List


def getsearchdirs():
    # type: () -> List[str]
    # Do not include things from the standard library
    # because those should come from typeshed.
    stdlib_zip = os.path.join(
        sys.base_exec_prefix,
        getattr(sys, "platlibdir", "lib"),
        "python{}{}.zip".format(sys.version_info.major, sys.version_info.minor)
    )
    stdlib = sysconfig.get_path("stdlib")
    stdlib_ext = os.path.join(stdlib, "lib-dynload")
    cwd = os.path.abspath(os.getcwd())
    excludes = set([cwd, stdlib_zip, stdlib, stdlib_ext])

    abs_sys_path = (os.path.abspath(p) for p in sys.path)
    return [p for p in abs_sys_path if p not in excludes]


if __name__ == '__main__':
    if sys.argv[-1] == 'getsearchdirs':
        print(repr(getsearchdirs()))
    else:
        print("ERROR: incorrect argument to pyinfo.py.", file=sys.stderr)
        sys.exit(1)
