import datetime
from typing import List
from typing import MutableMapping

from junit_xml import TestSuite, TestCase  # type: ignore  # not in typeshed

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


class JunitXMLDocument:
    def __init__(
        self,
        started_at: datetime.datetime,
        finished_at: datetime.datetime,
        sources: List[BuildSource],
        messages: List[str],
        was_serious_error: bool,
    ) -> None:
        total_elapsed_secs = (finished_at - started_at).total_seconds()

        test_cases = []

        if was_serious_error:
            # If there was a serious error, we consider the test suite to be one case that failed
            error_case = TestCase('mypy', classname='mypy', elapsed_sec=total_elapsed_secs)
            error_case.add_error_info(
                message="mypy produced messages",
                output=_format_messages_for_test_case(messages),
            )

            test_cases.append(error_case)
        else:
            failure_messages_by_file_path = _group_messages_by_file_path(messages)

            # Calculate all of the file paths to include as test cases
            unique_file_paths = set(failure_messages_by_file_path.keys())
            for source in sources:
                if not source.path:
                    continue
                unique_file_paths.add(source.path)

            file_paths = sorted(unique_file_paths)

            # Test suites don't expose a total duration, so fake it by dividing
            # time equally between all files
            elapsed_time_per_file = total_elapsed_secs / len(file_paths)

            for file_path in file_paths:
                case = TestCase(
                    file_path,
                    classname=file_path,
                    elapsed_sec=elapsed_time_per_file,
                )

                if file_path in failure_messages_by_file_path:
                    messages = failure_messages_by_file_path[file_path]
                    case.add_failure_info(
                        message="mypy produced messages",
                        output=_format_messages_for_test_case(messages),
                    )

                test_cases.append(case)

        self.test_suite = TestSuite(
            'mypy',
            timestamp=started_at.isoformat(),
            test_cases=test_cases,
        )

    def write_to_file(self, path: str) -> None:
        with open(path, 'w') as f:
            TestSuite.to_file(f, [self.test_suite], 'utf-8')
