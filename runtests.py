#!/usr/bin/env python3
"""Mypy test runner."""

from typing import Dict, List, Optional, Set, Iterable, Tuple

from mypy.waiter import Waiter, LazySubprocess
from mypy import util

import itertools
import os
from os.path import join, isdir
import sys


def get_versions():  # type: () -> List[str]
    major = sys.version_info[0]
    minor = sys.version_info[1]
    if major == 2:
        return ['2.7']
    else:
        # generates list of python versions to use.
        # For Python2, this is only [2.7].
        # Otherwise, it is [3.4, 3.3, 3.2, 3.1, 3.0].
        return ['%d.%d' % (major, i) for i in range(minor, -1, -1)]


# Ideally, all tests would be `discover`able so that they can be driven
# (and parallelized) by an external test driver.

class Driver:

    def __init__(self, *, whitelist: List[str], blacklist: List[str],
            lf: bool, ff: bool,
            arglist: List[str], pyt_arglist: List[str],
            verbosity: int, parallel_limit: int,
            xfail: List[str], coverage: bool) -> None:
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.arglist = arglist
        self.pyt_arglist = pyt_arglist
        self.verbosity = verbosity
        self.waiter = Waiter(verbosity=verbosity, limit=parallel_limit, xfail=xfail, lf=lf, ff=ff)
        self.versions = get_versions()
        self.cwd = os.getcwd()
        self.mypy = os.path.join(self.cwd, 'scripts', 'mypy')
        self.env = dict(os.environ)
        self.coverage = coverage

    def prepend_path(self, name: str, paths: List[str]) -> None:
        old_val = self.env.get(name)
        paths = [p for p in paths if isdir(p)]
        if not paths:
            return
        if old_val is not None:
            new_val = os.pathsep.join(itertools.chain(paths, [old_val]))
        else:
            new_val = os.pathsep.join(paths)
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

    def add_mypy_cmd(self, name: str, mypy_args: List[str], cwd: Optional[str] = None) -> None:
        full_name = 'check %s' % name
        if not self.allow(full_name):
            return
        args = [sys.executable, self.mypy] + mypy_args
        args.append('--show-traceback')
        self.waiter.add(LazySubprocess(full_name, args, cwd=cwd, env=self.env))

    def add_mypy(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        self.add_mypy_cmd(name, list(args), cwd=cwd)

    def add_mypy_modules(self, name: str, modules: Iterable[str],
                         cwd: Optional[str] = None) -> None:
        args = list(itertools.chain(*(['-m', mod] for mod in modules)))
        self.add_mypy_cmd(name, args, cwd=cwd)

    def add_mypy_package(self, name: str, packagename: str, *flags: str) -> None:
        self.add_mypy_cmd(name, ['-p', packagename] + list(flags))

    def add_mypy_string(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        self.add_mypy_cmd(name, ['-c'] + list(args), cwd=cwd)

    def add_pytest(self, files: List[Tuple[str, str]], coverage: bool = True) -> None:
        pytest_files = [name for kind, name in files
                        if self.allow('pytest {} {}'.format(kind, name))]
        if not pytest_files:
            return
        pytest_args = pytest_files + self.arglist + self.pyt_arglist
        if coverage and self.coverage:
            args = [sys.executable, '-m', 'pytest', '--cov=mypy'] + pytest_args
        else:
            args = [sys.executable, '-m', 'pytest'] + pytest_args

        self.waiter.add(LazySubprocess('pytest', args, env=self.env,
                                       passthrough=self.verbosity),
                        sequential=True)

    def add_python(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'run %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        largs[0:0] = [sys.executable]
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_python_mod(self, name: str, *args: str, cwd: Optional[str] = None,
                       coverage: bool = False) -> None:
        name = 'run %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        if coverage and self.coverage:
            largs[0:0] = ['coverage', 'run', '-m']
        else:
            largs[0:0] = [sys.executable, '-m']
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

    def add_python2(self, name: str, *args: str, cwd: Optional[str] = None) -> None:
        name = 'run2 %s' % name
        if not self.allow(name):
            return
        largs = list(args)
        python2 = util.try_find_python2_interpreter()
        assert python2, "Couldn't find a Python 2.7 interpreter"
        largs[0:0] = [python2]
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def add_flake8(self, cwd: Optional[str] = None) -> None:
        name = 'lint'
        if not self.allow(name):
            return
        largs = ['flake8', '-j0']
        env = self.env
        self.waiter.add(LazySubprocess(name, largs, cwd=cwd, env=env))

    def list_tasks(self) -> None:
        for id, task in enumerate(self.waiter.queue):
            print('{id}:{task}'.format(id=id, task=task.name))


def add_basic(driver: Driver) -> None:
    if False:
        driver.add_mypy('file setup.py', 'setup.py')
    driver.add_mypy('file runtests.py', 'runtests.py')
    driver.add_mypy('legacy entry script', 'scripts/mypy')
    driver.add_mypy('legacy myunit script', 'scripts/myunit')
    # needs typed_ast installed:
    driver.add_mypy('fast-parse', '--fast-parse', 'test-data/samples/hello.py')


def add_selftypecheck(driver: Driver) -> None:
    driver.add_mypy_package('package mypy', 'mypy', '--config-file', 'mypy_self_check.ini')


def find_files(base: str, prefix: str = '', suffix: str = '') -> List[str]:
    return [join(root, f)
            for root, dirs, files in os.walk(base)
            for f in files
            if f.startswith(prefix) and f.endswith(suffix)]


def file_to_module(file: str) -> str:
    rv = os.path.splitext(file)[0].replace(os.sep, '.')
    if rv.endswith('.__init__'):
        rv = rv[:-len('.__init__')]
    return rv


def add_imports(driver: Driver) -> None:
    # Make sure each module can be imported originally.
    # There is currently a bug in mypy where a module can pass typecheck
    # because of *implicit* imports from other modules.
    for f in find_files('mypy', suffix='.py'):
        mod = file_to_module(f)
        if not mod.endswith('.__main__'):
            driver.add_python_string('import %s' % mod, 'import %s' % mod)


def test_path(*names: str):
    return [os.path.join('mypy', 'test', '{}.py'.format(name))
            for name in names]


PYTEST_FILES = test_path(
    'testcheck',
    'testdmypy',
    'testextensions',
    'testdeps',
    'testdiff',
    'testfinegrained',
    'testmerge',
    'testtransform',
    'testtypegen',
    'testparse',
    'testsemanal'
)

SLOW_FILES = test_path(
    'testpythoneval',
    'testcmdline',
    'teststubgen',
)

MYUNIT_FILES = test_path(
    'teststubgen',
    'testargs',
    'testgraph',
    'testinfer',
    'testmoduleinfo',
    'testreports',
    'testsolve',
    'testsubtypes',
    'testtypes',
)

for f in find_files('mypy', prefix='test', suffix='.py'):
    assert f in PYTEST_FILES + SLOW_FILES + MYUNIT_FILES, f


def add_pytest(driver: Driver) -> None:
    driver.add_pytest([('unit-test', name) for name in PYTEST_FILES] +
                      [('integration', name) for name in SLOW_FILES])


def add_myunit(driver: Driver) -> None:
    for f in MYUNIT_FILES:
        mod = file_to_module(f)
        driver.add_python_mod('myunit unit-test %s' % mod, 'mypy.myunit', '-m', mod,
                              *driver.arglist, coverage=True)


def add_stubs(driver: Driver) -> None:
    # We only test each module in the one version mypy prefers to find.
    # TODO: test stubs for other versions, especially Python 2 stubs.

    modules = set()  # type: Set[str]
    modules.add('typing')
    # TODO: This should also test Python 2, and pass pyversion accordingly.
    for version in ["2and3", "3", "3.3", "3.4", "3.5"]:
        for stub_type in ['builtins', 'stdlib', 'third_party']:
            stubdir = join('typeshed', stub_type, version)
            for f in find_files(stubdir, suffix='.pyi'):
                module = file_to_module(f[len(stubdir) + 1:])
                modules.add(module)

    driver.add_mypy_modules('stubs', sorted(modules))


def add_stdlibsamples(driver: Driver) -> None:
    seen = set()  # type: Set[str]
    for version in driver.versions:
        stdlibsamples_dir = join(driver.cwd, 'test-data', 'stdlib-samples', version)
        modules = []  # type: List[str]
        for f in find_files(stdlibsamples_dir, prefix='test_', suffix='.py'):
            module = file_to_module(f[len(stdlibsamples_dir) + 1:])
            if module not in seen:
                seen.add(module)
                modules.append(module)
        if modules:
            driver.add_mypy_modules('stdlibsamples (%s)' % (version,), modules,
                                    cwd=stdlibsamples_dir)


def add_samples(driver: Driver) -> None:
    for f in find_files(os.path.join('test-data', 'samples'), suffix='.py'):
        driver.add_mypy('file %s' % f, f)


def usage(status: int) -> None:
    print('Usage: %s [-h | -v | -q | --lf | --ff | [-x] FILTER | -a ARG | -p ARG]'
          '... [-- FILTER ...]'
          % sys.argv[0])
    print()
    print('Run mypy tests. If given no arguments, run all tests.')
    print()
    print('Examples:')
    print('  %s unit-test  (run unit tests only)' % sys.argv[0])
    print('  %s testcheck  (run type checking unit tests only)' % sys.argv[0])
    print('  %s "pytest unit-test" -a -k -a Tuple' % sys.argv[0])
    print('       (run all pytest unit tests with "Tuple" in test name)')
    print()
    print('You can also run pytest directly without using %s:' % sys.argv[0])
    print('  pytest mypy/test/testcheck.py -k Tuple')
    print()
    print('Options:')
    print('  -h, --help             show this help')
    print('  -v, --verbose          increase driver verbosity')
    print('  --lf                   rerun only the tests that failed at the last run')
    print('  --ff                   run all tests but run the last failures first')
    print('  -q, --quiet            decrease driver verbosity')
    print('  -jN                    run N tasks at once (default: one per CPU)')
    print('  -a, --argument ARG     pass an argument to myunit tasks')
    print('  -p, --pytest_arg ARG   pass an argument to pytest tasks')
    print('                         (-v: verbose; glob pattern: filter by test name)')
    print('  -l, --list             list included tasks (after filtering) and exit')
    print('  FILTER                 include tasks matching FILTER')
    print('  -x, --exclude FILTER   exclude tasks matching FILTER')
    print('  -c, --coverage         calculate code coverage while running tests')
    print('  --                     treat all remaining arguments as positional')
    sys.exit(status)


def sanity() -> None:
    paths = os.getenv('PYTHONPATH')
    if paths is None:
        return
    failed = False
    for p in paths.split(os.pathsep):
        if not os.path.isabs(p):
            print('Relative PYTHONPATH entry %r' % p)
            failed = True
    if failed:
        print('Please use absolute so that chdir() tests can work.')
        print('Cowardly refusing to continue.')
        sys.exit(1)


def main() -> None:
    import time
    t0 = time.perf_counter()
    sanity()

    verbosity = 0
    parallel_limit = 0
    whitelist = []  # type: List[str]
    blacklist = []  # type: List[str]
    arglist = []  # type: List[str]
    pyt_arglist = []  # type: List[str]
    lf = False
    ff = False
    list_only = False
    coverage = False

    allow_opts = True
    curlist = whitelist
    for a in sys.argv[1:]:
        if not (curlist is arglist or curlist is pyt_arglist) and allow_opts and a.startswith('-'):
            if curlist is not whitelist:
                break
            if a == '--':
                allow_opts = False
            elif a == '-v' or a == '--verbose':
                verbosity += 1
            elif a == '-q' or a == '--quiet':
                verbosity -= 1
            elif a.startswith('-j'):
                try:
                    parallel_limit = int(a[2:])
                except ValueError:
                    usage(1)
            elif a == '-x' or a == '--exclude':
                curlist = blacklist
            elif a == '-a' or a == '--argument':
                curlist = arglist
            elif a == '-p' or a == '--pytest_arg':
                curlist = pyt_arglist
            # will also pass this option to pytest
            elif a == '--lf':
                lf = True
            # will also pass this option to pytest
            elif a == '--ff':
                ff = True
            elif a == '-l' or a == '--list':
                list_only = True
            elif a == '-c' or a == '--coverage':
                coverage = True
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
    if curlist is pyt_arglist:
        sys.exit('-p must be followed by an argument')
    if lf and ff:
        sys.exit('use either --lf or --ff, not both')
    # empty string is a substring of all names
    if not whitelist:
        whitelist.append('')
    if lf:
        pyt_arglist.append('--lf')
    if ff:
        pyt_arglist.append('--ff')
    if verbosity >= 1:
        pyt_arglist.extend(['-v'] * verbosity)
    elif verbosity < 0:
        pyt_arglist.extend(['-q'] * (-verbosity))
    if parallel_limit:
        if '-n' not in pyt_arglist:
            pyt_arglist.append('-n{}'.format(parallel_limit))

    driver = Driver(whitelist=whitelist, blacklist=blacklist, lf=lf, ff=ff,
                    arglist=arglist, pyt_arglist=pyt_arglist, verbosity=verbosity,
                    parallel_limit=parallel_limit, xfail=[], coverage=coverage)

    driver.prepend_path('PATH', [join(driver.cwd, 'scripts')])
    driver.prepend_path('MYPYPATH', [driver.cwd])
    driver.prepend_path('PYTHONPATH', [driver.cwd])

    driver.add_flake8()
    add_pytest(driver)
    add_basic(driver)
    add_selftypecheck(driver)
    add_myunit(driver)
    add_imports(driver)
    add_stubs(driver)
    add_stdlibsamples(driver)
    add_samples(driver)

    if list_only:
        driver.list_tasks()
        return

    exit_code = driver.waiter.run()
    t1 = time.perf_counter()
    print('total runtime:', t1 - t0, 'sec')

    if verbosity >= 1:
        times = driver.waiter.times2 if verbosity >= 2 else driver.waiter.times1
        times_sortable = ((t, tp) for (tp, t) in times.items())
        for total_time, test_type in sorted(times_sortable, reverse=True):
            print('total time in %s: %f' % (test_type, total_time))

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
