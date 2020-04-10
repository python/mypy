"""Test runner for data-flow analysis test cases."""

import os.path

from mypy.test.data import DataDrivenTestCase
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError

from mypyc.common import TOP_LEVEL_NAME
from mypyc import analysis
from mypyc.transform import exceptions
from mypyc.ir.func_ir import format_func
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, build_ir_for_single_file,
    assert_test_output,
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
            try:
                ir = build_ir_for_single_file(testcase.input)
            except CompileError as e:
                actual = e.messages
            else:
                actual = []
                for fn in ir:
                    if (fn.name == TOP_LEVEL_NAME
                            and not testcase.name.endswith('_toplevel')):
                        continue
                    exceptions.insert_exception_handling(fn)
                    actual.extend(format_func(fn))
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

                    for key in sorted(analysis_result.before.keys(),
                                      key=lambda x: (x[0].label, x[1])):
                        pre = ', '.join(sorted(reg.name
                                               for reg in analysis_result.before[key]))
                        post = ', '.join(sorted(reg.name
                                                for reg in analysis_result.after[key]))
                        actual.append('%-8s %-23s %s' % ((key[0].label, key[1]),
                                                         '{%s}' % pre, '{%s}' % post))
            assert_test_output(testcase, actual, 'Invalid source code output')
