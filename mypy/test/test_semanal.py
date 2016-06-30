"""Semantic analyzer test cases"""

import os.path

from typing import Dict, List

from mypy import build
from mypy.build import BuildSource
from mypy.test.helpers import (
    normalize_error_messages, pyversion_testfile, PytestSuite, test
)
from mypy.test.data import parse_test_cases
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.errors import CompileError
from mypy.nodes import TypeInfo


# Semantic analyzer test cases: dump parse tree

# Semantic analysis test case description files.
semanal_files = ['semanal-basic.test',
                 'semanal-expressions.test',
                 'semanal-classes.test',
                 'semanal-types.test',
                 'semanal-typealiases.test',
                 'semanal-modules.test',
                 'semanal-statements.test',
                 'semanal-abstractclasses.test',
                 'semanal-namedtuple.test',
                 'semanal-python2.test']


class TestSemAnal(PytestSuite):
    @classmethod
    def cases(cls):
        c = []
        for f in semanal_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  semanal_tests,
                                  base_path=test_temp_dir,
                                  optional_out=True,
                                  native_sep=True)
        return c


def semanal_tests(obj, testcase):
    """Perform a semantic analysis test case.

    The testcase argument contains a description of the test case
    (inputs and output).
    """

    try:
        src = '\n'.join(testcase.input)
        result = build.build(target=build.SEMANTIC_ANALYSIS,
                             sources=[BuildSource('main', None, src)],
                             pyversion=pyversion_testfile(testcase.file),
                             flags=[build.TEST_BUILTINS],
                             alt_lib_path=test_temp_dir)
        a = result.errors
        if a:
            raise CompileError(a)
        # Include string representations of the source files in the actual
        # output.
        for fnam in sorted(result.files.keys()):
            f = result.files[fnam]
            # Omit the builtins module and files with a special marker in the
            # path.
            # TODO the test is not reliable
            if (not f.path.endswith((os.sep + 'builtins.py',
                                     'typing.py',
                                     'abc.py',
                                     'collections.py'))
                    and not os.path.basename(f.path).startswith('_')
                    and not os.path.splitext(
                        os.path.basename(f.path))[0].endswith('_')):
                a += str(f).split('\n')
    except CompileError as e:
        a = e.messages
    assert testcase.output == a, \
        'Invalid semantic analyzer output ({}, line {})'.format(testcase.file,
                                                                testcase.line)

TestSemAnal.setup_tests()

# Semantic analyzer error test cases

# Paths to files containing test case descriptions.
semanal_error_files = ['semanal-errors.test']


class TestSemAnalError(PytestSuite):
    @classmethod
    def cases(cls):
        # Read test cases from test case description files.
        c = []
        for f in semanal_error_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  semanal_error_tests, test_temp_dir,
                                  optional_out=True)
        return c


def semanal_error_tests(obj, testcase):
    """Perform a test case."""

    try:
        src = '\n'.join(testcase.input)
        res = build.build(target=build.SEMANTIC_ANALYSIS,
                          sources=[BuildSource('main', None, src)],
                          flags=[build.TEST_BUILTINS],
                          alt_lib_path=test_temp_dir)
        a = res.errors
        assert a, 'No errors reported in {}, line {}'.format(testcase.file, testcase.line)
    except CompileError as e:
        # Verify that there was a compile error and that the error messages
        # are equivalent.
        a = e.messages
    assert testcase.output == normalize_error_messages(a), \
        'Invalid compiler output ({}, line {})'.format(testcase.file,
                                                       testcase.line)

TestSemAnalError.setup_tests()


# SymbolNode table export test cases

# Test case descriptions
semanal_symtable_files = ['semanal-symtable.test']


class TestSemAnalSymtable(PytestSuite):
    @classmethod
    def cases(cls):
        c = []
        for f in semanal_symtable_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  cls.run_test, test_temp_dir)
        return c

    def run_test(self, testcase):
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(testcase.input)
            result = build.build(target=build.SEMANTIC_ANALYSIS,
                                 sources=[BuildSource('main', None, src)],
                                 flags=[build.TEST_BUILTINS],
                                 alt_lib_path=test_temp_dir)
            # The output is the symbol table converted into a string.
            a = result.errors
            if a:
                raise CompileError(a)
            for f in sorted(result.files.keys()):
                if f not in ('builtins', 'typing', 'abc'):
                    a.append('{}:'.format(f))
                    for s in str(result.files[f].names).split('\n'):
                        a.append('  ' + s)
        except CompileError as e:
            a = e.messages
        assert testcase.output == a, \
            'Invalid semantic analyzer output ({}, line {})'.format(
                testcase.file, testcase.line)

TestSemAnalSymtable.setup_tests()


# Type info export test cases

semanal_typeinfo_files = ['semanal-typeinfo.test']


class TestSemAnalTypeInfo(PytestSuite):
    @classmethod
    def cases(cls):
        """Test case descriptions"""
        c = []
        for f in semanal_typeinfo_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  cls.run_test, test_temp_dir)
        return c

    def run_test(self, testcase):
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(testcase.input)
            result = build.build(target=build.SEMANTIC_ANALYSIS,
                                 sources=[BuildSource('main', None, src)],
                                 flags=[build.TEST_BUILTINS],
                                 alt_lib_path=test_temp_dir)
            a = result.errors
            if a:
                raise CompileError(a)

            # Collect all TypeInfos in top-level modules.
            typeinfos = TypeInfoMap()
            for f in result.files.values():
                for n in f.names.values():
                    if isinstance(n.node, TypeInfo):
                        typeinfos[n.fullname] = n.node

            # The output is the symbol table converted into a string.
            a = str(typeinfos).split('\n')
        except CompileError as e:
            a = e.messages
        assert testcase.output == a, \
            'Invalid semantic analyzer output ({}, line {})'.format(
                testcase.file, testcase.line)

TestSemAnalTypeInfo.setup_tests()


class TypeInfoMap(Dict[str, TypeInfo]):
    def __str__(self) -> str:
        a = ['TypeInfoMap(']  # type: List[str]
        for x, y in sorted(self.items()):
            if isinstance(x, str) and (not x.startswith('builtins.') and
                                       not x.startswith('typing.') and
                                       not x.startswith('abc.')):
                ti = ('\n' + '  ').join(str(y).split('\n'))
                a.append('  {} : {}'.format(x, ti))
        a[-1] += ')'
        return '\n'.join(a)
