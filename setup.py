#!/usr/bin/env python

import glob
import os
import os.path
import sys

if sys.version_info < (3, 5, 0):
    sys.stderr.write("ERROR: You need Python 3.5 or later to use mypyc.\n")
    exit(1)

# This requires setuptools when building; setuptools is not needed
# when installing from a wheel file.
from setuptools import setup
from setuptools.command.build_py import build_py
from mypyc.version import __version__ as version

description = 'Compiler from type annotated Python to C extensions'
long_description = '''
mypyc -- Compiler from type annotated Python to C extensions
=========================================

'''.lstrip()


def find_package_data(base, globs):
    """Find all interesting data files, for setup(package_data=)

    Arguments:
      root:  The directory to search in.
      globs: A list of glob patterns to accept files.
    """

    rv_dirs = [root for root, dirs, files in os.walk(base)]
    rv = []
    for rv_dir in rv_dirs:
        files = []
        for pat in globs:
            files += glob.glob(os.path.join(rv_dir, pat))
        if not files:
            continue
        rv.extend([os.path.relpath(f, 'mypyc') for f in files])
    return rv


class CustomPythonBuild(build_py):
    def pin_version(self):
        path = os.path.join(self.build_lib, 'mypy')
        self.mkpath(path)
        with open(os.path.join(path, 'version.py'), 'w') as stream:
            stream.write('__version__ = "{}"\n'.format(version))

    def run(self):
        self.execute(self.pin_version, ())
        build_py.run(self)


cmdclass = {'build_py': CustomPythonBuild}

package_data = []

package_data += find_package_data(
    os.path.join('mypyc', 'external', 'mypy', 'mypy'), ['*.py', '*.pyi'])
package_data += find_package_data(
    os.path.join('mypyc', 'lib-rt'), ['*.c', '*.h'])

classifiers = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Topic :: Software Development',
]

setup(name='mypyc',
      version=version,
      description=description,
      long_description=long_description,
      author='Jukka Lehtosalo',
      author_email='jukka.lehtosalo@iki.fi',
      url='https://github.com/mypyc/mypyc',
      license='MIT License',
      py_modules=[],
      packages=['mypyc', 'mypyc.test'],
      package_data={'mypyc': package_data},
      scripts=['scripts/mypyc'],
      classifiers=classifiers,
      cmdclass=cmdclass,
      install_requires = ['typed-ast >= 1.2.0, < 1.3.0',
                          'mypy_extensions >= 0.4.0, < 0.5.0',
                          ],
      include_package_data=True,
      )
