#!/usr/bin/env python

import glob
import os
import os.path
import sys

from distutils.core import setup

if sys.version_info < (3, 2, 0):
    sys.stderr.write("ERROR: You need Python 3.2 or later to use mypy.\n")
    exit(1)

version = '0.0.1.dev1'
description = 'Optional static type checker for Python'
long_description = '''
Mypy -- Optional Static Type Checker for Python
===============================================

Mypy lets you add type annotations to Python programs, type check them
without running them, and run the programs using a standard Python 3
interpreter.
'''.lstrip()

stub_dirs = [''] + [name for name in os.listdir('stubs')
                    if os.path.isdir(os.path.join('stubs', name))]

stubs = []
for stub_dir in stub_dirs:
    target = os.path.join('lib', 'mypy', 'stubs', stub_dir)
    files = glob.glob(os.path.join('stubs', stub_dir, '*.py'))
    stubs.append((target, files))
    
classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Topic :: Software Development',
]

setup(name='mypy',
      version=version,
      description=description,
      long_description=long_description,
      author='Jukka Lehtosalo',
      author_email='jukka.lehtosalo@iki.fi',
      url='http://www.mypy-lang.org/',
      license='MIT License',
      platforms=['POSIX'],
      package_dir={'': 'lib-typing', 'mypy': 'mypy'},
      py_modules=['typing'],
      packages=['mypy'],
      scripts=['scripts/mypy'],
      data_files=stubs,
      classifiers=classifiers,
      )
