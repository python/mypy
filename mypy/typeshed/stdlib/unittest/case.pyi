import logging
import sys
import unittest.result
from _typeshed import Self, SupportsDunderGE, SupportsDunderGT, SupportsDunderLE, SupportsDunderLT, SupportsRSub, SupportsSub
from collections.abc import Callable, Container, Iterable, Mapping, Sequence, Set as AbstractSet
from contextlib import AbstractContextManager
from re import Pattern
from types import TracebackType
from typing import (
    Any,
    AnyStr,
    ClassVar,
    Generic,
    NamedTuple,
    NoReturn,
    Protocol,
    SupportsAbs,
    SupportsRound,
    TypeVar,
    Union,
    overload,
)
from typing_extensions import ParamSpec, TypeAlias
from warnings import WarningMessage

if sys.version_info >= (3, 9):
    from types import GenericAlias

if sys.version_info >= (3, 10):
    from types import UnionType

_T = TypeVar("_T")
_S = TypeVar("_S", bound=SupportsSub[Any, Any])
_E = TypeVar("_E", bound=BaseException)
_FT = TypeVar("_FT", bound=Callable[..., Any])
_P = ParamSpec("_P")

DIFF_OMITTED: str

class _BaseTestCaseContext:
    def __init__(self, test_case: TestCase) -> None: ...

if sys.version_info >= (3, 9):
    from unittest._log import _AssertLogsContext, _LoggingWatcher
else:
    # Unused dummy for _AssertLogsContext. Starting with Python 3.10,
    # this is generic over the logging watcher, but in lower versions
    # the watcher is hard-coded.
    _L = TypeVar("_L")

    class _LoggingWatcher(NamedTuple):
        records: list[logging.LogRecord]
        output: list[str]

    class _AssertLogsContext(_BaseTestCaseContext, Generic[_L]):
        LOGGING_FORMAT: ClassVar[str]
        test_case: TestCase
        logger_name: str
        level: int
        msg: None
        def __init__(self, test_case: TestCase, logger_name: str, level: int) -> None: ...
        def __enter__(self) -> _LoggingWatcher: ...
        def __exit__(
            self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
        ) -> bool | None: ...

if sys.version_info >= (3, 8):
    def addModuleCleanup(__function: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs) -> None: ...
    def doModuleCleanups() -> None: ...

if sys.version_info >= (3, 11):
    def enterModuleContext(cm: AbstractContextManager[_T]) -> _T: ...

def expectedFailure(test_item: _FT) -> _FT: ...
def skip(reason: str) -> Callable[[_FT], _FT]: ...
def skipIf(condition: object, reason: str) -> Callable[[_FT], _FT]: ...
def skipUnless(condition: object, reason: str) -> Callable[[_FT], _FT]: ...

class SkipTest(Exception):
    def __init__(self, reason: str) -> None: ...

class _SupportsAbsAndDunderGE(SupportsDunderGE[Any], SupportsAbs[Any], Protocol): ...

if sys.version_info >= (3, 10):
    _IsInstanceClassInfo: TypeAlias = Union[type, UnionType, tuple[type | UnionType | tuple[Any, ...], ...]]
else:
    _IsInstanceClassInfo: TypeAlias = Union[type, tuple[type | tuple[Any, ...], ...]]

