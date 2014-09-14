# Stubs for unittest

# Based on http://docs.python.org/3.0/library/unittest.html

# NOTE: These stubs are based on the 3.0 version API, since later versions
#       would require featurs not supported currently by mypy.

# Only a subset of functionality is included.

from typing import (
    Any, Function, Iterable, Undefined, Tuple, List, TextIO, Sequence,
    overload, typevar, Pattern
)
from abc import abstractmethod, ABCMeta

_T = typevar('_T')
_FT = typevar('_FT')

class Testable(metaclass=ABCMeta):
    @abstractmethod
    def run(self, result: 'TestResult') -> None: pass
    @abstractmethod
    def debug(self) -> None: pass
    @abstractmethod
    def countTestCases(self) -> int: pass

# TODO ABC for test runners?

class TestResult:
    errors = Undefined(List[Tuple[Testable, str]])
    failures = Undefined(List[Tuple[Testable, str]])
    testsRun = 0
    shouldStop = False

    def wasSuccessful(self) -> bool: pass
    def stop(self) -> None: pass
    def startTest(self, test: Testable) -> None: pass
    def stopTest(self, test: Testable) -> None: pass
    def addError(self, test: Testable,
                  err: Tuple[type, Any, Any]) -> None: pass # TODO
    def addFailure(self, test: Testable,
                    err: Tuple[type, Any, Any]) -> None: pass # TODO
    def addSuccess(self, test: Testable) -> None: pass

class _AssertRaisesBaseContext:
    expected = Undefined(Any)
    failureException = Undefined(type)
    obj_name = ''
    expected_regex = Undefined(Pattern[str])

class _AssertRaisesContext(_AssertRaisesBaseContext):
    exception = Undefined(Any) # TODO precise type
    def __enter__(self) -> _AssertRaisesContext: pass
    def __exit__(self, exc_type, exc_value, tb) -> bool: pass

class _AssertWarnsContext(_AssertRaisesBaseContext):
    warning = Undefined(Any) # TODO precise type
    filename = ''
    lineno = 0
    def __enter__(self) -> _AssertWarnsContext: pass
    def __exit__(self, exc_type, exc_value, tb) -> bool: pass

class TestCase(Testable):
    def __init__(self, methodName: str = 'runTest') -> None: pass
    # TODO failureException
    def setUp(self) -> None: pass
    def tearDown(self) -> None: pass
    def run(self, result: TestResult = None) -> None: pass
    def debug(self) -> None: pass
    def assert_(self, expr: Any, msg: object = None) -> None: pass
    def failUnless(self, expr: Any, msg: object = None) -> None: pass
    def assertTrue(self, expr: Any, msg: object = None) -> None: pass
    def assertEqual(self, first: Any, second: Any,
                    msg: object = None) -> None: pass
    def failUnlessEqual(self, first: Any, second: Any,
                        msg: object = None) -> None: pass
    def assertNotEqual(self, first: Any, second: Any,
                       msg: object = None) -> None: pass
    def assertSequenceEqual(self, first: Sequence[Any], second: Sequence[Any],
                            msg: object = None,
                            seq_type: type = None) -> None: pass
    def failIfEqual(self, first: Any, second: Any,
                    msg: object = None) -> None: pass
    def assertAlmostEqual(self, first: float, second: float, places: int = 7,
                          msg: object = None,
                          delta: float = None) -> None: pass
    def failUnlessAlmostEqual(self, first: float, second: float,
                              places: int = 7,
                              msg: object = None) -> None: pass
    def assertNotAlmostEqual(self, first: float, second: float,
                             places: int = 7, msg: object = None,
                             delta: float = None) -> None: pass
    def failIfAlmostEqual(self, first: float, second: float, places: int = 7,
                          msg: object = None) -> None: pass
    def assertGreater(self, first: Any, second: Any,
                      msg: object = None) -> None: pass
    def assertGreaterEqual(self, first: Any, second: Any,
                      msg: object = None) -> None: pass
    def assertLess(self, first: Any, second: Any,
                   msg: object = None) -> None: pass
    def assertLessEqual(self, first: Any, second: Any,
                        msg: object = None) -> None: pass
    # TODO: If callableObj is None, the return value is None.
    def assertRaises(self, excClass: type, callableObj: Any = None,
                     *args: Any, **kwargs: Any) -> _AssertRaisesContext: pass
    def failIf(self, expr: Any, msg: object = None) -> None: pass
    def assertFalse(self, expr: Any, msg: object = None) -> None: pass
    def assertIs(self, first: object, second: object,
                 msg: object = None) -> None: pass
    def assertIsNot(self, first: object, second: object,
                    msg: object = None) -> None: pass
    def assertIsNone(self, expr: Any, msg: object = None) -> None: pass
    def assertIsNotNone(self, expr: Any, msg: object = None) -> None: pass
    def assertIn(self, first: _T, second: Iterable[_T],
                 msg: object = None) -> None: pass
    def assertNotIn(self, first: _T, second: Iterable[_T],
                    msg: object = None) -> None: pass
    def assertIsInstance(self, obj: Any, cls: type,
                         msg: object = None) -> None: pass
    def assertNotIsInstance(self, obj: Any, cls: type,
                            msg: object = None) -> None: pass
    def assertWarns(self, expected_warning: type, callable_obj: Any = None,
                    *args: Any, **kwargs: Any) -> _AssertWarnsContext: pass
    def fail(self, msg: object = None) -> None: pass
    def countTestCases(self) -> int: pass
    def defaultTestResult(self) -> TestResult: pass
    def id(self) -> str: pass
    def shortDescription(self) -> str: pass # May return None
    def addCleanup(function: Any, *args: Any, **kwargs: Any) -> None: pass
    def skipTest(self, reason: Any) -> None: pass

class FunctionTestCase(Testable):
    def __init__(self, testFunc: Function[[], None],
                 setUp: Function[[], None] = None,
                 tearDown: Function[[], None] = None,
                 description: str = None) -> None: pass
    def run(self, result: TestResult) -> None: pass
    def debug(self) -> None: pass
    def countTestCases(self) -> int: pass

class TestSuite(Testable):
    def __init__(self, tests: Iterable[Testable] = None) -> None: pass
    def addTest(self, test: Testable) -> None: pass
    def addTests(self, tests: Iterable[Testable]) -> None: pass
    def run(self, result: TestResult) -> None: pass
    def debug(self) -> None: pass
    def countTestCases(self) -> int: pass

# TODO TestLoader
# TODO defaultTestLoader

class TextTestRunner:
    def __init__(self, stream: TextIO = None, descriptions: bool = True,
                 verbosity: int = 1, failfast: bool = False) -> None: pass

class SkipTest(Exception):
    pass

# TODO precise types
def skipUnless(condition: Any, reason: str) -> Any: pass
def skipIf(condition: Any, reason: str) -> Any: pass
def expectedFailure(func: _FT) -> _FT: pass
def skip(reason: str) -> Any: pass

def main(module: str = '__main__', defaultTest: str = None,
         argv: List[str] = None, testRunner: Any = None,
         testLoader: Any = None) -> None: pass # TODO types
