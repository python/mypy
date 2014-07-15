#!/usr/bin/env python3
"""Stub to run pinfer on a stdlib module.

Usage is currently awkward (better UI is TBD):

  p.py modname testfile [testargs]

Where:

  modname:  the full target module (e.g. textwrap)
  testfile: the full test module file (e.g. test/test_textwrap.py)

Example invocation:

  python3 p.py textwrap test/test_textwrap.py
"""


import sys
import imp
import pinfer


def main():
    try:
        modname, testname = sys.argv[1:3]
    except Exception:
        print('Usage: %s modname testfile [testargs]\n' % sys.argv[0],
              file=sys.stderr)
        sys.exit(2)
        
    __import__(modname)
    mod = sys.modules[modname]
    pinfer.infer_module(mod)
    pinfer.dump_at_exit()

    del sys.argv[1:3]
    imp.load_source('__main__', testname)

if __name__ == '__main__':
    main()
