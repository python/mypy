#!/usr/bin/env python

"""setup.py for Python 2.x typing module"""

import glob
import os
import os.path
import sys

from distutils.core import setup

if sys.version_info >= (3, 0, 0):
    sys.stderr.write("ERROR: You need Python 2.x to install this module.\n")
    exit(1)

version = '0.0.1.dev1'
description = 'typing (Python 2.x)'
long_description = '''
typing (Python 2.x)
===================

This module is part of mypy, a static type checker for Python.
'''.lstrip()

classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX',
    'Programming Language :: Python :: 2.7',
    'Topic :: Software Development',
]

setup(name='typing',
      version=version,
      description=description,
      long_description=long_description,
      author='Jukka Lehtosalo',
      author_email='jukka.lehtosalo@iki.fi',
      url='http://www.mypy-lang.org/',
      license='MIT License',
      platforms=['POSIX'],
      py_modules=['typing'],
      classifiers=classifiers,
      )
