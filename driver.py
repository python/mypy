#!/usr/bin/env python
"""Mypy compiler and runner.

Type check and program, compile it to Python or C and run it. Note that you
must use a translated mypy translator to run this program.

Note that the C back end is early in development and has a very limited feature
set.
"""

import os
import os.path
import shutil
import subprocess
import sys
import tempfile

from mypy import build
from mypy.errors import CompileError
from typing import List, Tuple


# Fallback options
target = build.TYPE_CHECK
build_flags = [] # type: List[str]
interpreter = 'python'


def main() -> None:
    path, module, args = process_options(sys.argv[1:])
    try:
        if target == build.TYPE_CHECK:
            type_check_only(path, module, args)
        elif target == build.C:
            compile_to_c(path, module, args)
        else:
            raise RuntimeError('unsupported target %d' % target)
    except CompileError as e:
        for m in e.messages:
            print(m)
        sys.exit(1)


def type_check_only(path: str, module: str, args: List[str]) -> None:
    # Type check the program and dependencies and translate to Python.
    build.build(path,
                module=module,
                target=build.TYPE_CHECK,
                flags=build_flags)

    if build.COMPILE_ONLY not in build_flags:
        # Run the translated program.
        if module:
            opts = ['-m', module]
        else:
            opts = [path]
        status = subprocess.call([interpreter] + opts + args)
        sys.exit(status)


def compile_to_c(path: str, module: str, args: List[str]) -> None:
    assert not module # Not supported yet
    assert not args   # Not supported yet
    
    # Compile the program to C (also generate binary by default).
    result = build.build(path, target=build.C, flags=build_flags)

    if build.COMPILE_ONLY not in build_flags:
        # Run the compiled program.
        # TODO command line arguments
        status = subprocess.call([result.binary_path])
        sys.exit(status)


def process_options(args: List[str]) -> Tuple[str, str, List[str]]:
    if sys.executable:
        global interpreter
        interpreter = sys.executable
    while args and args[0].startswith('-'):
        if args[0] == '--verbose':
            build_flags.append(build.VERBOSE)
            args = args[1:]
        elif args[0] == '--py2' and args[1:]:
            # Generate Python 2 (but this is very incomplete).
            build_flags.append(build.PYTHON2)
            interpreter = args[1]
            args = args[2:]
        elif args[0] == '-c':
            global target
            target = build.C
            args = args[1:]
        elif args[0] == '-S':
            build_flags.append(build.COMPILE_ONLY)
            args = args[1:]
        elif args[0] == '-m' and args[1:]:
            build_flags.append(build.MODULE)
            return None, args[1], args[2:]
        else:
            usage('Invalid option {}'.format(args[0]))
    
    if not args:
        usage()
    
    return args[0], None, args[1:]


def usage(msg: str = None) -> None:
    if msg:
        sys.stderr.write('%s\n' % msg)
    sys.stderr.write(
'''Usage: mypy [options] [-m mod | file] [args]

Options:
  -c          compile to native code (EXPERIMENTAL)
  -m mod      run module as a script (terminates option list)
  -S          compile only to C; do not generate a binary or run the program
  --verbose   more verbose messages
  
Environment variables:
  MYPYPATH    additional module search path
  CC          the C compiler (used with -c)
  CFLAGS      command line options to the C compiler (used with -c)
''')
    sys.exit(2)


def fail(msg: str) -> None:
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)


if __name__ == '__main__':
    main()
