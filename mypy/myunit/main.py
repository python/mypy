from typing import Callable, List, cast

import importlib
import sys

from mypy.myunit.suite import Suite
from mypy.myunit import ick
from mypy.myunit.run import run_test_recursive
from mypy.myunit import run


def add_suites_from_module(suites: List[Suite], mod_name: str) -> None:
    mod = importlib.import_module(mod_name)
    got_suite = False
    for suite in mod.__dict__.values():
        if isinstance(suite, type) and issubclass(suite, Suite) and suite is not Suite:
            got_suite = True
            suites.append(cast(Callable[[], Suite], suite)())
    if not got_suite:
        # Sanity check in case e.g. it uses unittest instead of a myunit.
        # The codecs tests do since they need to be python2-compatible.
        sys.exit('Test module %s had no test!' % mod_name)


class ListSuite(Suite):
    def __init__(self, suites: List[Suite]) -> None:
        for suite in suites:
            mod_name = type(suite).__module__.replace('.', '_')
            mod_name = mod_name.replace('mypy_', '')
            mod_name = mod_name.replace('test_', '')
            mod_name = mod_name.strip('_').replace('__', '_')
            type_name = type(suite).__name__
            name = 'test_%s_%s' % (mod_name, type_name)
            setattr(self, name, suite)
        super().__init__()


def main(args: List[str] = None) -> None:
    if not args:
        args = sys.argv[1:]
    run.is_verbose = False
    run.is_quiet = False
    suites = []  # type: List[Suite]
    run.patterns = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '-v':
            run.is_verbose = True
        elif a == '-q':
            run.is_quiet = True
        elif a == '-u':
            ick.APPEND_TESTCASES = '.new'
            ick.UPDATE_TESTCASES = True
        elif a == '-i':
            ick.APPEND_TESTCASES = ''
            ick.UPDATE_TESTCASES = True
        elif a == '-m':
            i += 1
            if i == len(args):
                sys.exit('-m requires an argument')
            add_suites_from_module(suites, args[i])
        elif not a.startswith('-'):
            run.patterns.append(a)
        else:
            sys.exit('Usage: python -m mypy.myunit [-v] [-q] [-u | -i]'
                    + ' -m test.module [-m test.module ...] [filter ...]')
        i += 1
    if len(run.patterns) == 0:
        run.patterns.append('*')
    if not suites:
        sys.exit('At least one -m argument is required')

    t = ListSuite(suites)
    num_total, num_fail, num_skip = run_test_recursive(t, 0, 0, 0, '', 0)

    skip_msg = ''
    if num_skip > 0:
        skip_msg = ', {} skipped'.format(num_skip)

    if num_fail == 0:
        if not run.is_quiet:
            print('%d test cases run%s, all passed.' % (num_total, skip_msg))
            print('*** OK ***')
    else:
        sys.stderr.write('%d/%d test cases failed%s.\n' % (num_fail,
                                                           num_total,
                                                           skip_msg))
        sys.stderr.write('*** FAILURE ***\n')
        sys.exit(1)
