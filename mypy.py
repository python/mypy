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

import build
from errors import CompileError
from pythongen import PythonGenerator


# Fallback options
verbose = False
target = build.PYTHON
build_flags = <str> []
interpreter = 'python'


void main():
    path, args = process_options()

    try:
        mainfile = open(path)
        program_text = mainfile.read()
        mainfile.close()
    except IOError as ioerr:
        fail("mypy: can't read file '{}': {}".format(path,
                                                     ioerr.strerror))
    
    try:
        if target == build.PYTHON:
            compile_to_python(program_text, path, args)
        elif target == build.C:
            compile_to_c(program_text, path)
        else:
            raise RuntimeError('unsupported target %d' % target)
    except CompileError as e:
        for m in e.messages:
            print(m)
        sys.exit(1)


void compile_to_python(str program_text, str path, str[] args):
    outputdir = os.path.join(os.path.dirname(path), '__mycache__')
    tempdir = False
    if not os.path.isdir(outputdir):
        try:
            os.mkdir(outputdir)
        except OSError:
            # Could not create a directory under program directory; must
            # fall back to a temp directory. It will be removed later.
            outputdir = tempfile.mkdtemp()
            tempdir = True

    try:
        # Type check the program and dependencies and translate to Python.
        build.build(program_text, path,
                    target=build.PYTHON,
                    output_dir=outputdir,
                    flags=build_flags)

        if build.COMPILE_ONLY not in build_flags:
            # Run the translated program.
            status = subprocess.call(
                [interpreter,
                 '{}/{}'.format(outputdir,os.path.basename(path))] +
                args)
            sys.exit(status)
    finally:
        if tempdir:
            shutil.rmtree(outputdir)


void compile_to_c(str program_text, str path):
    # Compile the program to C (also generate binary by default).
    result = build.build(program_text, path, target=build.C, flags=build_flags)

    if build.COMPILE_ONLY not in build_flags:
        # Run the translated program.
        # TODO command line arguments
        status = subprocess.call([result.binary_path])
        sys.exit(status)


tuple<str, str[]> process_options():
    if sys.executable:
        global interpreter
        interpreter = sys.executable
    args = sys.argv[1:]
    while args and args[0].startswith('-'):
        if args[0] == '--verbose':
            global verbose
            verbose = True
            args = args[1:]
        elif args[0] == '--py2' and args[1:]:
            # Generate Python 2 (but this is very buggy).
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
        else:
            usage('Invalid option {}'.format(args[0]))
    
    if not args:
        usage()
    
    return args[0], args[1:]    


void usage(str msg=None):
    if msg:
        sys.stderr.write('%s\n' % msg)
    sys.stderr.write('Usage: mypy.py [--verbose] [-c] PROGRAM\n')
    sys.exit(2)


void fail(str msg):
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)


void log(str message):
    if verbose:
        print('LOG: {}'.format(message))


if __name__ == '__main__':
    main()
