"""Mypy type checker and Python translator

Type check and program, translate it to Python and run it. Note that you must
use a mypy translator that has already been translated to run this program.
"""

import os
import os.path
import sys
import tempfile
import shutil

from build import build
from pythongen import PythonGenerator
from errors import CompileError


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
            # Parse and type check the program and dependencies.
            trees, symtable, infos, types = build(text, path, False, None,
                                                  True)
        
            # Translate each file in the program to Python.
            # TODO support packages
            for t in trees:
                if not is_stub(t.path):
                    out_path = os.path.join(outputdir,
                                            os.path.basename(t.path))
                    log('translate {} to {}'.format(t.path, out_path))
                    v = PythonGenerator(pyversion)
                    t.accept(v)
                    outfile = open(out_path, 'w')
                    outfile.write(v.output())
                    outfile.close()

            # Run the translated program.

            a = <str> []
            for arg in args:
                # TODO escape arguments etc.
                a.append('"{}"'.format(arg))

            os.system('{} "{}/{}" {}'.format(interpreter, outputdir,
                                             os.path.basename(path),
                                             ' '.join(a)))
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


bool is_stub(str path):
    # TODO make the check more precise
    return path.startswith('stubs/') or '/stubs/' in path


void log(str message):
    if verbose:
        print('LOG: {}'.format(message))


if __name__ == '__main__':
    main()
