import os

import pytest

from mypy.test.data import DataSuite


def pytest_pycollect_makeitem(collector, name, obj):
    if not isinstance(obj, type) or not issubclass(obj, DataSuite):
        return None
    #os.write(3, ('collecting: %r %r %r\n' % (collector, name, obj)).encode('utf-8'))

    return MypyDataSuite(name, parent=collector)


class MypyDataSuite(pytest.Class):
    def collect(self):
        for case in self.obj.cases():
            yield MypyDataCase(case.name, self, case)


class MypyDataCase(pytest.Item):
    def __init__(self, name, parent, obj):
        super().__init__(name, parent)
        self.obj = obj

    def runtest(self):
        self.parent.obj().run_case(self.obj)
