import sys
import re
import time
import traceback


bool is_verbose
bool is_quiet
list<str> patterns
list<tuple<float, str>> times = []


class AssertionFailure(Exception):
    void __init__(self, str s=None):
        if s:
            super().__init__(s)
        else:
            super().__init__()


# Exception used to signal skipped test cases.
class SkipTestCaseException(Exception): pass


void assertTrue(bool b, str msg=None):
    if not b:
        raise AssertionFailure(msg)


void assert_equal(object a, object b, str fmt='{} != {}'):
    if a != b:
        raise AssertionFailure(fmt.format(repr(a), repr(b)))


void assertNotEqual(object a, object b, str fmt='{} == {}'):
    if a == b:
        raise AssertionFailure(fmt.format(repr(a), repr(b)))


# Usage: AssertRaises(exception class[, message], function[, args])
#
# Call function with the given arguments and expect an exception of the given
# type.
#
# FIX: The type is probably too complex to be supported...
void assertRaises(type typ, any *rest):
    # Parse arguments.
    str msg = None
    if isinstance(rest[0], str) or rest[0] is None:
        msg = rest[0]
        rest = rest[1:]
    f = rest[0]
    args = <any> []
    if len(rest) > 1:
        args = rest[1]
        if len(rest) > 2:
            raise ValueError('Too many arguments')
    
    # Perform call and verify the exception.
    try:
        f(*args)
    except Exception as e:
        assertType(typ, e)
        if msg:
            assert_equal(e.args[0], msg, 'Invalid message {}, expected {}')
        return 
    assertTrue(False, 'No exception raised')


void assertType(type typ, object value):
    if type(value) != typ:
        raise AssertionFailure('Invalid type {}, expected {}'.format(
            type(value), typ))


void fail():
    raise AssertionFailure()


class TestCase:
    str name    
    func<void> func
    Suite suite
    
    void __init__(self, str name, Suite suite=None, func<void> func=None):
        self.func = func
        self.name = name
        self.suite = suite
    
    void run(self):
        if self.func:
            self.func()
    
    void set_up(self):
        if self.suite:
            self.suite.set_up()
    
    void tear_down(self):
        if self.suite:
            self.suite.tear_down()


class Suite:
    list<any> test_cases = [] # TestCase or (Str, func)
    str prefix
    
    void __init__(self):
        self.prefix = unqualify_name(str(type(self))) + '.'
        self.init()
    
    void set_up(self):
        pass
    
    void tear_down(self):
        pass
    
    void init(self):
        for m in dir(self):
            if m.startswith('test'):
                t = getattr(self, m)
                if isinstance(t, Suite):
                    self.add_test((m + '.', t))
                else:
                    self.add_test(TestCase(m, self, getattr(self, m)))
    
    void add_test(self, TestCase test):
        self.test_cases.append(test)
    
    void add_test(self, tuple<str, func<void>> test):
        self.test_cases.append(test)
    
    list<any> cases(self):
        return self.test_cases[:]
    
    void skip(self):
        raise SkipTestCaseException()


void run_test(Suite t, list<str> args=None):
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
            print(num_total, ' test cases run', skip_msg, ', all passed.')
            print('*** OK ***')
    else:
        sys.stderr.write('%d/%d test cases failed%s.\n' % (num_fail,
                                                           num_total,
                                                           skip_msg))
        sys.stderr.write('*** FAILURE ***\n')


# The first argument may be TestCase, Suite or (Str, Suite).
tuple<int, int, int> run_test_recursive(any t, int num_total, int num_fail,
                                        int num_skip, str prefix, int depth):
    if isinstance(t, TestCase):
        name = prefix + t.name
        
        match = False
        for p in patterns:
            if match_pattern(name, p):
                match = True
                break
        
        if match:
            if is_verbose:
                sys.stderr.write(name)
            
            t1 = time.time()
            t.set_up() # FIX: check exceptions
            try:
                t.run()
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
            else:
                exc_traceback = None
            t.tear_down() # FIX: check exceptions
            times.append((time.time() - t1, name))
            
            if exc_traceback:
                tb = traceback.format_tb(exc_traceback)
                if isinstance(exc_value, SkipTestCaseException):
                    num_skip += 1
                    if is_verbose:
                        sys.stderr.write(' (skipped)\n')
                else:
                    # Failed test case.
                    if is_verbose:
                        sys.stderr.write('\n\n')
                    str msg
                    if exc_value.args[0]:
                        msg = ': ' + exc_value.args[0]
                    else:
                        msg = ''
                    sys.stderr.write(
                        'Traceback (most recent call last):\n')
                    tb = clean_traceback(tb)
                    for s in reversed(tb):
                        sys.stderr.write('  ' + s + '\n')
                    type = re.sub(str(exc_type), '^unittest::', '')
                    sys.stderr.write('{}{}\n\n'.format(type, msg))
                    sys.stderr.write('{} failed\n\n'.format(name))
                    num_fail += 1
            elif is_verbose:
                sys.stderr.write('\n')
            num_total += 1
    else:
        Suite suite
        str suite_prefix
        if isinstance(t, list) or isinstance(t, tuple):
            suite = t[1]
            suite_prefix = t[0]
        else:
            suite = t
            suite_prefix = t.prefix
        
        for tt in suite.cases():
            new_prefix = prefix
            if depth > 0:
                new_prefix = prefix + suite_prefix
            num_total, num_fail, num_skip = run_test_recursive(
                tt, num_total, num_fail, num_skip, new_prefix, depth + 1)
    return num_total, num_fail, num_skip


str unqualify_name(str s):
    beg_index = 0
    for i in range(len(s)):
        if s[i] == ':':
            beg_index = i + 1
    return s[beg_index:]


bool match_pattern(str s, str p):
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


list<str> clean_traceback(list<str> tb):
    # Remove clutter from the traceback.
    if tb != [] and tb[-1].find('run of unittest::TestCase') >= 0:
        tb = tb[:-1]
    for f in ['Assert', 'AssertEqual', 'AssertNotEqual', 'AssertRaises',
              'AssertType']:
        if tb != [] and tb[0].find('unittest::{}'.format(f)) >= 0:
            tb = tb[1:]
    return tb
