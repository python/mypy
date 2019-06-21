#!/usr/bin/env python

import glob
import os
import os.path
import sys

if sys.version_info < (3, 5, 0):
    sys.stderr.write("ERROR: You need Python 3.5 or later to use mypy.\n")
    exit(1)

# we'll import stuff from the source tree, let's ensure is on the sys path
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

# This requires setuptools when building; setuptools is not needed
# when installing from a wheel file (though it is still neeeded for
# alternative forms of installing, as suggested by README.md).
from setuptools import setup
from setuptools.command.build_py import build_py
from mypy.version import __version__ as version
from mypy import git

git.verify_git_integrity_or_abort(".")

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
        rv.extend([f[5:] for f in files])
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

package_data = ['py.typed']

package_data += find_package_data(os.path.join('mypy', 'typeshed'), ['*.py', '*.pyi'])

package_data += find_package_data(os.path.join('mypy', 'xml'), ['*.xsd', '*.xslt', '*.css'])

USE_MYPYC = False
# To compile with mypyc, a mypyc checkout must be present on the PYTHONPATH
if len(sys.argv) > 1 and sys.argv[1] == '--use-mypyc':
    sys.argv.pop(1)
    USE_MYPYC = True
if os.getenv('MYPY_USE_MYPYC', None) == '1':
    USE_MYPYC = True

if USE_MYPYC:
    MYPYC_BLACKLIST = (
        # Need to be runnable as scripts
        '__main__.py',
        'sitepkgs.py',
        os.path.join('dmypy', '__main__.py'),

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

    everything = find_package_data('mypy', ['*.py'])
    # Start with all the .py files
    all_real_pys = [x for x in everything if not x.startswith('typeshed' + os.sep)]
    # Strip out anything in our blacklist
    mypyc_targets = [x for x in all_real_pys if x not in MYPYC_BLACKLIST]
    # Strip out any test code
    mypyc_targets = [x for x in mypyc_targets if not x.startswith('test' + os.sep)]
    # ... and add back in the one test module we need
    mypyc_targets.append(os.path.join('test', 'visitors.py'))

    # Fix the paths to be full
    mypyc_targets = [os.path.join('mypy', x) for x in mypyc_targets]
    # The targets come out of file system apis in an unspecified
    # order. Sort them so that the mypyc output is deterministic.
    mypyc_targets.sort()

    # This bit is super unfortunate: we want to use the mypy packaged
    # with mypyc. It will arrange for the path to be setup so it can
    # find it, but we've already imported parts, so we remove the
    # modules that we've imported already, which will let the right
    # versions be imported by mypyc.
    del sys.modules['mypy']
    del sys.modules['mypy.version']
    del sys.modules['mypy.git']

    from mypyc.build import mypycify, MypycifyBuildExt
    opt_level = os.getenv('MYPYC_OPT_LEVEL', '3')
    ext_modules = mypycify(
        mypyc_targets,
        ['--config-file=mypy_bootstrap.ini'],
        opt_level=opt_level,
        # Use multi-file compliation mode on windows because without it
        # our Appveyor builds run out of memory sometimes.
        multi_file=sys.platform == 'win32',
    )
    cmdclass['build_ext'] = MypycifyBuildExt
else:
    ext_modules = []


classifiers = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
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
      py_modules=[],
      ext_modules=ext_modules,
      packages=[
          'mypy', 'mypy.test', 'mypy.server', 'mypy.plugins', 'mypy.newsemanal', 'mypy.dmypy'
      ],
      package_data={'mypy': package_data},
      entry_points={'console_scripts': ['mypy=mypy.__main__:console_entry',
                                        'stubgen=mypy.stubgen:main',
                                        'dmypy=mypy.dmypy.client:console_entry',
                                        ]},
      classifiers=classifiers,
      cmdclass=cmdclass,
      # When changing this, also update test-requirements.txt.
      install_requires=['typed_ast >= 1.4.0, < 1.5.0',
                        'typing_extensions>=3.7.4',
                        'mypy_extensions >= 0.4.0, < 0.5.0',
                        ],
      # Same here.
      extras_require={'dmypy': 'psutil >= 4.0'},
      include_package_data=True,
      )
