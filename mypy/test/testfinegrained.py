"""Test cases for fine-grained incremental checking.

Each test cases runs a batch build followed by one or more fine-grained
incremental steps. We verify that each step produces the expected output.

See the comment at the top of test-data/unit/fine-grained.test for more
information.

N.B.: Unlike most of the other test suites, testfinegrained does not
rely on an alt_lib_path for finding source files. This means that they
can test interactions with the lib_path that is built implicitly based
on specified sources.
"""

import os
import re

from typing import List, cast

from mypy import build
from mypy.modulefinder import BuildSource
from mypy.errors import CompileError
from mypy.options import Options
from mypy.test.config import test_temp_dir
from mypy.test.data import (
    DataDrivenTestCase, DataSuite, UpdateFile
)
from mypy.test.helpers import (
    assert_string_arrays_equal, parse_options, copy_and_fudge_mtime, assert_module_equivalence,
)
from mypy.server.mergecheck import check_consistency
from mypy.dmypy_server import Server
from mypy.main import parse_config_file
from mypy.find_sources import create_source_list

import pytest  # type: ignore  # no pytest in typeshed

# Set to True to perform (somewhat expensive) checks for duplicate AST nodes after merge
CHECK_CONSISTENCY = False


class FineGrainedSuite(DataSuite):
    files = [
        'fine-grained.test',
        'fine-grained-cycles.test',
        'fine-grained-blockers.test',
        'fine-grained-modules.test',
    ]
    # Whether to use the fine-grained cache in the testing. This is overridden
    # by a trivial subclass to produce a suite that uses the cache.
    use_cache = False

    # Decide whether to skip the test. This could have been structured
    # as a filter() classmethod also, but we want the tests reported
    # as skipped, not just elided.
    def should_skip(self, testcase: DataDrivenTestCase) -> bool:
        if self.use_cache:
            if testcase.only_when == '-only_when_nocache':
                return True
            # TODO: In caching mode we currently don't well support
            # starting from cached states with errors in them.
            if testcase.output and testcase.output[0] != '==':
                return True
        else:
            if testcase.only_when == '-only_when_cache':
                return True

        return False

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        if self.should_skip(testcase):
            pytest.skip()
            return

        main_src = '\n'.join(testcase.input)
        main_path = os.path.join(test_temp_dir, 'main')
        with open(main_path, 'w') as f:
            f.write(main_src)

        options = self.get_options(main_src, testcase, build_cache=False)
        build_options = self.get_options(main_src, testcase, build_cache=True)
        server = Server(options)

        num_regular_incremental_steps = self.get_build_steps(main_src)
        step = 1
        sources = self.parse_sources(main_src, step, options)
        if step <= num_regular_incremental_steps:
            messages = self.build(build_options, sources)
        else:
            messages = self.run_check(server, sources)

        a = []
        if messages:
            a.extend(normalize_messages(messages))

        if server.fine_grained_manager:
            if CHECK_CONSISTENCY:
                check_consistency(server.fine_grained_manager)

        steps = testcase.find_steps()
        all_triggered = []

        for operations in steps:
            step += 1
            for op in operations:
                if isinstance(op, UpdateFile):
                    # Modify/create file
                    copy_and_fudge_mtime(op.source_path, op.target_path)
                else:
                    # Delete file
                    os.remove(op.path)
            sources = self.parse_sources(main_src, step, options)

            if step <= num_regular_incremental_steps:
                new_messages = self.build(build_options, sources)
            else:
                new_messages = self.run_check(server, sources)

            updated = []  # type: List[str]
            changed = []  # type: List[str]
            if server.fine_grained_manager:
                if CHECK_CONSISTENCY:
                    check_consistency(server.fine_grained_manager)
                all_triggered.append(server.fine_grained_manager.triggered)

                updated = server.fine_grained_manager.updated_modules
                changed = [mod for mod, file in server.fine_grained_manager.changed_modules]

            assert_module_equivalence(
                'stale' + str(step - 1),
                testcase.expected_stale_modules.get(step - 1),
                changed)
            assert_module_equivalence(
                'rechecked' + str(step - 1),
                testcase.expected_rechecked_modules.get(step - 1),
                updated)

            new_messages = normalize_messages(new_messages)

            a.append('==')
            a.extend(new_messages)

        # Normalize paths in test output (for Windows).
        a = [line.replace('\\', '/') for line in a]

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(
                testcase.file, testcase.line))

        if testcase.triggered:
            assert_string_arrays_equal(
                testcase.triggered,
                self.format_triggered(all_triggered),
                'Invalid active triggers ({}, line {})'.format(testcase.file,
                                                               testcase.line))

    def get_options(self,
                    source: str,
                    testcase: DataDrivenTestCase,
                    build_cache: bool) -> Options:
        # This handles things like '# flags: --foo'.
        options = parse_options(source, testcase, incremental_step=1)
        options.incremental = True
        options.use_builtins_fixtures = True
        options.show_traceback = True
        options.fine_grained_incremental = not build_cache
        options.use_fine_grained_cache = self.use_cache and not build_cache
        options.cache_fine_grained = self.use_cache
        options.local_partial_types = True
        if options.follow_imports == 'normal':
            options.follow_imports = 'error'

        for name, _ in testcase.files:
            if 'mypy.ini' in name:
                parse_config_file(options, name)
                break

        return options

    def run_check(self, server: Server, sources: List[BuildSource]) -> List[str]:
        response = server.check(sources)
        out = cast(str, response['out'] or response['err'])
        return out.splitlines()

    def build(self,
              options: Options,
              sources: List[BuildSource]) -> List[str]:
        try:
            result = build.build(sources=sources,
                                 options=options)
        except CompileError as e:
            return e.messages
        return result.errors

    def format_triggered(self, triggered: List[List[str]]) -> List[str]:
        result = []
        for n, triggers in enumerate(triggered):
            filtered = [trigger for trigger in triggers
                        if not trigger.endswith('__>')]
            filtered = sorted(filtered)
            result.append(('%d: %s' % (n + 2, ', '.join(filtered))).strip())
        return result

    def get_build_steps(self, program_text: str) -> int:
        """Get the number of regular incremental steps to run, from the test source"""
        if not self.use_cache:
            return 0
        m = re.search('# num_build_steps: ([0-9]+)$', program_text, flags=re.MULTILINE)
        if m is not None:
            return int(m.group(1))
        return 1

    def parse_sources(self, program_text: str,
                      incremental_step: int,
                      options: Options) -> List[BuildSource]:
        """Return target BuildSources for a test case.

        Normally, the unit tests will check all files included in the test
        case. This differs from how testcheck works by default, as dmypy
        doesn't currently support following imports.

        You can override this behavior and instruct the tests to check
        multiple modules by using a comment like this in the test case
        input:

          # cmd: main a.py

        You can also use `# cmdN:` to have a different cmd for incremental
        step N (2, 3, ...).

        """
        m = re.search('# cmd: mypy ([a-zA-Z0-9_./ ]+)$', program_text, flags=re.MULTILINE)
        regex = '# cmd{}: mypy ([a-zA-Z0-9_./ ]+)$'.format(incremental_step)
        alt_m = re.search(regex, program_text, flags=re.MULTILINE)
        if alt_m is not None:
            # Optionally return a different command if in a later step
            # of incremental mode, otherwise default to reusing the
            # original cmd.
            m = alt_m

        if m:
            # The test case wants to use a non-default set of files.
            paths = [os.path.join(test_temp_dir, path) for path in m.group(1).strip().split()]
            return create_source_list(paths, options)
        else:
            base = BuildSource(os.path.join(test_temp_dir, 'main'), '__main__', None)
            # Use expand_dir instead of create_source_list to avoid complaints
            # when there aren't any .py files in an increment
            return [base] + create_source_list([test_temp_dir], options,
                                               allow_empty_dir=True)


def normalize_messages(messages: List[str]) -> List[str]:
    return [re.sub('^tmp' + re.escape(os.sep), '', message)
            for message in messages]
