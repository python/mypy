#!/usr/bin/env python

import glob
import os
import os.path
import sys

if sys.version_info < (3, 2, 0):
    sys.stderr.write("ERROR: You need Python 3.2 or later to use mypy.\n")
    exit(1)

from distutils.core import setup
from distutils.command.build_py import build_py
from mypy.version import __version__
from mypy import git

git.verify_git_integrity_or_abort(".")

version = __version__
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


def cache_version_id():
    """Returns the version id to use for the incremental hash.

    If setup.py is run from a git repo, the git commit hash will be
    included if possible. If not, then this function will fall back to
    using the default version id from mypy/version.py."""
    if git.is_git_repo('.') and git.have_git():
        return __version__ + '-' + git.git_revision('.').decode('utf-8')
    else:
        # Default fallback
        return __version__


def find_data_files(base, globs):
    """Find all interesting data files, for setup(data_files=)

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
        target = os.path.join('lib', 'mypy', rv_dir)
        rv.append((target, files))

    return rv


class CustomPythonBuild(build_py):
    def pin_version(self):
        path = os.path.join(self.build_lib, 'mypy')
        self.mkpath(path)
        with open(os.path.join(path, 'version.py'), 'w') as stream:
            stream.write('__version__ = "{}"\n'.format(cache_version_id()))

    def run(self):
        self.execute(self.pin_version, ())
        build_py.run(self)


data_files = []

data_files += find_data_files('typeshed', ['*.py', '*.pyi'])

data_files += find_data_files('xml', ['*.xsd', '*.xslt', '*.css'])

classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Topic :: Software Development',
]

package_dir = {'mypy': 'mypy'}
if sys.version_info < (3, 5, 0):
    package_dir[''] = 'lib-typing/3.2'

scripts = ['scripts/mypy', 'scripts/stubgen']
if os.name == 'nt':
    scripts.append('scripts/mypy.bat')

setup(name='mypy-lang',
      version=version,
      description=description,
      long_description=long_description,
      author='Jukka Lehtosalo',
      author_email='jukka.lehtosalo@iki.fi',
      url='http://www.mypy-lang.org/',
      license='MIT License',
      platforms=['POSIX'],
      package_dir=package_dir,
      py_modules=['typing'] if sys.version_info < (3, 5, 0) else [],
      packages=['mypy'],
      scripts=scripts,
      data_files=data_files,
      classifiers=classifiers,
      cmdclass={'build_py': CustomPythonBuild},
      )
