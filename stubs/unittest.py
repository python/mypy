# Stubs for unittest

# Based on http://docs.python.org/3.0/library/unittest.html

# NOTE: These stubs are based on the 3.0 version API, since later versions
#       would require featurs not supported currently by mypy.

# Only a subset of functionality is included.

interface Testable:
    void run(self, TestResult result)
    void debug(self)
    int countTestCases(self)

# TODO interface for test runners?

class TestCase(Testable):
    void __init__(self, str methodName='runTest'): pass
    # TODO failureException
    void setUp(self): pass
    void tearDown(self): pass
    void run(self, TestResult result=None): pass
    void debug(self): pass
    void assert_(self, any expr, str msg=None): pass
    void failUnless(self, any expr, str msg=None): pass
    void assertTrue(self, any expr, str msg=None): pass
    void assertEqual(self, any first, any second, str msg=None): pass
    void failUnlessEqual(self, any first, any second, str msg=None): pass
    void assertNotEqual(self, any first, any second, str msg=None): pass
    void failIfEqual(self, any first, any second, str msg=None): pass
    void assertAlmostEqual(self, float first, float second, int places=7,
                           str msg=None): pass
    void failUnlessAlmostEqual(self, float first, float second, int places=7,
                               str msg=None): pass
    void assertNotAlmostEqual(self, float first, float second, int places=7,
                              str msg=None): pass
    void failIfAlmostEqual(self, float first, float second, int places=7,
                           str msg=None): pass
    void assertRaises(self, type exception, any callable, any *args): pass
    void failIf(self, any expr, str msg=None): pass
    void assertFalse(self, any expr, str msg=None): pass
    void fail(self, str msg=None): pass
    int countTestCases(self): pass
    TestResult defaultTestResult(self): pass
    str id(self): pass
    str shortDescription(self): pass # May return None

class FunctionTestCase(Testable):
    void __init__(self, func<void> testFunc, func<void> setUp=None,
                  func<void> tearDown=None, str description=None): pass
    void run(self, TestResult result): pass
    void debug(self): pass
    int countTestCases(self): pass

class TestSuite(Testable):
    void __init__(self, Iterable<Testable> tests=None): pass
    void addTest(self, Testable test): pass
    void addTests(self, Iterable<Testable> tests): pass
    void run(self, TestResult result): pass
    void debug(self): pass
    int countTestCases(self): pass

class TestResult:
    list<tuple<Testable, str>> errors
    list<tuple<Testable, str>> failures
    int testsRun
    bool shouldStop
    bool wasSuccessful(self): pass
    void stop(self): pass
    void startTest(self, Testable test): pass
    void stopTest(self, Testable test): pass
    void addError(self, Testable test,
                  tuple<type, any, any> err): pass # TODO
    void addFailure(self, Testable test,
                    tuple<type, any, any> err): pass # TODO
    void addSuccess(self, Testable test): pass

# TODO TestLoader
# TODO defaultTestLoader

class TextTestRunner:
    void __init__(self, TextIO stream=None, bool descriptions=True,
                  int verbosity=1): pass

void main(str module='__main__', str defaultTest=None, str[] argv=None,
          any testRunner=None, any testLoader=None): pass # TODO types
