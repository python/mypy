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

MYPY = False
if MYPY:
    from typing import List

if __name__ == '__main__':
    # HACK: We don't want to pick up mypy.types as the top-level types
    #       module. This could happen if this file is run as a script.
    #       This workaround fixes it.
    old_sys_path = sys.path
    sys.path = sys.path[1:]
    import types  # noqa
    sys.path = old_sys_path


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
    excludes = set([stdlib_zip, stdlib, stdlib_ext])

    # Drop the first entry of sys.path
    # - If pyinfo.py is executed as a script (in a subprocess), this is the directory
    #   containing pyinfo.py
    # - Otherwise, if mypy launched via console script, this is the directory of the script
    # - Otherwise, if mypy launched via python -m mypy, this is the current directory
    # In all cases, this is safe to drop
    # Note that mypy adds the cwd to SearchPaths.python_path, so we still find things on the
    # cwd consistently (the return value here sets SearchPaths.package_path)
    abs_sys_path = (os.path.abspath(p) for p in sys.path[1:])
    return [p for p in abs_sys_path if p not in excludes]


if __name__ == '__main__':
    if sys.argv[-1] == 'getsearchdirs':
        print(repr(getsearchdirs()))
    else:
        print("ERROR: incorrect argument to pyinfo.py.", file=sys.stderr)
        sys.exit(1)
