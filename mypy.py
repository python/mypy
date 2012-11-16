import os.path
import alore
import sys
from os import make_dirs, base_name, system
from build import build
from pythongen import PythonGenerator
from io import OUTPUT
from errors import CompileError


void main(list<str> args):
    verbose = False
    while args != [] and args[0].startswith('-'):
        _x = args[0]
        if _x == '--verbose':
            verbose = True
            args = args[1:]
        else:
            fail('Invalid option {}'.format(args[0]))
    
    if args == []:
        fail()
    
    path = args[0]
    
    main_file = file(path)
    text = main_file.read()
    main_file.close()
    
    try:
        # TODO determine directory more intelligently
        # TODO make sure only the current user can access the directory
        output_dir = '/tmp/mypy-xx'
        make_dirs(output_dir)
        
        # Parse and type check the program and dependencies.
        trees, symtable, infos, types = build(text, path, False, None, True)
        
        # Translate each file in the program to Python.
        # TODO support packages
        for t in trees:
            if not is_stub(t.path):
                out_path = os.path.join(output_dir, base_name(t.path))
                if verbose:
                    print('LOG: translate {} to {}'.format(t.path, out_path))
                v = PythonGenerator()
                t.accept(v)
                out_file = file(out_path, OUTPUT)
                out_file.write(v.output())
                out_file.close()
        
        # Run the translated program.
        # TODO determine path to Python interpreter reliably
        
        list<str> a = []
        for arg in args[1:]:
            # TODO escape arguments etc.
            a.append('"{}"'.format(arg))
        
        system('python3 "{}/{}" {}'.format(output_dir, base_name(path), ' '.join(a)))
    except CompileError as e:
        for m in e.messages:
            alore.writeln(m)
        exit(2)


def fail(msg=None):
    if msg is not None:
        sys.stderr.write_ln(msg + '\n')
    sys.stderr.write_ln('Usage: mypy.alo [--verbose] PROGRAM')
    exit(1)


def is_stub(path):
    # TODO make the check more precise
    return path.startswith('stubs/') or '/stubs/' in path
