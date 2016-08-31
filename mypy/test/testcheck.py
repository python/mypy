"""Type checker test cases"""

import os.path
import re
import shutil
import sys
import time

from typing import Tuple, List, Dict, Set

from mypy import build, defaults
from mypy.main import parse_version, process_options
from mypy.build import BuildSource, find_module_clear_caches
from mypy.myunit import AssertionFailure
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import (
    assert_string_arrays_equal, normalize_error_messages,
    testcase_pyversion, update_testcase_output,
)
from mypy.errors import CompileError, set_show_tb
from mypy.options import Options

from mypy import experiments

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
    'check-optional.test',
    'check-fastparse.test',
    'check-warnings.test',
    'check-async-await.test',
    'check-newtype.test',
]


class TypeCheckSuite(DataSuite):
    def __init__(self, *, update_data=False):
        self.update_data = update_data

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        incremental = 'incremental' in testcase.name.lower() or 'incremental' in testcase.file
        optional = 'optional' in testcase.file
        if incremental:
            # Incremental tests are run once with a cold cache, once with a warm cache.
            # Expect success on first run, errors from testcase.output (if any) on second run.
            # We briefly sleep to make sure file timestamps are distinct.
            self.clear_cache()
            self.run_case_once(testcase, 1)
            self.run_case_once(testcase, 2)
        elif optional:
            try:
                experiments.STRICT_OPTIONAL = True
                self.run_case_once(testcase)
            finally:
                experiments.STRICT_OPTIONAL = False
        else:
            self.run_case_once(testcase)

    def clear_cache(self) -> None:
        dn = defaults.MYPY_CACHE

        if os.path.exists(dn):
            shutil.rmtree(dn)

    def run_case_once(self, testcase: DataDrivenTestCase, incremental=0) -> None:
        find_module_clear_caches()
        original_program_text = '\n'.join(testcase.input)
        module_data = self.parse_module(original_program_text, incremental)

        options = self.parse_options(original_program_text, testcase)
        options.use_builtins_fixtures = True
        set_show_tb(True)  # Show traceback on crash.

        if incremental:
            options.incremental = True
            if incremental == 1:
                # In run 1, copy program text to program file.
                for module_name, program_path, program_text in module_data:
                    if module_name == '__main__':
                        with open(program_path, 'w') as f:
                            f.write(program_text)
                        break
            elif incremental == 2:
                # In run 2, copy *.py.next files to *.py files.
                for dn, dirs, files in os.walk(os.curdir):
                    for file in files:
                        if file.endswith('.py.next'):
                            full = os.path.join(dn, file)
                            target = full[:-5]
                            shutil.copy(full, target)

                            # In some systems, mtime has a resolution of 1 second which can cause
                            # annoying-to-debug issues when a file has the same size after a
                            # change. We manually set the mtime to circumvent this.
                            new_time = os.stat(target).st_mtime + 1
                            os.utime(target, times=(new_time, new_time))

        sources = []
        for module_name, program_path, program_text in module_data:
            # Always set to none so we're forced to reread the module in incremental mode
            program_text = None if incremental else program_text
            sources.append(BuildSource(program_path, module_name, program_text))
        try:
            res = build.build(sources=sources,
                              options=options,
                              alt_lib_path=test_temp_dir)
            a = res.errors
        except CompileError as e:
            res = None
            a = e.messages
        a = normalize_error_messages(a)

        # Make sure error messages match
        if incremental == 0:
            msg = 'Invalid type checker output ({}, line {})'
            output = testcase.output
        elif incremental == 1:
            msg = 'Invalid type checker output in incremental, run 1 ({}, line {})'
            output = testcase.output
        elif incremental == 2:
            msg = 'Invalid type checker output in incremental, run 2 ({}, line {})'
            output = testcase.output2
        else:
            raise AssertionError()

        if output != a and self.update_data:
            update_testcase_output(testcase, a)
        assert_string_arrays_equal(output, a, msg.format(testcase.file, testcase.line))

        if incremental and res:
            if not options.silent_imports and testcase.output is None:
                self.verify_cache(module_data, a, res.manager)
            if incremental == 2:
                self.check_module_equivalence(
                    'rechecked',
                    testcase.expected_rechecked_modules,
                    res.manager.rechecked_modules)
                self.check_module_equivalence(
                    'stale',
                    testcase.expected_stale_modules,
                    res.manager.stale_modules)

    def check_module_equivalence(self, name: str, expected: Set[str], actual: Set[str]) -> None:
        if expected is not None:
            assert_string_arrays_equal(
                list(sorted(expected)),
                list(sorted(actual.difference({"__main__"}))),
                'Set of {} modules does not match expected set'.format(name))

    def verify_cache(self, module_data: List[Tuple[str, str, str]], a: List[str],
                     manager: build.BuildManager) -> None:
        # There should be valid cache metadata for each module except
        # those in error_paths; for those there should not be.
        #
        # NOTE: When A imports B and there's an error in B, the cache
        # data for B is invalidated, but the cache data for A remains.
        # However build.process_graphs() will ignore A's cache data.
        #
        # Also note that when A imports B, and there's an error in A
        # _due to a valid change in B_, the cache data for B will be
        # invalidated and updated, but the old cache data for A will
        # remain unchanged. As before, build.process_graphs() will
        # ignore A's (old) cache data.
        error_paths = self.find_error_paths(a)
        modules = self.find_module_files()
        modules.update({module_name: path for module_name, path, text in module_data})
        missing_paths = self.find_missing_cache_files(modules, manager)
        if not missing_paths.issubset(error_paths):
            raise AssertionFailure("cache data discrepancy %s != %s" %
                                   (missing_paths, error_paths))

    def find_error_paths(self, a: List[str]) -> Set[str]:
        hits = set()
        for line in a:
            m = re.match(r'([^\s:]+):\d+: error:', line)
            if m:
                p = m.group(1).replace('/', os.path.sep)
                hits.add(p)
        return hits

    def find_module_files(self) -> Dict[str, str]:
        modules = {}
        for dn, dirs, files in os.walk(test_temp_dir):
            dnparts = dn.split(os.sep)
            assert dnparts[0] == test_temp_dir
            del dnparts[0]
            for file in files:
                if file.endswith('.py'):
                    if file == "__init__.py":
                        # If the file path is `a/b/__init__.py`, exclude the file name
                        # and make sure the module id is just `a.b`, not `a.b.__init__`.
                        id = '.'.join(dnparts)
                    else:
                        base, ext = os.path.splitext(file)
                        id = '.'.join(dnparts + [base])
                    modules[id] = os.path.join(dn, file)
        return modules

    def find_missing_cache_files(self, modules: Dict[str, str],
                                 manager: build.BuildManager) -> Set[str]:
        missing = {}
        for id, path in modules.items():
            meta = build.find_cache_meta(id, path, manager)
            if not build.is_meta_fresh(meta, id, path, manager):
                missing[id] = path
        return set(missing.values())

    def parse_module(self, program_text: str, incremental: int = 0) -> List[Tuple[str, str, str]]:
        """Return the module and program names for a test case.

        Normally, the unit tests will parse the default ('__main__')
        module and follow all the imports listed there. You can override
        this behavior and instruct the tests to check multiple modules
        by using a comment like this in the test case input:

          # cmd: mypy -m foo.bar foo.baz

        Return a list of tuples (module name, file name, program text).
        """
        m = re.search('# cmd: mypy -m ([a-zA-Z0-9_. ]+)$', program_text, flags=re.MULTILINE)
        m2 = re.search('# cmd2: mypy -m ([a-zA-Z0-9_. ]+)$', program_text, flags=re.MULTILINE)
        if m2 is not None and incremental == 2:
            # Optionally return a different command if in the second
            # stage of incremental mode, otherwise default to reusing
            # the original cmd.
            m = m2

        if m:
            # The test case wants to use a non-default main
            # module. Look up the module and give it as the thing to
            # analyze.
            module_names = m.group(1)
            out = []
            for module_name in module_names.split(' '):
                path = build.find_module(module_name, [test_temp_dir])
                with open(path) as f:
                    program_text = f.read()
                out.append((module_name, path, program_text))
            return out
        else:
            return [('__main__', 'main', program_text)]

    def parse_options(self, program_text: str, testcase: DataDrivenTestCase) -> Options:
        options = Options()
        flags = re.search('# flags: (.*)$', program_text, flags=re.MULTILINE)

        flag_list = None
        if flags:
            flag_list = flags.group(1).split()
            targets, options = process_options(flag_list, require_targets=False)
            if targets:
                # TODO: support specifying targets via the flags pragma
                raise RuntimeError('Specifying targets via the flags pragma is not supported.')
        else:
            options = Options()

        # Allow custom python version to override testcase_pyversion
        if (not flag_list or
                all(flag not in flag_list for flag in ['--python-version', '-2', '--py2'])):
            options.python_version = testcase_pyversion(testcase.file, testcase.name)

        return options
