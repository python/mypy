#!/usr/bin/env python

import glob
import os
import os.path
import sys

from distutils.core import setup

if sys.version_info < (3, 2, 0):
    sys.stderr.write("ERROR: You need Python 3.2 or later to use mypy.\n")
    exit(1)

version = '0.2.0'
description = 'Optional static typing for Python'
long_description = '''
Mypy -- Optional Static Typing for Python
=========================================

Add type annotations to your Python programs, and use mypy to type
check them.  Mypy is essentially a Python linter on steroids, and it
can catch many programming errors by analyzing your program, without
actually having to run it.  Mypy has a powerful type system with
features such as type inference, gradual typing, generics and union
types.
'''.lstrip()

stubs = []

for py_version in ['3.4', '3.3', '3.2', '2.7']:
    base = os.path.join('stubs', py_version)
    if not os.path.exists(base):
        os.mkdir(base)

    stub_dirs = ['']
    for root, dirs, files in os.walk(base):
        stub_dirs.extend(os.path.relpath(os.path.join(root, stub_dir), base)
                         for stub_dir in dirs
                         if stub_dir != '__pycache__')
    for stub_dir in stub_dirs:
        target = os.path.join('lib', 'mypy', 'stubs', py_version, stub_dir)
        files = glob.glob(os.path.join(base, stub_dir, '*.py'))
        files += glob.glob(os.path.join(base, stub_dir, '*.pyi'))
        stubs.append((target, files))

classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Topic :: Software Development',
]

setup(name='mypy-lang',
      version=version,
      description=description,
      long_description=long_description,
      author='Jukka Lehtosalo',
      author_email='jukka.lehtosalo@iki.fi',
      url='http://www.mypy-lang.org/',
      license='MIT License',
      platforms=['POSIX'],
      package_dir={'': 'lib-typing/3.2', 'mypy': 'mypy'},
      py_modules=['typing'],
      packages=['mypy'],
      scripts=['scripts/mypy'],
      data_files=stubs,
      classifiers=classifiers,
      )
