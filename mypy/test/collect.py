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
        update_data = self.config.getoption('--update-data', False)
        self.parent.obj(update_data=update_data).run_case(self.obj)

    def setup(self):
        self.obj.set_up()

    def teardown(self):
        self.obj.tear_down()

    def reportinfo(self):
        return self.obj.file, self.obj.line, self.obj.name

    def repr_failure(self, excinfo):
        if excinfo.errisinstance(SystemExit):
            # We assume that before doing exit() (which raises SystemExit) we've printed
            # enough context about what happened so that a stack trace is not useful.
            # In particular, uncaught exceptions during semantic analysis or type checking
            # call exit() and they already print out a stack trace.
            excrepr = excinfo.exconly()
        else:
            self.parent._prunetraceback(excinfo)
            excrepr = excinfo.getrepr(style='short')

        return "data: {}:{}\n{}".format(self.obj.file, self.obj.line, excrepr)
