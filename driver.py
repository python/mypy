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
from mypy.pythongen import PythonGenerator


# Fallback options
target = build.PYTHON
build_flags = <str> []
interpreter = 'python'


void main():
    path, module, args = process_options()
    try:
        if target == build.PYTHON:
            compile_to_python(path, module, args)
        elif target == build.C:
            compile_to_c(path, module, args)
        else:
            raise RuntimeError('unsupported target %d' % target)
    except CompileError as e:
        for m in e.messages:
            print(m)
        sys.exit(1)


void compile_to_python(str path, str module, str[] args):
    if path:
        basedir = os.path.dirname(path)
    else:
        basedir = os.getcwd()
    
    outputdir = os.path.join(basedir, '__mycache__')
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
        build.build(path,
                    module=module,
                    target=build.PYTHON,
                    output_dir=outputdir,
                    flags=build_flags)

        if build.COMPILE_ONLY not in build_flags:
            # Run the translated program.
            if module:
                # Run the module using runpy. We can't use -m since Python
                # would try to run the mypy code instead of the translated
                # code.
                p = os.path.join(outputdir, '__main__.py')
                f = open(p, 'w')
                f.write('import runpy\n'
                        "runpy.run_module('%s', run_name='__main__')" % module)
                f.close()
                opts = [p]
            else:
                opts = [os.path.join(outputdir, os.path.basename(path))]
            status = subprocess.call([interpreter] + opts + args)
            sys.exit(status)
    finally:
        if tempdir:
            shutil.rmtree(outputdir)


void compile_to_c(str path, str module, str[] args):
    assert not module # Not supported yet
    assert not args   # Not supported yet
    
    # Compile the program to C (also generate binary by default).
    result = build.build(path, target=build.C, flags=build_flags)

    if build.COMPILE_ONLY not in build_flags:
        # Run the compiled program.
        # TODO command line arguments
        status = subprocess.call([result.binary_path])
        sys.exit(status)


tuple<str, str, str[]> process_options():
    if sys.executable:
        global interpreter
        interpreter = sys.executable
    args = sys.argv[1:]
    while args and args[0].startswith('-'):
        if args[0] == '--verbose':
            build_flags.append(build.VERBOSE)
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
        elif args[0] == '-m' and args[1:]:
            build_flags.append(build.MODULE)
            return None, args[1], args[2:]
        else:
            usage('Invalid option {}'.format(args[0]))
    
    if not args:
        usage()
    
    return args[0], None, args[1:]


void usage(str msg=None):
    if msg:
        sys.stderr.write('%s\n' % msg)
    sys.stderr.write(
'''Usage: mypy [options] [-m mod | file] [args]

Options:
  -c          compile to native code (EXPERIMENTAL)
  -m mod      run module as a script (terminates option list)
  -S          compile only to C or Python; do not run or generate a binary
  --verbose   more verbose messages
  
Environment variables:
  MYPYPATH    additional module search path
  CC          the C compiler (used with -c)
  CFLAGS      command line options to the C compiler (used with -c)
''')
    sys.exit(2)


void fail(str msg):
    sys.stderr.write('%s\n' % msg)
    sys.exit(1)


if __name__ == '__main__':
    main()
