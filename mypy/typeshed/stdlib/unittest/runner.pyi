import unittest.case
import unittest.result
import unittest.suite
from collections.abc import Callable, Iterable
from typing import TextIO
from typing_extensions import TypeAlias

_ResultClassType: TypeAlias = Callable[[TextIO, bool, int], unittest.result.TestResult]

class TextTestResult(unittest.result.TestResult):
    descriptions: bool  # undocumented
    dots: bool  # undocumented
    separator1: str
    separator2: str
    showAll: bool  # undocumented
    stream: TextIO  # undocumented
    def __init__(self, stream: TextIO, descriptions: bool, verbosity: int) -> None: ...
    def getDescription(self, test: unittest.case.TestCase) -> str: ...
    def printErrors(self) -> None: ...
    def printErrorList(self, flavour: str, errors: Iterable[tuple[unittest.case.TestCase, str]]) -> None: ...

class TextTestRunner:
    resultclass: _ResultClassType
    def __init__(
        self,
        stream: TextIO | None = ...,
        descriptions: bool = ...,
        verbosity: int = ...,
        failfast: bool = ...,
        buffer: bool = ...,
        resultclass: _ResultClassType | None = ...,
        warnings: type[Warning] | None = ...,
        *,
        tb_locals: bool = ...,
    ) -> None: ...
    def _makeResult(self) -> unittest.result.TestResult: ...
    def run(self, test: unittest.suite.TestSuite | unittest.case.TestCase) -> unittest.result.TestResult: ...
