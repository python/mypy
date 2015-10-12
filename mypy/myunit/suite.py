from typing import Callable, List, Tuple, Union

import os
import tempfile

from mypy.myunit.errors import SkipTestCaseException


class TestCase:
    def __init__(self, name: str, suite: 'Suite' = None,
                 func: Callable[[], None] = None) -> None:
        self.func = func
        self.name = name
        self.suite = suite
        self.old_cwd = None  # type: str
        self.tmpdir = None  # type: tempfile.TemporaryDirectory

    def run(self) -> None:
        if self.func:
            self.func()

    def set_up(self) -> None:
        self.old_cwd = os.getcwd()
        self.tmpdir = tempfile.TemporaryDirectory(prefix='mypy-test-',
                dir=os.path.abspath('tmp-test-dirs'))
        os.chdir(self.tmpdir.name)
        os.mkdir('tmp')
        if self.suite:
            self.suite.set_up()

    def tear_down(self) -> None:
        if self.suite:
            self.suite.tear_down()
        os.chdir(self.old_cwd)
        self.tmpdir.cleanup()
        self.old_cwd = None
        self.tmpdir = None


TestUnion = Union[TestCase, Tuple[str, 'Suite']]


class Suite:
    def __init__(self) -> None:
        self.prefix = typename(type(self)) + '.'
        self._test_cases = []  # type: List[TestUnion]
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
                    assert callable(t), '%s.%s is %s' % (type(self).__name__, m, type(t).__name__)
                    self.add_test(TestCase(m, self, t))

    def add_test(self, test: TestUnion) -> None:
        self._test_cases.append(test)

    def cases(self) -> List[TestUnion]:
        return self._test_cases[:]

    def skip(self) -> None:
        raise SkipTestCaseException()


def typename(t: type) -> str:
    if '.' in str(t):
        return str(t).split('.')[-1].rstrip("'>")
    else:
        return str(t)[8:-2]
