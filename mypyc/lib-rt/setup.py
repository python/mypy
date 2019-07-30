from distutils.core import setup, Extension

setup(name='test_capi',
      version='0.1',
      ext_modules=[Extension(
          'test_capi',
          ['test_capi.cc', 'CPy.cc'],
          depends=['CPy.h', 'mypyc_util.h', 'pythonsupport.h'],
          extra_compile_args=['--std=c++11', '-Wno-unused-function', '-Wno-sign-compare'],
          library_dirs=['../external/googletest/make'],
          libraries=['gtest'],
          include_dirs=['../external/googletest', '../external/googletest/include'],
      )])
