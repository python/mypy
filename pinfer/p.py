#!/usr/bin/env python3
"""Stub to run pinfer on a stdlib module.

Usage:

  p.py modname testfile [testargs]

Where:

  modname:  the full target module (e.g. textwrap).  If modname is "-",
            infer the types of all imported modules.
  testfile: the full test module file (e.g. test/test_textwrap.py)

Example invocation:

  python3 p.py test/test_textwrap.py
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
    try:
        targetpackage, testfile = sys.argv[1], sys.argv[2]
        del sys.argv[1:3]
    except Exception:
        sys.stderr.write('Usage: %s targetpackage testfile [testargs]\n' % sys.argv[0])
        sys.exit(2)

    # help us with local imports
    filemodule = os.path.dirname(os.path.abspath(testfile))
    sys.path.append(filemodule)

    targetmod = __import__(targetpackage)
    targetfile = inspect.getfile(targetmod)
    pinfer.infer_module(targetmod)

    @atexit.register
    def rewrite_file(targetfile=targetfile, pinfer=pinfer):
        if targetfile.endswith(".pyc"):
          targetfile = targetfile[0:-1]
        annotated = pinfer.annotate_file(targetfile)
        print(annotated)

    # run testfile as main
    del sys.modules['__main__']
    imp.load_source('__main__', testfile)

if __name__ == '__main__':
    main()
