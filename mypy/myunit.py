import sys
import re
import time
import traceback

from typing import List, Tuple, Any, Function, overload, Undefined


# TODO remove global state
is_verbose = False
is_quiet = False
patterns = List[str]()
times = List[Tuple[float, str]]()


class AssertionFailure(Exception):
    """Exception used to signal skipped test cases."""
    def __init__(self, s: str = None) -> None:
        if s:
            super().__init__(s)
        else:
            super().__init__()


class SkipTestCaseException(Exception): pass


def assert_true(b: bool, msg: str = None) -> None:
    if not b:
        raise AssertionFailure(msg)


def assert_false(b: bool, msg: str = None) -> None:
    if b:
        raise AssertionFailure(msg)


def assert_equal(a: object, b: object, fmt: str = '{} != {}') -> None:
    if a != b:
        raise AssertionFailure(fmt.format(repr(a), repr(b)))


def assert_not_equal(a: object, b: object, fmt: str = '{} == {}') -> None:
    if a == b:
        raise AssertionFailure(fmt.format(repr(a), repr(b)))


def assert_raises(typ: type, *rest: Any) -> None:
    """Usage: assert_raises(exception class[, message], function[, args])

    Call function with the given arguments and expect an exception of the given
    type.

    TODO use overloads for better type checking
    """
    # Parse arguments.
    msg = None  # type: str
    if isinstance(rest[0], str) or rest[0] is None:
        msg = rest[0]
        rest = rest[1:]
    f = rest[0]
    args = []  # type: List[Any]
    if len(rest) > 1:
        args = rest[1]
        assert len(rest) <= 2

    # Perform call and verify the exception.
    try:
        f(*args)
    except Exception as e:
        assert_type(typ, e)
        if msg:
            assert_equal(e.args[0], msg, 'Invalid message {}, expected {}')
    else:
        raise AssertionFailure('No exception raised')


def assert_type(typ: type, value: object) -> None:
    if type(value) != typ:
        raise AssertionFailure('Invalid type {}, expected {}'.format(
            typename(type(value)), typename(typ)))


def fail() -> None:
    raise AssertionFailure()


class TestCase:
    def __init__(self, name: str, suite: 'Suite' = None,
                 func: Function[[], None] = None) -> None:
        self.func = func
        self.name = name
        self.suite = suite

    def run(self) -> None:
        if self.func:
            self.func()

    def set_up(self) -> None:
        if self.suite:
            self.suite.set_up()

    def tear_down(self) -> None:
        if self.suite:
            self.suite.tear_down()


class Suite:
    def __init__(self) -> None:
        self.prefix = typename(type(self)) + '.'
        # Each test case is either a TestCase object or (str, function).
        self._test_cases = []  # type: List[Any]
        self.init()

    def set_up(self) -> None:
        pass

    def tear_down(self) -> None:
        pass

    def init(self) -> None:
        for m in dir(self):
            if m.startswith('test'):
                t = getattr(self, m)
                if isinstance(t, Suite):
                    self.add_test((m + '.', t))
                else:
                    self.add_test(TestCase(m, self, getattr(self, m)))

    @overload
    def add_test(self, test: TestCase) -> None:
        self._test_cases.append(test)

    @overload
    def add_test(self, test: Tuple[str, Function[[], None]]) -> None:
        self._test_cases.append(test)

    @overload
    def add_test(self, test: Tuple[str, 'Suite']) -> None:
        self._test_cases.append(test)

    def cases(self) -> List[Any]:
        return self._test_cases[:]

    def skip(self) -> None:
        raise SkipTestCaseException()


def run_test(t: Suite, args: List[str] = None) -> None:
    global patterns, is_verbose, is_quiet
    if not args:
        args = []
    is_verbose = False
    is_quiet = False
    patterns = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '-v':
            is_verbose = True
        elif a == '-q':
            is_quiet = True
        # Used for updating tests, but breaks clean code usage.
        elif a in ('-u', '-i'):
            pass
        elif len(a) > 0 and a[0] != '-':
            patterns.append(a)
        else:
            raise ValueError('Invalid arguments')
        i += 1
    if len(patterns) == 0:
        patterns.append('*')

    num_total, num_fail, num_skip = run_test_recursive(t, 0, 0, 0, '', 0)

    skip_msg = ''
    if num_skip > 0:
        skip_msg = ', {} skipped'.format(num_skip)

    if num_fail == 0:
        if not is_quiet:
            print('%d test cases run%s, all passed.' % (num_total, skip_msg))
            print('*** OK ***')
    else:
        sys.stderr.write('%d/%d test cases failed%s.\n' % (num_fail,
                                                           num_total,
                                                           skip_msg))
        sys.stderr.write('*** FAILURE ***\n')
        sys.exit(1)


def run_test_recursive(test: Any, num_total: int, num_fail: int, num_skip: int,
                       prefix: str, depth: int) -> Tuple[int, int, int]:
    """The first argument may be TestCase, Suite or (str, Suite)."""
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
        suite = Undefined  # type: Suite
        suite_prefix = ''
        if isinstance(test, list) or isinstance(test, tuple):
            suite = test[1]
            suite_prefix = test[0]
        else:
            suite = test
            suite_prefix = test.prefix

        for stest in suite.cases():
            new_prefix = prefix
            if depth > 0:
                new_prefix = prefix + suite_prefix
            num_total, num_fail, num_skip = run_test_recursive(
                stest, num_total, num_fail, num_skip, new_prefix, depth + 1)
    return num_total, num_fail, num_skip


def run_single_test(name: str, test: Any) -> Tuple[bool, bool]:
    if is_verbose:
        sys.stderr.write(name)
        sys.stderr.flush()

    time0 = time.time()
    test.set_up()  # FIX: check exceptions
    exc_traceback = None  # type: Any
    try:
        test.run()
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
    test.tear_down()  # FIX: check exceptions
    times.append((time.time() - time0, name))

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


def typename(t: type) -> str:
    if '.' in str(t):
        return str(t).split('.')[-1].rstrip("'>")
    else:
        return str(t)[8:-2]


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
