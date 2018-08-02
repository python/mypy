"""Test runner for data-flow analysis test cases."""

import os.path
import re
import shutil
from typing import List, Set

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options
from mypy import experiments

from mypyc import analysis
from mypyc import genops
from mypyc import exceptions
from mypyc.ops import format_func, Register, Value
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, assert_test_output
)

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
            program_text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.python_version = (3, 6)
            options.export_types = True

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
                    modules = genops.build_ir([result.files['__main__']], result.types)
                    module = modules[0][1]
                    assert len(module.functions) == 2, (
                        "Only 1 function definition expected per test case")
                    fn = module.functions[0]
                    exceptions.insert_exception_handling(fn)
                    actual = format_func(fn)
                    actual = actual[actual.index('L0:'):]
                    cfg = analysis.get_cfg(fn.blocks)

                    args = set(reg for reg, i in fn.env.indexes.items() if i < len(fn.args))

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
                            regs=fn.env.regs())
                    elif name.endswith('_BorrowedArgument'):
                        # Forward, must
                        analysis_result = analysis.analyze_borrowed_arguments(fn.blocks, cfg, args)
                    else:
                        assert False, 'No recognized _AnalysisName suffix in test case'

                    actual.append('')
                    for key in sorted(analysis_result.before.keys(),
                                      key=lambda x: (x[0].label, x[1])):
                        pre = ', '.join(sorted(reg.name
                                               for reg in analysis_result.before[key]))
                        post = ', '.join(sorted(reg.name
                                                for reg in analysis_result.after[key]))
                        actual.append('%-8s %-23s %s' % ((key[0].label, key[1]),
                                                         '{%s}' % pre, '{%s}' % post))
            assert_test_output(testcase, actual, 'Invalid source code output')
