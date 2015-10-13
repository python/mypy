#!/usr/bin/env python3

if False:
    import typing

if True:
    # When this is run as a script, `typing` is not available yet.
    import sys
    from os.path import (
        basename,
        dirname,
        isabs,
        isdir,
        join,
        realpath,
        relpath,
        splitext,
    )

    def get_versions():  # type: () -> typing.List[str]
        major = sys.version_info[0]
        minor = sys.version_info[1]
        if major == 2:
            return ['2.7']
        else:
            # generates list of python versions to use.
            # For Python2, this is only [2.7].
            # Otherwise, it is [3.4, 3.3, 3.2, 3.1, 3.0].
            return ['%d.%d' % (major, i) for i in range(minor, -1, -1)]

    sys.path[0:0] = [v for v in [join('lib-typing', v) for v in get_versions()] if isdir(v)]
    # Now `typing` is available.


from typing import Dict, List, Optional, Set

from mypy.waiter import Waiter, LazySubprocess

import itertools
import os


# Allow this to be symlinked to support running an installed version.
SOURCE_DIR = dirname(realpath(__file__))


# Ideally, all tests would be `discover`able so that they can be driven
# (and parallelized) by an external test driver.

class Driver:

    def __init__(self, whitelist: List[str], blacklist: List[str],
            arglist: List[str], verbosity: int, xfail: List[str]) -> None:
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.arglist = arglist
        self.verbosity = verbosity
        self.waiter = Waiter(verbosity=verbosity, xfail=xfail)
        self.versions = get_versions()
        self.cwd = os.getcwd()
        self.env = dict(os.environ)

    def prepend_path(self, name: str, paths: List[str]) -> None:
        old_val = self.env.get(name)
        paths = [p for p in paths if isdir(p)]
        if not paths:
            return
        if old_val is not None:
            new_val = ':'.join(itertools.chain(paths, [old_val]))
        else:
            new_val = ':'.join(paths)
        self.env[name] = new_val

    def allow(self, name: str) -> bool:
        if any(f in name for f in self.whitelist):
            if not any(f in name for f in self.blacklist):
                if self.verbosity >= 2:
                    print('SELECT   #%d %s' % (len(self.waiter.queue), name))
                return True
        if self.verbosity >= 3:
            print('OMIT     %s' % name)
        return False

    def add_mypy(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'check %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = ['mypy', '--use-python-path']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_python(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'run %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = [sys.executable]
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_both(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        self.add_mypy(name, *args, cwd=cwd)
        self.add_python(name, *args, cwd=cwd)

    def add_mypy_mod(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'check %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = ['mypy', '--use-python-path', '-m']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_python_mod(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'run %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = [sys.executable, '-m']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_both_mod(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        self.add_mypy_mod(name, *args, cwd=cwd)
        self.add_python_mod(name, *args, cwd=cwd)

    def add_mypy_string(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'check %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = ['mypy', '--use-python-path', '-c']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_python_string(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'run %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = [sys.executable, '-c']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_both_string(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        self.add_mypy_string(name, *args, cwd=cwd)
        self.add_python_string(name, *args, cwd=cwd)

    def add_python2(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'run2 %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = ['python2']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_myunit(self, name: str, *args: str, cwd: Optional[str] = None,
            script: bool = True) -> None:
        name = 'run %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        if script:
            largs[0:0] = ['myunit']
        else:
            largs[0:0] = [sys.executable, '-m' 'mypy.myunit']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_flake8(self, name: str, file: str, cwd: Optional[str] = None) -> None:
        name = 'lint %s' % name
        if not self.allow(name):
            return
        largs = ['flake8', file]
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def list_tasks(self) -> None:
        for id, task in enumerate(self.waiter.queue):
            print('{id}:{task}'.format(id=id, task=task.name))


def add_basic(driver: Driver) -> None:
    if False:
        driver.add_mypy('file setup.py', join(SOURCE_DIR, 'setup.py'))
    driver.add_flake8('file setup.py', join(SOURCE_DIR, 'setup.py'))
    driver.add_mypy('file runtests.py', join(SOURCE_DIR, 'runtests.py'))
    driver.add_flake8('file runtests.py', join(SOURCE_DIR, 'runtests.py'))
    driver.add_mypy('legacy entry script', join(SOURCE_DIR, 'scripts/mypy'))
    driver.add_flake8('legacy entry script', join(SOURCE_DIR, 'scripts/mypy'))
    driver.add_mypy('legacy myunit script', join(SOURCE_DIR, 'scripts/myunit'))
    driver.add_flake8('legacy myunit script', join(SOURCE_DIR, 'scripts/myunit'))
    driver.add_mypy_mod('entry mod mypy', 'mypy')
    driver.add_mypy_mod('entry mod mypy.stubgen', 'mypy.stubgen')
    driver.add_mypy_mod('entry mod mypy.myunit', 'mypy.myunit')


def find_files(base: str, prefix: str = '', suffix: str = '') -> List[str]:
    base = join(SOURCE_DIR, base)
    return [join(root, f)
            for root, dirs, files in os.walk(base)
            for f in files
            if f.startswith(prefix) and f.endswith(suffix)]


def file_to_module(file: str, ignore: str = '') -> str:
    file = relpath(file, join(SOURCE_DIR, ignore))
    rv = splitext(file)[0].replace(os.sep, '.')
    if rv.endswith('.__init__'):
        rv = rv[:-len('.__init__')]
    return rv


def add_imports(driver: Driver) -> None:
    # Make sure each module can be imported originally.
    # There is currently a bug in mypy where a module can pass typecheck
    # because of *implicit* imports from other modules.
    for f in find_files('mypy', suffix='.py'):
        mod = file_to_module(f)
        if '.test.data.' in mod:
            continue
        driver.add_mypy_string('import %s' % mod, 'import %s' % mod)
        if not mod.endswith('.__main__'):
            driver.add_python_string('import %s' % mod, 'import %s' % mod)
        driver.add_flake8('module %s' % mod, f)


def add_myunit(driver: Driver) -> None:
    for f in find_files('mypy', prefix='test', suffix='.py'):
        mod = file_to_module(f)
        if '.codec.test.' in mod:
            # myunit is Python3 only.
            driver.add_python_mod('unittest %s' % mod, 'unittest', mod)
            driver.add_python2('unittest %s' % mod, '-m', 'unittest', mod)
        elif mod == 'mypy.test.testpythoneval':
            # Run Python evaluation integration tests separetely since they are much slower
            # than proper unit tests.

            # testpythoneval requires lib-typing/2.7 to be available. Ick!
            driver.add_myunit('eval-test %s' % mod, '-m', mod, *driver.arglist,
                cwd=SOURCE_DIR, script=False)
        else:
            driver.add_myunit('unit-test %s' % mod, '-m', mod, *driver.arglist)


def add_stubs(driver: Driver) -> None:
    # Only test each module once, for the latest Python version supported.
    # The third-party stub modules will only be used if it is not in the version.
    seen = set()  # type: Set[str]
    for version in driver.versions:
        for pfx in ['', 'third-party-']:
            stubdir = join('mypy/data/stubs', pfx + version)
            for f in find_files(stubdir, suffix='.pyi'):
                module = file_to_module(f, stubdir)
                if module not in seen:
                    seen.add(module)
                    driver.add_mypy_string(
                        'stub (%s) module %s' % (pfx + version, module),
                        'import typing, %s' % module)


def add_libpython(driver: Driver) -> None:
    seen = set()  # type: Set[str]
    for version in driver.versions:
        libpython_dir = join('lib-python', version)
        for f in find_files(libpython_dir, prefix='test_', suffix='.pyi'):
            module = file_to_module(f, libpython_dir)
            if module not in seen:
                seen.add(module)
                driver.add_mypy_mod(
                    'libpython (%s) module %s' % (version, module),
                    module,
                    cwd=join(SOURCE_DIR, libpython_dir))


def add_samples(driver: Driver) -> None:
    for f in find_files('samples', suffix='.py'):
        if 'codec' in f:
            cwd, bf = dirname(f), basename(f)
            bf = bf[:-len('.py')]
            driver.add_mypy_string('codec file %s' % f,
                    'import mypy.codec.register, %s' % bf,
                    cwd=cwd)
        else:
            f = relpath(f, SOURCE_DIR)
            driver.add_mypy('file %s' % f, f, cwd=SOURCE_DIR)


def usage(status: int) -> None:
    print('Usage: %s [-h | -v | -q | [-x] filter | -a argument] ... [-- filter ...]' % sys.argv[0])
    print('  -h, --help             show this help')
    print('  -v, --verbose          increase driver verbosity')
    print('  -q, --quiet            decrease driver verbosity')
    print('  -a, --argument         pass an argument to myunit tasks')
    print('  --                     treat all remaning arguments as positional')
    print('  filter                 only include tasks matching filter')
    print('  -x, --exclude filter   exclude tasks matching filter')
    print('  -l, --list             list included tasks and exit')
    sys.exit(status)


def sanity() -> None:
    paths = os.getenv('PYTHONPATH')
    if paths is None:
        return
    failed = False
    for p in paths.split(os.pathsep):
        if not isabs(p):
            print('Relative PYTHONPATH entry %r' % p)
            failed = True
    if failed:
        print('Please use absolute so that chdir() tests can work.')
        print('Cowardly refusing to continue.')
        sys.exit(1)


def main() -> None:
    sanity()

    verbosity = 0
    whitelist = []  # type: List[str]
    blacklist = []  # type: List[str]
    arglist = []  # type: List[str]
    list_only = False

    allow_opts = True
    curlist = whitelist
    for a in sys.argv[1:]:
        if curlist is not arglist and allow_opts and a.startswith('-'):
            if curlist is not whitelist:
                break
            if a == '--':
                allow_opts = False
            elif a == '-v' or a == '--verbose':
                verbosity += 1
            elif a == '-q' or a == '--quiet':
                verbosity -= 1
            elif a == '-x' or a == '--exclude':
                curlist = blacklist
            elif a == '-a' or a == '--argument':
                curlist = arglist
            elif a == '-l' or a == '--list':
                list_only = True
            elif a == '-h' or a == '--help':
                usage(0)
            else:
                usage(1)
        else:
            curlist.append(a)
            curlist = whitelist
    if curlist is blacklist:
        sys.exit('-x must be followed by a filter')
    if curlist is arglist:
        sys.exit('-a must be followed by an argument')
    # empty string is a substring of all names
    if not whitelist:
        whitelist.append('')

    driver = Driver(whitelist=whitelist, blacklist=blacklist, arglist=arglist,
            verbosity=verbosity, xfail=[
                'run2 unittest mypy.codec.test.test_function_translation',
            ])
    driver.prepend_path('PATH', [join(driver.cwd, 'scripts')])
    driver.prepend_path('MYPYPATH', [driver.cwd])
    driver.prepend_path('PYTHONPATH', [driver.cwd])
    driver.prepend_path('PYTHONPATH', [join(driver.cwd, 'lib-typing', v) for v in driver.versions])

    for adder in [
            add_basic,
            add_myunit,
            add_imports,
            add_stubs,
            add_libpython,
            add_samples,
    ]:
        before = len(driver.waiter.queue)
        adder(driver)
        if whitelist == [''] and blacklist == []:
            assert len(driver.waiter.queue) != before, 'no tasks in %s' % adder.__name__

    if not list_only:
        driver.waiter.run()
    else:
        driver.list_tasks()


if __name__ == '__main__':
    main()
