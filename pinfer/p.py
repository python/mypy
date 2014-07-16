#!/usr/bin/env python3
"""Stub to run pinfer on a stdlib module.

Usage is currently awkward (better UI is TBD):

  p.py testfile [testargs]

Where:

  testfile: the full test module file (e.g. test/test_textwrap.py)

Example invocation:

  python3 p.py test/test_textwrap.py
"""


import sys
import imp
import pinfer

iport = __builtins__.__import__
watched = set()
def inferring_import(*args, **kwargs):
  module = iport(*args, **kwargs)
  if module not in watched:
    watched.add(module)
    pinfer.infer_module(module)
  #  print(module)
  return module

def main():
    try:
        testfile = sys.argv[1]
        del sys.argv[1]
    except Exception:
        print('Usage: %s testfile [testargs]\n' % sys.argv[0], file=sys.stderr)
        sys.exit(2)
        
    pinfer.dump_at_exit()

    __builtins__.__import__ = inferring_import

    # run testfile as main
    del sys.modules['__main__']
    imp.load_source('__main__', testfile)

if __name__ == '__main__':
    main()
