import glob
import os.path
import shutil

import typing

from mypy.myunit import Suite, AssertionFailure, run_test
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.data import parse_test_cases
from mypy.test import config
from mypy.parse import parse
from mypy.errors import CompileError
from mypy.stubgen import generate_stub


class StubgenSuite(Suite):
    test_data_files = ['stubgen.test']

    def cases(self):
        c = []
        for path in self.test_data_files:
            c += parse_test_cases(os.path.join(config.test_data_prefix, path), test_stubgen)
        return c


def test_stubgen(testcase):
    source = '\n'.join(testcase.input)
    path = 'prog.py'
    out_dir = '_out'
    os.mkdir(out_dir)
    try:
        with open(path, 'w') as file:
            file.write(source)
            file.close()
            try:
                n = generate_stub(path, out_dir)
                a = load_output(out_dir)
            except CompileError as e:
                a = e.messages
            assert_string_arrays_equal(testcase.output, a,
                                       'Invalid output ({}, line {})'.format(
                                           testcase.file, testcase.line))
    finally:
        shutil.rmtree(out_dir)
        os.remove(path)


def load_output(dirname):
    result = []
    entries = glob.glob('%s/*' % dirname)
    assert entries, 'No files generated'
    if len(entries) == 1:
        add_file(entries[0], result)
    else:
        for entry in entries:
            result.append('## %s ##' % entry)
            add_file(entry, result)
    return result


def add_file(path, result):
    with open(path) as file:
        result.extend(file.read().splitlines())


if __name__ == '__main__':
    import sys
    run_test(StubgenSuite(), sys.argv[1:])
