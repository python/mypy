"""Identity AST transform test cases"""

import os.path

from typing import Dict, List

from mypy import build
from mypy.build import BuildSource
from mypy.myunit import Suite
from mypy.test.helpers import assert_string_arrays_equal, testfile_pyversion
from mypy.test.data import parse_test_cases
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.errors import CompileError
from mypy.nodes import TypeInfo
from mypy.treetransform import TransformVisitor
from mypy.options import Options


class TransformSuite(Suite):
    # Reuse semantic analysis test cases.
    transform_files = ['semanal-basic.test',
                       'semanal-expressions.test',
                       'semanal-classes.test',
                       'semanal-types.test',
                       'semanal-modules.test',
                       'semanal-statements.test',
                       'semanal-abstractclasses.test',
                       'semanal-python2.test']

    def cases(self):
        c = []
        for f in self.transform_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_transform,
                                  base_path=test_temp_dir,
                                  native_sep=True)
        return c


def test_transform(testcase):
    """Perform an identity transform test case."""

    try:
        src = '\n'.join(testcase.input)
        options = Options()
        options.use_builtins_fixtures = True
        options.semantic_analysis_only = True
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
                                     'abc.pyi'))
                    and not os.path.basename(f.path).startswith('_')
                    and not os.path.splitext(
                        os.path.basename(f.path))[0].endswith('_')):
                t = TestTransformVisitor()
                f = t.node(f)
                a += str(f).split('\n')
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(
        testcase.output, a,
        'Invalid semantic analyzer output ({}, line {})'.format(testcase.file,
                                                                testcase.line))


class TestTransformVisitor(TransformVisitor):
    def type(self, type):
        assert type is not None
        return type
