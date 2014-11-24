#!/usr/bin/env python3
"""Stub to run pinfer on a module.

Usage:

  p.py targetmod testfile [outfile] [ -- testargs]

Where:

  targetmod:  the full target module (e.g. textwrap)
  testfile: the full test module file (e.g. test/test_textwrap.py)
  outfile:  where to write the annotated module.  If unspecified, will
            write stubs at end of stdout.

Example invocation:

  python3 p.py textwrap test/test_textwrap.py
"""


import sys
import imp
import pinfer
import os
import atexit
import inspect

iport = __builtins__.__import__
watched = set()


def inferring_import(*args, **kwargs):
    module = iport(*args, **kwargs)
    if module not in watched:
        watched.add(module)
        pinfer.infer_module(module)
    return module


def main():
    if '--' in sys.argv:
        argslen = sys.argv.index('--')
    else:
        argslen = len(sys.argv)
    args = sys.argv[1:argslen]
    del sys.argv[1:argslen + 1]

    if len(args) == 2:
        targetpackage, testfile = args
        outfile = None
    elif len(args) == 3:
        targetpackage, testfile, outfile = args
    else:
        sys.stderr.write('Usage: %s targetmodule testfile [outfile] [ -- testargs]\n' %
                         sys.argv[0])
        sys.exit(2)

    # help us with local imports
    filemodule = os.path.dirname(os.path.abspath(testfile))
    sys.path.append(filemodule)

    targetmod = __import__(targetpackage)
    targetfile = inspect.getfile(targetmod)
    pinfer.infer_module(targetmod)

    if outfile:
        @atexit.register
        def rewrite_file(targetfile=targetfile, outfile=outfile, pinfer=pinfer):
            if targetfile.endswith(".pyc"):
                targetfile = targetfile[0:-1]
            annotated = pinfer.annotate_file(targetfile)
            open(outfile, "w").write(annotated)
    else:
        pinfer.dump_at_exit()

    pinfer.ignore_files.add(os.path.abspath(testfile))

    # run testfile as main
    del sys.modules['__main__']
    imp.load_source('__main__', testfile)

if __name__ == '__main__':
    main()
