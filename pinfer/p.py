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
        modname, testfile = sys.argv[1], sys.argv[2]
        del sys.argv[1:3]
    except Exception:
        print('Usage: %s outputfile modname testfile [testargs]\n' % sys.argv[0], file=sys.stderr)
        sys.exit(2)

    pinfer.dump_at_exit()

    # help us with local imports
    filemodule = os.path.dirname(os.path.abspath(testfile))
    sys.path.append(filemodule)

    if modname == '-':
      __builtins__.__import__ = inferring_import
    else:
      module = __import__(modname)
      pinfer.infer_module(module)

    # run testfile as main
    del sys.modules['__main__']
    imp.load_source('__main__', testfile)

if __name__ == '__main__':
    main()
