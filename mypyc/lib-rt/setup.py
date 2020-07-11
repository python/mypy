"""Build script for mypyc C runtime library unit tests.

The tests are written in C++ and use the Google Test framework.
"""

from distutils.core import setup, Extension

setup(name='test_capi',
      version='0.1',
      ext_modules=[Extension(
          'test_capi',
          ['test_capi.cc', 'CPy.cc', 'list_ops.c'],
          depends=['CPy.h', 'mypyc_util.h', 'pythonsupport.h'],
          extra_compile_args=['--std=c++11', '-Wno-unused-function', '-Wno-sign-compare'],
          library_dirs=['../external/googletest/make'],
          libraries=['gtest'],
          include_dirs=['../external/googletest', '../external/googletest/include'],
      )])
