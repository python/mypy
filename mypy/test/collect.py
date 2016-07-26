import os

import pytest

from mypy.test.data import DataSuite, DataDrivenTestCase


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
    def __init__(self, name: str, parent: MypyDataSuite, obj: DataDrivenTestCase):
        self.skip = False
        if name.endswith('-skip'):
            self.skip = True
            name = name[:-len('-skip')]

        super().__init__(name, parent)
        self.obj = obj

    def runtest(self):
        if self.skip:
            pytest.skip()
        self.parent.obj().run_case(self.obj)

    def setup(self):
        self.obj.set_up()

    def teardown(self):
        self.obj.tear_down()
