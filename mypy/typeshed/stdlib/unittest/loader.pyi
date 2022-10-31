import unittest.case
import unittest.suite
from collections.abc import Callable, Sequence
from re import Pattern
from types import ModuleType
from typing import Any
from typing_extensions import TypeAlias

_SortComparisonMethod: TypeAlias = Callable[[str, str], int]
_SuiteClass: TypeAlias = Callable[[list[unittest.case.TestCase]], unittest.suite.TestSuite]

VALID_MODULE_NAME: Pattern[str]

class TestLoader:
    errors: list[type[BaseException]]
    testMethodPrefix: str
    sortTestMethodsUsing: _SortComparisonMethod
    testNamePatterns: list[str] | None
    suiteClass: _SuiteClass
    def loadTestsFromTestCase(self, testCaseClass: type[unittest.case.TestCase]) -> unittest.suite.TestSuite: ...
    def loadTestsFromModule(self, module: ModuleType, *args: Any, pattern: Any = ...) -> unittest.suite.TestSuite: ...
    def loadTestsFromName(self, name: str, module: ModuleType | None = ...) -> unittest.suite.TestSuite: ...
    def loadTestsFromNames(self, names: Sequence[str], module: ModuleType | None = ...) -> unittest.suite.TestSuite: ...
    def getTestCaseNames(self, testCaseClass: type[unittest.case.TestCase]) -> Sequence[str]: ...
    def discover(self, start_dir: str, pattern: str = ..., top_level_dir: str | None = ...) -> unittest.suite.TestSuite: ...
    def _match_path(self, path: str, full_path: str, pattern: str) -> bool: ...

defaultTestLoader: TestLoader

def getTestCaseNames(
    testCaseClass: type[unittest.case.TestCase],
    prefix: str,
    sortUsing: _SortComparisonMethod = ...,
    testNamePatterns: list[str] | None = ...,
) -> Sequence[str]: ...
def makeSuite(
    testCaseClass: type[unittest.case.TestCase],
    prefix: str = ...,
    sortUsing: _SortComparisonMethod = ...,
    suiteClass: _SuiteClass = ...,
) -> unittest.suite.TestSuite: ...
def findTestCases(
    module: ModuleType, prefix: str = ..., sortUsing: _SortComparisonMethod = ..., suiteClass: _SuiteClass = ...
) -> unittest.suite.TestSuite: ...
