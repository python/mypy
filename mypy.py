"""Mypy type checker and Python translator

Type check and program, translate it to Python and run it. Note that you must
use a mypy translator that has already been translated to run this program.
"""

import os
import os.path
import sys

from build import build
from pythongen import PythonGenerator
from errors import CompileError


# Options
verbose = False
pyversion = 3
interpreter = 'python'


void main():
    path, args = process_options()
    
    mainfile = open(path)
    text = mainfile.read()
    mainfile.close()
    
    try:
        # TODO determine directory more intelligently
        # TODO make sure only the current user can access the directory
        output_dir = '/tmp/mypy-xx'
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir, 0o777)
        
        # Parse and type check the program and dependencies.
        trees, symtable, infos, types = build(text, path, False, None, True)
        
        # Translate each file in the program to Python.
        # TODO support packages
        for t in trees:
            if not is_stub(t.path):
                out_path = os.path.join(output_dir, os.path.basename(t.path))
                log('translate {} to {}'.format(t.path, out_path))
                v = PythonGenerator(pyversion)
                t.accept(v)
                outfile = open(out_path, 'w')
                outfile.write(v.output())
                outfile.close()
        
        # Run the translated program.
        
        a = <str> []
        for arg in args[1:]:
            # TODO escape arguments etc.
            a.append('"{}"'.format(arg))

        os.system('{} "{}/{}" {}'.format(
                             interpreter, output_dir, os.path.basename(path),
                             ' '.join(a)))
    except CompileError as e:
        for m in e.messages:
            print(m)
        sys.exit(2)


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
            fail('Invalid option {}'.format(args[0]))
    
    if not args:
        fail()
    
    return args[0], args[1:]    


void fail(str msg=None):
    if msg:
        sys.stderr.write('%s\n' % msg)
    sys.stderr.write('Usage: mypy.py [--verbose] PROGRAM\n')
    sys.exit(1)


bool is_stub(str path):
    # TODO make the check more precise
    return path.startswith('stubs/') or '/stubs/' in path


void log(str message):
    if verbose:
        print('LOG: {}'.format(message))


if __name__ == '__main__':
    main()
