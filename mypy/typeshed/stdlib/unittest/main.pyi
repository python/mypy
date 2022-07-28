import unittest.case
import unittest.loader
import unittest.result
import unittest.suite
from collections.abc import Iterable
from types import ModuleType
from typing import Any, Protocol

MAIN_EXAMPLES: str
MODULE_EXAMPLES: str

class _TestRunner(Protocol):
    def run(self, test: unittest.suite.TestSuite | unittest.case.TestCase) -> unittest.result.TestResult: ...

# not really documented
class TestProgram:
    result: unittest.result.TestResult
    module: None | str | ModuleType
    verbosity: int
    failfast: bool | None
    catchbreak: bool | None
    buffer: bool | None
    progName: str | None
    warnings: str | None
    testNamePatterns: list[str] | None
    def __init__(
        self,
        module: None | str | ModuleType = ...,
        defaultTest: str | Iterable[str] | None = ...,
        argv: list[str] | None = ...,
        testRunner: type[_TestRunner] | _TestRunner | None = ...,
        testLoader: unittest.loader.TestLoader = ...,
        exit: bool = ...,
        verbosity: int = ...,
        failfast: bool | None = ...,
        catchbreak: bool | None = ...,
        buffer: bool | None = ...,
        warnings: str | None = ...,
        *,
        tb_locals: bool = ...,
    ) -> None: ...
    def usageExit(self, msg: Any = ...) -> None: ...
    def parseArgs(self, argv: list[str]) -> None: ...
    def createTests(self, from_discovery: bool = ..., Loader: unittest.loader.TestLoader | None = ...) -> None: ...
    def runTests(self) -> None: ...  # undocumented

main = TestProgram
