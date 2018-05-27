import datetime
import enum
import re
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom  # type: ignore  # not in typshed
from typing import Any
from typing import List
from typing import MutableMapping
from typing import Optional

from mypy.build import BuildSource


def _format_messages_for_test_case(messages: List[str]) -> str:
    return '\n' + '\n'.join(messages)


def _group_messages_by_file_path(messages: List[str]) -> MutableMapping[str, List[str]]:
    groups = {}  # type: MutableMapping[str, List[str]]

    for message in messages:
        if ':' not in message:
            continue

        file_path = message.split(':', 1)[0]

        if file_path not in groups:
            groups[file_path] = list()
        groups[file_path].append(message)

    return groups


def _format_duration_as_seconds(duration: datetime.timedelta) -> str:
    # We manually cap the precision of the seconds in our XML output
    return str(round(duration.total_seconds(), 6))


class TestCaseResultState(enum.Enum):
    error = 'error'
    failure = 'failure'


class TestCase:
    def __init__(
        self,
        name: str,
        classname: str,
        elapsed_time: datetime.timedelta,
        result_state: Optional[TestCaseResultState] = None,
        message: Optional[str] = None,
        output: Optional[str] = None
    ) -> None:
        self.name = name
        self.classname = classname
        self.elapsed_time = elapsed_time
        self.result_state = result_state
        self.message = message
        self.output = output

    def to_xml_element(self) -> ET.Element:
        attributes = {
            "name": self.name,
            "classname": self.classname,
            "time": _format_duration_as_seconds(self.elapsed_time),
        }

        testcase_element = ET.Element("testcase", attributes)

        if self.result_state:
            result_attributes = {
                "type": self.result_state.value,
            }
            if self.message:
                result_attributes["message"] = self.message
            result_element = ET.SubElement(
                testcase_element, self.result_state.value, result_attributes)
            if self.output:
                result_element.text = self.output

        return testcase_element


class TestSuite:
    def __init__(
        self,
        name: str,
        timestamp: datetime.datetime,
        test_cases: List[TestCase],
    ) -> None:
        self.name = name
        self.timestamp = timestamp
        self.test_cases = test_cases

    def to_xml_element(self) -> ET.Element:
        testsuite_element = ET.Element("testsuite")

        num_errors = 0
        num_failures = 0
        total_elapsed_time = datetime.timedelta()
        for test_case in self.test_cases:
            testcase_element = test_case.to_xml_element()
            testsuite_element.append(testcase_element)

            total_elapsed_time += test_case.elapsed_time

            if test_case.result_state == TestCaseResultState.error:
                num_errors += 1
            elif test_case.result_state == TestCaseResultState.failure:
                num_failures += 1

        testsuite_element.attrib = {
            "name": self.name,
            "disabled": "0",
            "skipped": "0",
            "errors": str(num_errors),
            "failures": str(num_failures),
            "timestamp": self.timestamp.isoformat(),
            "tests": str(len(self.test_cases)),
            "time": _format_duration_as_seconds(total_elapsed_time),
        }

        return testsuite_element


class JUnitXMLDocument:
    def __init__(self, test_suite: TestSuite) -> None:
        self.test_suite = test_suite

    def to_xml_string(self) -> str:
        # JUnit XML has a testsuites element that has each testsuite element as a child,
        # but we only have one testsuite we care about.
        testsuite_element = self.test_suite.to_xml_element()

        attributes = {
            key: testsuite_element.attrib[key]
            for key in ["disabled", "errors", "failures", "tests", "time"]
        }
        testsuites_element = ET.Element("testsuites", attributes)
        testsuites_element.append(testsuite_element)

        xml_string = _clean_illegal_xml_chars(ET.tostring(testsuites_element, encoding="unicode"))

        dom = minidom.parseString(xml_string)
        xml_string = dom.toprettyxml()

        return xml_string

    def write_to_file(self, path: str) -> None:
        with open(path, 'w') as f:
            f.write(self.to_xml_string())


def create_document(
    started_at: datetime.datetime,
    finished_at: datetime.datetime,
    sources: List[BuildSource],
    messages: List[str],
) -> JUnitXMLDocument:
    elapsed_time = finished_at - started_at

    failure_messages_by_file_path = _group_messages_by_file_path(messages)

    # Calculate all of the file paths to include as test cases
    unique_file_paths = set(failure_messages_by_file_path.keys())
    for source in sources:
        if not source.path:
            continue
        unique_file_paths.add(source.path)

    file_paths = sorted(unique_file_paths)

    # We don't actually know how much each file contributes to the total time taken to
    # typecheck everything, so we fake it by splitting up the time taken by each build source.
    elapsed_time_per_file = elapsed_time / len(file_paths)

    test_cases = []
    for file_path in file_paths:
        result_state = None
        message = None
        output = None
        if file_path in failure_messages_by_file_path:
            result_state = TestCaseResultState.failure
            message = "mypy produced messages"
            output = _format_messages_for_test_case(failure_messages_by_file_path[file_path])

        case = TestCase(
            file_path,
            classname=file_path,
            elapsed_time=elapsed_time_per_file,
            result_state=result_state,
            message=message,
            output=output,
        )

        test_cases.append(case)

    test_suite = TestSuite(
        'mypy',
        timestamp=started_at,
        test_cases=test_cases,
    )
    return JUnitXMLDocument(test_suite)


def create_serious_error_document(
    started_at: datetime.datetime,
    finished_at: datetime.datetime,
    sources: List[BuildSource],
    messages: List[str],
) -> JUnitXMLDocument:
    total_elapsed_time = finished_at - started_at

    # If there was a serious error, we consider the test suite to be one case that failed
    error_case = TestCase(
        'mypy',
        classname='mypy',
        elapsed_time=total_elapsed_time,
        result_state=TestCaseResultState.error,
        message="mypy produced messages",
        output=_format_messages_for_test_case(messages),
    )
    test_suite = TestSuite(
        'mypy',
        timestamp=started_at,
        test_cases=[error_case],
    )

    return JUnitXMLDocument(test_suite)


def _clean_illegal_xml_chars(string_to_clean: str) -> str:
    """
    Removes any illegal unicode characters from the given XML string.
    Based on: https://stackoverflow.com/q/1707890
    """
    illegal_unichrs = [
        (0x00, 0x08), (0x0B, 0x0C), (0x0E, 0x1F),
        (0x7F, 0x84), (0x86, 0x9F), (0xFDD0, 0xFDDF),
        (0xFFFE, 0xFFFF),
    ]
    if sys.maxunicode >= 0x10000:
        illegal_unichrs.extend([
            (0x1FFFE, 0x1FFFF), (0x2FFFE, 0x2FFFF),
            (0x3FFFE, 0x3FFFF), (0x4FFFE, 0x4FFFF),
            (0x5FFFE, 0x5FFFF), (0x6FFFE, 0x6FFFF),
            (0x7FFFE, 0x7FFFF), (0x8FFFE, 0x8FFFF),
            (0x9FFFE, 0x9FFFF), (0xAFFFE, 0xAFFFF),
            (0xBFFFE, 0xBFFFF), (0xCFFFE, 0xCFFFF),
            (0xDFFFE, 0xDFFFF), (0xEFFFE, 0xEFFFF),
            (0xFFFFE, 0xFFFFF), (0x10FFFE, 0x10FFFF),
        ])

    illegal_ranges = [
        "%s-%s" % (chr(low), chr(high))
        for (low, high) in illegal_unichrs
    ]

    illegal_xml_re = re.compile('[{}]'.format(''.join(illegal_ranges)))
    return illegal_xml_re.sub('', string_to_clean)
