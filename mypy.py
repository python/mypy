#!/usr/bin/env python
"""Mypy type checker and Python translator

Type check and program, translate it to Python and run it. Note that you must
use a translated mypy translator to run this program.
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
pyversion = 3
interpreter = 'python'


void main():
    path, args = process_options()

    try:
        mainfile = open(path)
        text = mainfile.read()
        mainfile.close()
    except IOError as ioerr:
        fail("mypy: can't read file '{}': {}".format(path,
                                                     ioerr.strerror))
    
    try:
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
            build.build(text, path,
                        target=build.PYTHON,
                        output_dir=outputdir,
                        python_version=pyversion)
            
            # Run the translated program.
            status = subprocess.call(
                [interpreter,
                 '{}/{}'.format(outputdir,os.path.basename(path))] +
                args)
            sys.exit(status)
        finally:
            if tempdir:
                shutil.rmtree(outputdir)
    except CompileError as e:
        for m in e.messages:
            print(m)
        sys.exit(1)


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
            global pyversion
            pyversion = 2
            interpreter = args[1]
            args = args[2:]
        else:
            usage('Invalid option {}'.format(args[0]))
    
    if not args:
        usage()
    
    return args[0], args[1:]    


void usage(str msg=None):
    if msg:
        sys.stderr.write('%s\n' % msg)
    sys.stderr.write('Usage: mypy.py [--verbose] PROGRAM\n')
    sys.exit(2)


void fail(str msg):
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)


void log(str message):
    if verbose:
        print('LOG: {}'.format(message))


if __name__ == '__main__':
    main()
