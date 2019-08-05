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
        path = os.path.join(self.build_lib, 'mypyc')
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

USE_MYPYC = False
# To compile with mypyc, a mypyc checkout must be present on the PYTHONPATH
if len(sys.argv) > 1 and sys.argv[1] == '--use-mypyc':
    sys.argv.pop(1)
    USE_MYPYC = True
if os.getenv('MYPYC_USE_MYPYC', None) == '1':
    USE_MYPYC = True

if USE_MYPYC:
    MYPYC_BLACKLIST = ('__init__.py',)
    MYPY_BLACKLIST = (
        # Need to be runnable as scripts
        '__main__.py',
        'sitepkgs.py',
        'dmypy/__main__.py',

        # Needs to be interpreted to provide a hook to interpreted plugins
        'interpreted_plugin.py',

        # Uses __getattr__/__setattr__
        'split_namespace.py',

        # Lies to mypy about code reachability
        'bogus_type.py',

        # We don't populate __file__ properly at the top level or something?
        # Also I think there would be problems with how we generate version.py.
        'version.py',
    )

    # Start with all the .py files
    mypyc_targets = find_package_data('mypyc', ['*.py'])
    # Strip out blacklist files
    mypyc_targets = [x for x in mypyc_targets if x not in MYPYC_BLACKLIST]
    # Strip out any mypyc test code
    mypyc_targets = [x for x in mypyc_targets if not x.startswith('test' + os.sep)]
    # Figure out which mypy files we want to keep
    mypy_dir = 'external' + os.sep + 'mypy' + os.sep + 'mypy' + os.sep
    mypy_targets = [x for x in mypyc_targets if x.startswith(mypy_dir)]
    # Temprorarily remove mypy stuff from mypyc targets
    mypyc_targets = [x for x in mypyc_targets if not x.startswith('external' + os.sep)]
    # Remove typeshed stuff
    mypy_targets = [x for x in mypy_targets if not x.startswith(mypy_dir + 'typeshed' + os.sep)]
    # Strip out anything in mypy blacklist
    mypy_targets = [x for x in mypy_targets if os.path.join(mypy_dir, x) not in MYPY_BLACKLIST]
    # Strip out any mypy test code
    mypy_targets = [x for x in mypy_targets if not x.startswith(mypy_dir + 'test')]
    # ... and add back in the one test module we need
    mypy_targets.append(os.path.join(mypy_dir + 'test', 'visitors.py'))
    # Add refined mypy targets to mypyc targets
    mypyc_targets.extend(mypy_targets)
    # Fix the paths to be full
    mypyc_targets = [os.path.join('mypyc', x) for x in mypyc_targets]
    # The targets come out of file system apis in an unspecified
    # order. Sort them so that the mypyc output is deterministic.
    mypyc_targets.sort()

    opt_level = os.getenv('MYPYC_OPT_LEVEL', '3')

    from mypyc.build import mypycify

    ext_modules = mypycify(mypyc_targets,
                  ['--config-file=mypyc_bootstrap.ini'],
                  opt_level=opt_level,
                  multi_file=sys.platform == 'win32')
else:
  ext_modules = []

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
      ext_modules= ext_modules,
      py_modules=[],
      packages=['mypyc', 'mypyc.test'],
      package_data={'mypyc': package_data},
      scripts=['scripts/mypyc'],
      classifiers=classifiers,
      cmdclass=cmdclass,
      install_requires = ['typed-ast >= 1.4.0, < 1.5.0',
                          'typing_extensions>=3.7.4',
                          'mypy_extensions >= 0.4.0, < 0.5.0',
                          ],
      include_package_data=True,
      )
