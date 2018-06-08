"""Test JUnit XML file generation"""
import os.path
import re
import subprocess
import sys

from typing import List

from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase, DataSuite, fix_win_path_in_message
import xml.etree.ElementTree as ET

# Path to Python 3 interpreter
python3_path = sys.executable


class JUnitXMLSuite(DataSuite):
    files = [
        'check-junit.test',
    ]
    base_path = test_temp_dir
    optional_out = True
    native_sep = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        generated_junit_xml_file_name = 'generated-junit.xml'

        # Execute mypy with the provided arguments
        files = parse_files_arg(testcase.input[0])
        args = [
            '--show-traceback',
            '--junit-xml',
            generated_junit_xml_file_name,
        ] + files

        assert testcase.old_cwd is not None
        fixed = [python3_path, '-m', 'mypy']
        process = subprocess.Popen(fixed + args,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   cwd=test_temp_dir)
        process.communicate()

        expected_tree = ET.fromstring(
            dict(testcase.output_files)[os.path.join(test_temp_dir, 'expected-junit.xml')]
        )
        with open(os.path.join(test_temp_dir, generated_junit_xml_file_name)) as f:
            generated_tree = ET.fromstring(f.read())

        assert_equivalent_xml_elements(expected_tree, generated_tree)


def _fix_windows_path(path_with_posix_sep: str) -> str:
    # Test fixtures use the posix path separator, but it should be replaced with the
    # OS's native separator
    return path_with_posix_sep.replace(os.path.sep, '/')


def _convert_to_native_path(path_with_posix_sep: str) -> str:
    return path_with_posix_sep.replace('/', os.path.sep)


def assert_equivalent_xml_elements(expected: ET.Element, actual: ET.Element) -> None:
    queue = []

    def handle_single_element(ex: ET.Element, ac: ET.Element) -> None:
        ex_attributes = ex.attrib.copy()
        ac_attributes = ac.attrib.copy()

        # We only check for matching existence of time/timestamp attributes. Values don't matter.
        fuzzy_attributes = ['time', 'timestamp']
        for attrib in fuzzy_attributes:
            assert (attrib in ex_attributes) == (attrib in ac_attributes), \
                "Mismatch of time-based attrib in elements"

        # Once we've verified both elements match in existence of fuzzy attributes, remove them
        for attrib in fuzzy_attributes:
            ex_attributes.pop(attrib, None)
            ac_attributes.pop(attrib, None)

        # The expected output contains posix-specific path separators, so we need to normalize
        # the paths generated on Windows.
        path_sep_dependent_attributes = ['name', 'classname']
        for attrib in path_sep_dependent_attributes:
            ex_value = ex_attributes.pop(attrib, '')
            ac_value = _fix_windows_path(ac_attributes.pop(attrib, ''))

            assert ex_value == ac_value

        assert ex_attributes == ac_attributes

        # We want to normalize the paths in the error messages (if there is any text)
        normalized_ac_text = ac.text
        if normalized_ac_text and os.path.sep == '\\':
            normalized_ac_text = "\n".join(
                fix_win_path_in_message(line)
                for line in normalized_ac_text.split("\n")
            )

        assert ex.text == normalized_ac_text

        # Then, we handle the children
        ex_children = list(ex)
        ac_children = list(ac)

        assert len(ex_children) == len(ac_children)

        for ex_c, ac_c in zip(ex_children, ac_children):
            queue.append((ex_c, ac_c))

    queue.append((expected, actual))

    while queue:
        ex_child, ac_child = queue.pop()

        handle_single_element(ex_child, ac_child)


def parse_files_arg(line: str) -> List[str]:
    """Parse the first line of the program for the command line."""
    m = re.match('# files: (.*)$', line)
    if not m:
        return []  # No args; mypy will spit out an error.
    return [_convert_to_native_path(path) for path in m.group(1).split()]
