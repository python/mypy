"""Type checker test cases"""

import os.path
import re
import shutil
import sys

from typing import Tuple, List, Dict, Set

from mypy import build
import mypy.myunit  # for mutable globals (ick!)
from mypy.build import BuildSource, find_module_clear_caches
from mypy.myunit import Suite, AssertionFailure
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.helpers import (
    assert_string_arrays_equal, normalize_error_messages,
    testcase_pyversion, update_testcase_output,
)
from mypy.errors import CompileError


# List of files that contain test case descriptions.
files = [
    'check-basic.test',
    'check-classes.test',
    'check-expressions.test',
    'check-statements.test',
    'check-generics.test',
    'check-tuples.test',
    'check-dynamic-typing.test',
    'check-weak-typing.test',
    'check-functions.test',
    'check-inference.test',
    'check-inference-context.test',
    'check-varargs.test',
    'check-kwargs.test',
    'check-overloading.test',
    'check-type-checks.test',
    'check-abstract.test',
    'check-multiple-inheritance.test',
    'check-super.test',
    'check-modules.test',
    'check-generic-subtyping.test',
    'check-typevar-values.test',
    'check-python2.test',
    'check-unsupported.test',
    'check-unreachable-code.test',
    'check-unions.test',
    'check-isinstance.test',
    'check-lists.test',
    'check-namedtuple.test',
    'check-type-aliases.test',
    'check-ignore.test',
    'check-type-promotion.test',
    'check-semanal-error.test',
    'check-flags.test',
    'check-incremental.test',
    'check-bound.test',
]


class TypeCheckSuite(Suite):

    def cases(self) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  self.run_test, test_temp_dir, True)
        return c

    def run_test(self, testcase: DataDrivenTestCase) -> None:
        incremental = 'Incremental' in testcase.name.lower() or 'incremental' in testcase.file
        if incremental:
            # Incremental tests are run once with a cold cache, once with a warm cache.
            # Expect success on first run, errors from testcase.output (if any) on second run.
            self.clear_cache()
            self.run_test_once(testcase, 1)
            self.run_test_once(testcase, 2)
        else:
            self.run_test_once(testcase)

    def clear_cache(self) -> None:
        dn = build.MYPY_CACHE
        if os.path.exists(dn):
            shutil.rmtree(dn)

    def run_test_once(self, testcase: DataDrivenTestCase, incremental=0) -> None:
        find_module_clear_caches()
        pyversion = testcase_pyversion(testcase.file, testcase.name)
        program_text = '\n'.join(testcase.input)
        module_name, program_name, program_text = self.parse_options(program_text)
        flags = self.parse_flags(program_text)
        output = testcase.output
        if incremental:
            flags.append(build.INCREMENTAL)
            if incremental == 1:
                # In run 1, copy program text to program file.
                output = []
                with open(program_name, 'w') as f:
                    f.write(program_text)
                    program_text = None
            elif incremental == 2:
                # In run 2, copy *.py.next files to *.py files.
                for dn, dirs, files in os.walk(os.curdir):
                    for file in files:
                        if file.endswith('.py.next'):
                            full = os.path.join(dn, file)
                            target = full[:-5]
                            shutil.copy(full, target)
        source = BuildSource(program_name, module_name, program_text)
        try:
            res = build.build(target=build.TYPE_CHECK,
                              sources=[source],
                              pyversion=pyversion,
                              flags=flags + [build.TEST_BUILTINS],
                              alt_lib_path=test_temp_dir)
            a = res.errors
        except CompileError as e:
            res = None
            a = e.messages
        a = normalize_error_messages(a)

        if output != a and mypy.myunit.UPDATE_TESTCASES:
            update_testcase_output(testcase, a, mypy.myunit.APPEND_TESTCASES)

        assert_string_arrays_equal(
            output, a,
            'Invalid type checker output ({}, line {})'.format(
                testcase.file, testcase.line))

        if incremental and res:
            self.verify_cache(module_name, program_name, a, res.manager)

    def verify_cache(self, module_name: str, program_name: str, a: List[str],
                     manager: build.BuildManager) -> None:
        # There should be valid cache metadata for each module except
        # those in error_paths; for those there should not be.
        #
        # NOTE: When A imports B and there's an error in B, the cache
        # data for B is invalidated, but the cache data for A remains.
        # However build.process_graphs() will ignore A's cache data.
        error_paths = self.find_error_paths(a)
        modules = self.find_module_files()
        modules.update({module_name: program_name})
        missing_paths = self.find_missing_cache_files(modules, manager)
        if missing_paths != error_paths:
            raise AssertionFailure("cache data discrepancy %s != %s" %
                                   (missing_paths, error_paths))

    def find_error_paths(self, a: List[str]) -> Set[str]:
        hits = set()
        for line in a:
            m = re.match(r'([^\s:]+):\d+: error:', line)
            if m:
                hits.add(m.group(1))
        return hits

    def find_module_files(self) -> Dict[str, str]:
        modules = {}
        for dn, dirs, files in os.walk(test_temp_dir):
            dnparts = dn.split(os.sep)
            assert dnparts[0] == test_temp_dir
            del dnparts[0]
            for file in files:
                if file.endswith('.py'):
                    base, ext = os.path.splitext(file)
                    id = '.'.join(dnparts + [base])
                    modules[id] = os.path.join(dn, file)
        return modules

    def find_missing_cache_files(self, modules: Dict[str, str],
                                 manager: build.BuildManager) -> Set[str]:
        missing = {}
        for id, path in modules.items():
            meta = build.find_cache_meta(id, path, manager)
            if meta is None:
                missing[id] = path
        return set(missing.values())

    def parse_options(self, program_text: str) -> Tuple[str, str, str]:
        """Return type check options for a test case.

        The default ('__main__') module name can be overridden by
        using a comment like this in the test case input:

          # cmd: mypy -m foo.bar

        Return tuple (main module name, main file name, main program text).
        """
        m = re.search('# cmd: mypy -m ([a-zA-Z0-9_.]+) *$', program_text, flags=re.MULTILINE)
        if m:
            # The test case wants to use a non-default main
            # module. Look up the module and give it as the thing to
            # analyze.
            module_name = m.group(1)
            path = build.find_module(module_name, [test_temp_dir])
            with open(path) as f:
                program_text = f.read()
            return m.group(1), path, program_text
        else:
            return '__main__', 'main', program_text

    def parse_flags(self, program_text: str) -> List[str]:
        m = re.search('# flags: (.*)$', program_text, flags=re.MULTILINE)
        if m:
            return m.group(1).split()
        else:
            return []