class TestCase:
    failureException: type[BaseException]
    longMessage: bool
    maxDiff: int | None
    # undocumented
    _testMethodName: str
    # undocumented
    _testMethodDoc: str
    def __init__(self, methodName: str = ...) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def setUp(self) -> None: ...
    def tearDown(self) -> None: ...
    @classmethod
    def setUpClass(cls) -> None: ...
    @classmethod
    def tearDownClass(cls) -> None: ...
    def run(self, result: unittest.result.TestResult | None = ...) -> unittest.result.TestResult | None: ...
    def __call__(self, result: unittest.result.TestResult | None = ...) -> unittest.result.TestResult | None: ...
    def skipTest(self, reason: Any) -> None: ...
    def subTest(self, msg: Any = ..., **params: Any) -> AbstractContextManager[None]: ...
    def debug(self) -> None: ...
    if sys.version_info < (3, 11):
        def _addSkip(self, result: unittest.result.TestResult, test_case: TestCase, reason: str) -> None: ...

    def assertEqual(self, first: Any, second: Any, msg: Any = ...) -> None: ...
    def assertNotEqual(self, first: Any, second: Any, msg: Any = ...) -> None: ...
    def assertTrue(self, expr: Any, msg: Any = ...) -> None: ...
    def assertFalse(self, expr: Any, msg: Any = ...) -> None: ...
    def assertIs(self, expr1: object, expr2: object, msg: Any = ...) -> None: ...
    def assertIsNot(self, expr1: object, expr2: object, msg: Any = ...) -> None: ...
    def assertIsNone(self, obj: object, msg: Any = ...) -> None: ...
    def assertIsNotNone(self, obj: object, msg: Any = ...) -> None: ...
    def assertIn(self, member: Any, container: Iterable[Any] | Container[Any], msg: Any = ...) -> None: ...
    def assertNotIn(self, member: Any, container: Iterable[Any] | Container[Any], msg: Any = ...) -> None: ...
    def assertIsInstance(self, obj: object, cls: _IsInstanceClassInfo, msg: Any = ...) -> None: ...
    def assertNotIsInstance(self, obj: object, cls: _IsInstanceClassInfo, msg: Any = ...) -> None: ...
    @overload
    def assertGreater(self, a: SupportsDunderGT[_T], b: _T, msg: Any = ...) -> None: ...
    @overload
    def assertGreater(self, a: _T, b: SupportsDunderLT[_T], msg: Any = ...) -> None: ...
    @overload
    def assertGreaterEqual(self, a: SupportsDunderGE[_T], b: _T, msg: Any = ...) -> None: ...
    @overload
    def assertGreaterEqual(self, a: _T, b: SupportsDunderLE[_T], msg: Any = ...) -> None: ...
    @overload
    def assertLess(self, a: SupportsDunderLT[_T], b: _T, msg: Any = ...) -> None: ...
    @overload
    def assertLess(self, a: _T, b: SupportsDunderGT[_T], msg: Any = ...) -> None: ...
    @overload
    def assertLessEqual(self, a: SupportsDunderLT[_T], b: _T, msg: Any = ...) -> None: ...
    @overload
    def assertLessEqual(self, a: _T, b: SupportsDunderGT[_T], msg: Any = ...) -> None: ...
    # `assertRaises`, `assertRaisesRegex`, and `assertRaisesRegexp`
    # are not using `ParamSpec` intentionally,
    # because they might be used with explicitly wrong arg types to raise some error in tests.
    @overload
    def assertRaises(  # type: ignore[misc]
        self,
        expected_exception: type[BaseException] | tuple[type[BaseException], ...],
        callable: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None: ...
    @overload
    def assertRaises(self, expected_exception: type[_E] | tuple[type[_E], ...], msg: Any = ...) -> _AssertRaisesContext[_E]: ...
    @overload
    def assertRaisesRegex(  # type: ignore[misc]
        self,
        expected_exception: type[BaseException] | tuple[type[BaseException], ...],
        expected_regex: str | bytes | Pattern[str] | Pattern[bytes],
        callable: Callable[..., object],
        *args: Any,
        **kwargs: Any,
    ) -> None: ...
    @overload
    def assertRaisesRegex(
        self,
        expected_exception: type[_E] | tuple[type[_E], ...],
        expected_regex: str | bytes | Pattern[str] | Pattern[bytes],
        msg: Any = ...,
    ) -> _AssertRaisesContext[_E]: ...
    @overload
    def assertWarns(  # type: ignore[misc]
        self,
        expected_warning: type[Warning] | tuple[type[Warning], ...],
        callable: Callable[_P, object],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None: ...
    @overload
    def assertWarns(self, expected_warning: type[Warning] | tuple[type[Warning], ...], msg: Any = ...) -> _AssertWarnsContext: ...
    @overload
    def assertWarnsRegex(  # type: ignore[misc]
        self,
        expected_warning: type[Warning] | tuple[type[Warning], ...],
        expected_regex: str | bytes | Pattern[str] | Pattern[bytes],
        callable: Callable[_P, object],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None: ...
    @overload
    def assertWarnsRegex(
        self,
        expected_warning: type[Warning] | tuple[type[Warning], ...],
        expected_regex: str | bytes | Pattern[str] | Pattern[bytes],
        msg: Any = ...,
    ) -> _AssertWarnsContext: ...
    def assertLogs(
        self, logger: str | logging.Logger | None = ..., level: int | str | None = ...
    ) -> _AssertLogsContext[_LoggingWatcher]: ...
    if sys.version_info >= (3, 10):
        def assertNoLogs(
            self, logger: str | logging.Logger | None = ..., level: int | str | None = ...
        ) -> _AssertLogsContext[None]: ...

    @overload
    def assertAlmostEqual(self, first: _S, second: _S, places: None, msg: Any, delta: _SupportsAbsAndDunderGE) -> None: ...
    @overload
    def assertAlmostEqual(
        self, first: _S, second: _S, places: None = ..., msg: Any = ..., *, delta: _SupportsAbsAndDunderGE
    ) -> None: ...
    @overload
    def assertAlmostEqual(
        self,
        first: SupportsSub[_T, SupportsAbs[SupportsRound[object]]],
        second: _T,
        places: int | None = ...,
        msg: Any = ...,
        delta: None = ...,
    ) -> None: ...
    @overload
    def assertAlmostEqual(
        self,
        first: _T,
        second: SupportsRSub[_T, SupportsAbs[SupportsRound[object]]],
        places: int | None = ...,
        msg: Any = ...,
        delta: None = ...,
    ) -> None: ...
    @overload
    def assertNotAlmostEqual(self, first: _S, second: _S, places: None, msg: Any, delta: _SupportsAbsAndDunderGE) -> None: ...
    @overload
    def assertNotAlmostEqual(
        self, first: _S, second: _S, places: None = ..., msg: Any = ..., *, delta: _SupportsAbsAndDunderGE
    ) -> None: ...
    @overload
    def assertNotAlmostEqual(
        self,
        first: SupportsSub[_T, SupportsAbs[SupportsRound[object]]],
        second: _T,
        places: int | None = ...,
        msg: Any = ...,
        delta: None = ...,
    ) -> None: ...
    @overload
    def assertNotAlmostEqual(
        self,
        first: _T,
        second: SupportsRSub[_T, SupportsAbs[SupportsRound[object]]],
        places: int | None = ...,
        msg: Any = ...,
        delta: None = ...,
    ) -> None: ...
    def assertRegex(self, text: AnyStr, expected_regex: AnyStr | Pattern[AnyStr], msg: Any = ...) -> None: ...
    def assertNotRegex(self, text: AnyStr, unexpected_regex: AnyStr | Pattern[AnyStr], msg: Any = ...) -> None: ...
    def assertCountEqual(self, first: Iterable[Any], second: Iterable[Any], msg: Any = ...) -> None: ...
    def addTypeEqualityFunc(self, typeobj: type[Any], function: Callable[..., None]) -> None: ...
    def assertMultiLineEqual(self, first: str, second: str, msg: Any = ...) -> None: ...
    def assertSequenceEqual(
        self, seq1: Sequence[Any], seq2: Sequence[Any], msg: Any = ..., seq_type: type[Sequence[Any]] | None = ...
    ) -> None: ...
    def assertListEqual(self, list1: list[Any], list2: list[Any], msg: Any = ...) -> None: ...
    def assertTupleEqual(self, tuple1: tuple[Any, ...], tuple2: tuple[Any, ...], msg: Any = ...) -> None: ...
    def assertSetEqual(self, set1: AbstractSet[object], set2: AbstractSet[object], msg: Any = ...) -> None: ...
    def assertDictEqual(self, d1: Mapping[Any, object], d2: Mapping[Any, object], msg: Any = ...) -> None: ...
    def fail(self, msg: Any = ...) -> NoReturn: ...
    def countTestCases(self) -> int: ...
    def defaultTestResult(self) -> unittest.result.TestResult: ...
    def id(self) -> str: ...
    def shortDescription(self) -> str | None: ...
    if sys.version_info >= (3, 8):
        def addCleanup(self, __function: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs) -> None: ...
    else:
        def addCleanup(self, function: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs) -> None: ...

    if sys.version_info >= (3, 11):
        def enterContext(self, cm: AbstractContextManager[_T]) -> _T: ...

    def doCleanups(self) -> None: ...
    if sys.version_info >= (3, 8):
        @classmethod
        def addClassCleanup(cls, __function: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs) -> None: ...
        @classmethod
        def doClassCleanups(cls) -> None: ...

    if sys.version_info >= (3, 11):
        @classmethod
        def enterClassContext(cls, cm: AbstractContextManager[_T]) -> _T: ...

    def _formatMessage(self, msg: str | None, standardMsg: str) -> str: ...  # undocumented
    def _getAssertEqualityFunc(self, first: Any, second: Any) -> Callable[..., None]: ...  # undocumented
    if sys.version_info < (3, 12):
        failUnlessEqual = assertEqual
        assertEquals = assertEqual
        failIfEqual = assertNotEqual
        assertNotEquals = assertNotEqual
        failUnless = assertTrue
        assert_ = assertTrue
        failIf = assertFalse
        failUnlessRaises = assertRaises
        failUnlessAlmostEqual = assertAlmostEqual
        assertAlmostEquals = assertAlmostEqual
        failIfAlmostEqual = assertNotAlmostEqual
        assertNotAlmostEquals = assertNotAlmostEqual
        assertRegexpMatches = assertRegex
        assertNotRegexpMatches = assertNotRegex
        assertRaisesRegexp = assertRaisesRegex
        def assertDictContainsSubset(
            self, subset: Mapping[Any, Any], dictionary: Mapping[Any, Any], msg: object = ...
        ) -> None: ...

class FunctionTestCase(TestCase):
    def __init__(
        self,
        testFunc: Callable[[], object],
        setUp: Callable[[], object] | None = ...,
        tearDown: Callable[[], object] | None = ...,
        description: str | None = ...,
    ) -> None: ...
    def runTest(self) -> None: ...

class _AssertRaisesContext(Generic[_E]):
    exception: _E
    def __enter__(self: Self) -> Self: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, tb: TracebackType | None
    ) -> bool: ...
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

class _AssertWarnsContext:
    warning: WarningMessage
    filename: str
    lineno: int
    warnings: list[WarningMessage]
    def __enter__(self: Self) -> Self: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, tb: TracebackType | None
    ) -> None: ...
