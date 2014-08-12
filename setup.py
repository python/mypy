#!/usr/bin/env python

import glob
import os
import os.path
import sys

from mypy.codec import register

from setuptools import setup, find_packages

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
      package_dir={'typing': 'lib-typing/3.2/typing', 'mypy': 'mypy'},
      package_data={'mypy': ['stubs/*/*.py', 'lib/*py', 'vm/*']},
      py_modules=['typing'],
      packages=find_packages(),
      entry_points={
          'console_scripts': ['mypy = mypy.main:main']
      },
      classifiers=classifiers,
      )
