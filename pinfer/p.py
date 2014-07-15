#!/usr/bin/env python3
"""Stub to run pinfer on a stdlib module.

Usage is currently awkward (better UI is TBD):

  p.py modname testname mainexpr [testargs]

Where:

  modname:  the full target module (e.g. textwrap)
  testname: the full test module name (e.g. test.test_textwrap)
  mainargs: an expression to run in the testname module
            (e.g. 'unittest.main()')

Example invocation:

  python3 p.py textwrap test.test_textwrap 'unittest.main()'
"""


import sys

import pinfer


def main():
    try:
        modname, testname, mainexpr = sys.argv[1:4]
    except Exception:
        print('Usage: %s modname testname mainexpr [testargs]\n' % sys.argv[0],
              file=sys.stderr)
        sys.exit(2)
    __import__(modname)
    mod = sys.modules[modname]
    pinfer.infer_module(mod)
    pinfer.dump_at_exit()
    del sys.argv[1:4]
    __import__(testname)
    testmod = sys.modules[testname]
    sys.modules['__main__'] = testmod
    testmod.__name__ = '__main__'
    eval(mainexpr, testmod.__dict__)


if __name__ == '__main__':
    main()
