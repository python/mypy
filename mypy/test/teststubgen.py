import glob
import os.path
import random
import shutil
import time

import typing

from mypy.myunit import Suite, AssertionFailure, run_test, assert_equal
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.data import parse_test_cases
from mypy.test import config
from mypy.parse import parse
from mypy.errors import CompileError
from mypy.stubgen import generate_stub, generate_stub_for_module
from mypy.stubutil import (
    parse_signature, parse_all_signatures, build_signature, find_unique_signatures
)


class StubgenUtilSuite(Suite):
    def test_parse_signature(self):
        self.assert_parse_signature('func()', ('func', [], []))

    def test_parse_signature_with_args(self):
        self.assert_parse_signature('func(arg)', ('func', ['arg'], []))
        self.assert_parse_signature('do(arg, arg2)', ('do', ['arg', 'arg2'], []))

    def test_parse_signature_with_optional_args(self):
        self.assert_parse_signature('func([arg])', ('func', [], ['arg']))
        self.assert_parse_signature('func(arg[, arg2])', ('func', ['arg'], ['arg2']))
        self.assert_parse_signature('func([arg[, arg2]])', ('func', [], ['arg', 'arg2']))

    def test_parse_signature_with_default_arg(self):
        self.assert_parse_signature('func(arg=None)', ('func', [], ['arg']))
        self.assert_parse_signature('func(arg, arg2=None)', ('func', ['arg'], ['arg2']))
        self.assert_parse_signature('func(arg=1, arg2="")', ('func', [], ['arg', 'arg2']))

    def test_parse_signature_with_qualified_function(self):
        self.assert_parse_signature('ClassName.func(arg)', ('func', ['arg'], []))

    def test_parse_signature_with_kw_only_arg(self):
        self.assert_parse_signature('ClassName.func(arg, *, arg2=1)',
                                    ('func', ['arg', '*'], ['arg2']))

    def test_parse_signature_with_star_arg(self):
        self.assert_parse_signature('ClassName.func(arg, *args)',
                                    ('func', ['arg', '*args'], []))

    def test_parse_signature_with_star_star_arg(self):
        self.assert_parse_signature('ClassName.func(arg, **args)',
                                    ('func', ['arg', '**args'], []))

    def assert_parse_signature(self, sig, result):
        assert_equal(parse_signature(sig), result)

    def test_build_signature(self):
        assert_equal(build_signature([], []), '()')
        assert_equal(build_signature(['arg'], []), '(arg)')
        assert_equal(build_signature(['arg', 'arg2'], []), '(arg, arg2)')
        assert_equal(build_signature(['arg'], ['arg2']), '(arg, arg2=Undefined)')

    def test_parse_all_signatures(self):
        assert_equal(parse_all_signatures(['random text',
                                           '.. function:: fn(arg',
                                           '.. function:: fn()',
                                           '  .. method:: fn2(arg)']),
                                          [('fn', '()'),
                                           ('fn2', '(arg)')])

    def test_find_unique_signatures(self):
        assert_equal(find_unique_signatures(
            [('func', '()'),
             ('func', '()'),
             ('func2', '()'),
             ('func2', '(arg)'),
             ('func3', '(arg, arg2)')]),
            [('func', '()'),
             ('func3', '(arg, arg2)')])


class StubgenSuite(Suite):
    test_data_files = ['stubgen.test']

    def cases(self):
        c = []
        for path in self.test_data_files:
            c += parse_test_cases(os.path.join(config.test_data_prefix, path), test_stubgen)
        return c


def test_stubgen(testcase):
    source = '\n'.join(testcase.input)
    name = 'prog%d' % random.randrange(1000 * 1000 * 1000)
    path = '%s.py' % name
    out_dir = '_out'
    os.mkdir(out_dir)
    try:
        with open(path, 'w') as file:
            file.write(source)
            file.close()
            try:
                if testcase.name.endswith('_import'):
                    # For some reason without this sleep fixes random test failures.
                    time.sleep(0.01)
                    generate_stub_for_module(name, out_dir, quiet=True)
                else:
                    generate_stub(path, out_dir, quiet=True)
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
