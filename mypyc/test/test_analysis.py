"""Test runner for data-flow analysis test cases."""

import os.path
import re
import shutil
from typing import List

from mypy import build
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options
from mypy import experiments

from mypyc import analysis
from mypyc import genops
from mypyc.ops import format_func, Register
from mypyc.test.testutil import ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite

files = [
    'analysis.test'
]


class TestAnalysis(MypycDataSuite):
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a data-flow analysis test case."""

        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = testcase.output
            program_text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.python_version = (3, 6)

            source = build.BuildSource('main', '__main__', program_text)
            try:
                # Construct input as a single single.
                # Parse and type check the input program.
                result = build.build(sources=[source],
                                     options=options,
                                     alt_lib_path=test_temp_dir)
            except CompileError as e:
                actual = e.messages
            else:
                if result.errors:
                    actual = result.errors
                else:
                    module = genops.build_ir(result.files['__main__'], result.types)
                    assert len(module.functions) == 1, "Only 1 function definition expected per test case"
                    fn = module.functions[0]
                    actual = format_func(fn)
                    actual = actual[actual.index('L0:'):]
                    cfg = analysis.get_cfg(fn.blocks)

                    args = set([Register(i) for i in range(len(fn.args))])
                    name = testcase.name
                    if name.endswith('_MaybeDefined'):
                        # Forward, maybe
                        analysis_result = analysis.analyze_maybe_defined_regs(fn.blocks, cfg, args)
                    elif name.endswith('_Liveness'):
                        # Backward, maybe
                        analysis_result = analysis.analyze_live_regs(fn.blocks, cfg)
                    elif name.endswith('_MustDefined'):
                        # Forward, must
                        analysis_result = analysis.analyze_must_defined_regs(
                            fn.blocks, cfg, args,
                            num_regs=fn.env.num_regs())
                    elif name.endswith('_BorrowedArgument'):
                        # Forward, must
                        analysis_result = analysis.analyze_borrowed_arguments(fn.blocks, cfg, args)
                    else:
                        assert False, 'No recognized _AnalysisName suffix in test case'

                    actual.append('')
                    for key in sorted(analysis_result.before.keys()):
                        pre = ', '.join(fn.env.names[reg] for reg in analysis_result.before[key])
                        post = ', '.join(fn.env.names[reg] for reg in analysis_result.after[key])
                        actual.append('%-8s %-23s %s' % (key, '{%s}' % pre, '{%s}' % post))
            assert_string_arrays_equal(
                expected_output, actual,
                'Invalid source code output ({}, line {})'.format(testcase.file,
                                                                  testcase.line))
