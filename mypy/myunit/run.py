from typing import Any, List, Tuple, Union, cast

import sys
import traceback

from mypy.myunit.errors import SkipTestCaseException
from mypy.myunit.suite import Suite, TestCase, TestUnion, typename

# TODO remove global state
is_verbose = False
is_quiet = False
patterns = []  # type: List[str]


def run_test_recursive(test: Union[Suite, TestUnion],
                       num_total: int, num_fail: int, num_skip: int,
                       prefix: str, depth: int) -> Tuple[int, int, int]:
    if isinstance(test, TestCase):
        name = prefix + test.name
        for pattern in patterns:
            if match_pattern(name, pattern):
                match = True
                break
        else:
            match = False
        if match:
            is_fail, is_skip = run_single_test(name, test)
            if is_fail: num_fail += 1
            if is_skip: num_skip += 1
            num_total += 1
    else:
        suite = None  # type: Suite
        suite_prefix = ''
        if isinstance(test, tuple):
            suite_prefix, suite = cast(Tuple[str, Suite], test)
        else:
            suite = cast(Suite, test)
            suite_prefix = suite.prefix

        for stest in suite.cases():
            new_prefix = prefix
            if depth > 0:
                new_prefix = prefix + suite_prefix
            num_total, num_fail, num_skip = run_test_recursive(
                stest, num_total, num_fail, num_skip, new_prefix, depth + 1)
    return num_total, num_fail, num_skip


def run_single_test(name: str, test: TestCase) -> Tuple[bool, bool]:
    if is_verbose:
        sys.stderr.write(name)
        sys.stderr.flush()

    test.set_up()  # FIX: check exceptions
    exc_traceback = None  # type: Any
    try:
        test.run()
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
    test.tear_down()  # FIX: check exceptions

    if exc_traceback:
        if isinstance(exc_value, SkipTestCaseException):
            if is_verbose:
                sys.stderr.write(' (skipped)\n')
            return False, True
        else:
            handle_failure(name, exc_type, exc_value, exc_traceback)
            return True, False
    elif is_verbose:
        sys.stderr.write('\n')

    return False, False


def handle_failure(name, exc_type, exc_value, exc_traceback) -> None:
    # Report failed test case.
    if is_verbose:
        sys.stderr.write('\n\n')
    msg = ''
    if exc_value.args and exc_value.args[0]:
        msg = ': ' + str(exc_value)
    else:
        msg = ''
    sys.stderr.write('Traceback (most recent call last):\n')
    tb = traceback.format_tb(exc_traceback)
    tb = clean_traceback(tb)
    for s in tb:
        sys.stderr.write(s)
    exception = typename(exc_type)
    sys.stderr.write('{}{}\n\n'.format(exception, msg))
    sys.stderr.write('{} failed\n\n'.format(name))


def match_pattern(s: str, p: str) -> bool:
    if len(p) == 0:
        return len(s) == 0
    elif p[0] == '*':
        if len(p) == 1:
            return True
        else:
            for i in range(len(s) + 1):
                if match_pattern(s[i:], p[1:]):
                    return True
            return False
    elif len(s) == 0:
        return False
    else:
        return s[0] == p[0] and match_pattern(s[1:], p[1:])


def clean_traceback(tb: List[str]) -> List[str]:
    # Remove clutter from the traceback.
    start = 0
    for i, s in enumerate(tb):
        if '\n    test.run()\n' in s or '\n    self.func()\n' in s:
            start = i + 1
    tb = tb[start:]
    for f in ['assert_equal', 'assert_not_equal', 'assert_type',
              'assert_raises', 'assert_true']:
        if tb != [] and ', in {}\n'.format(f) in tb[-1]:
            tb = tb[:-1]
    return tb
