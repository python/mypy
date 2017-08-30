"""Semantic analyzer test cases"""

import os.path

from typing import Dict, List

from mypy import build
from mypy.build import BuildSource
from mypy.test.helpers import (
    assert_string_arrays_equal, normalize_error_messages, testfile_pyversion,
)
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.errors import CompileError
from mypy.nodes import TypeInfo
from mypy.options import Options


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
                 'semanal-typeddict.test',
                 'semanal-classvar.test',
                 'semanal-python2.test']


def get_semanal_options() -> Options:
    options = Options()
    options.use_builtins_fixtures = True
    options.semantic_analysis_only = True
    options.show_traceback = True
    return options


class SemAnalSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in semanal_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_semanal,
                                  base_path=test_temp_dir,
                                  optional_out=True,
                                  native_sep=True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_semanal(testcase)


def test_semanal(testcase: DataDrivenTestCase) -> None:
    """Perform a semantic analysis test case.

    The testcase argument contains a description of the test case
    (inputs and output).
    """

    try:
        src = '\n'.join(testcase.input)
        options = get_semanal_options()
        options.python_version = testfile_pyversion(testcase.file)
        result = build.build(sources=[BuildSource('main', None, src)],
                             options=options,
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
            if (not f.path.endswith((os.sep + 'builtins.pyi',
                                     'typing.pyi',
                                     'mypy_extensions.pyi',
                                     'abc.pyi',
                                     'collections.pyi'))
                    and not os.path.basename(f.path).startswith('_')
                    and not os.path.splitext(
                        os.path.basename(f.path))[0].endswith('_')):
                a += str(f).split('\n')
    except CompileError as e:
        a = e.messages
    a = normalize_error_messages(a)
    assert_string_arrays_equal(
        testcase.output, a,
        'Invalid semantic analyzer output ({}, line {})'.format(testcase.file,
                                                                testcase.line))


# Semantic analyzer error test cases

# Paths to files containing test case descriptions.
semanal_error_files = ['semanal-errors.test']


class SemAnalErrorSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        # Read test cases from test case description files.
        c = []  # type: List[DataDrivenTestCase]
        for f in semanal_error_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_semanal_error, test_temp_dir, optional_out=True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_semanal_error(testcase)


def test_semanal_error(testcase: DataDrivenTestCase) -> None:
    """Perform a test case."""

    try:
        src = '\n'.join(testcase.input)
        res = build.build(sources=[BuildSource('main', None, src)],
                          options=get_semanal_options(),
                          alt_lib_path=test_temp_dir)
        a = res.errors
        assert a, 'No errors reported in {}, line {}'.format(testcase.file, testcase.line)
    except CompileError as e:
        # Verify that there was a compile error and that the error messages
        # are equivalent.
        a = e.messages
    assert_string_arrays_equal(
        testcase.output, normalize_error_messages(a),
        'Invalid compiler output ({}, line {})'.format(testcase.file, testcase.line))


# SymbolNode table export test cases

# Test case descriptions
semanal_symtable_files = ['semanal-symtable.test']


class SemAnalSymtableSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in semanal_symtable_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(testcase.input)
            result = build.build(sources=[BuildSource('main', None, src)],
                                 options=get_semanal_options(),
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
        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(
                testcase.file, testcase.line))


# Type info export test cases

semanal_typeinfo_files = ['semanal-typeinfo.test']


class SemAnalTypeInfoSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        """Test case descriptions"""
        c = []  # type: List[DataDrivenTestCase]
        for f in semanal_typeinfo_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(testcase.input)
            result = build.build(sources=[BuildSource('main', None, src)],
                                 options=get_semanal_options(),
                                 alt_lib_path=test_temp_dir)
            a = result.errors
            if a:
                raise CompileError(a)

            # Collect all TypeInfos in top-level modules.
            typeinfos = TypeInfoMap()
            for f in result.files.values():
                for n in f.names.values():
                    if isinstance(n.node, TypeInfo):
                        assert n.fullname is not None
                        typeinfos[n.fullname] = n.node

            # The output is the symbol table converted into a string.
            a = str(typeinfos).split('\n')
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(
                testcase.file, testcase.line))


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
