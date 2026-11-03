"""Test cases for `--output=json`.

These cannot be run by the usual unit test runner because of the backslashes in
the output, which get normalized to forward slashes by the test suite on Windows.
"""

from __future__ import annotations

import os
import os.path
import re
from unittest import mock

import mypy
from mypy import api
from mypy.defaults import PYTHON3_VERSION
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase, DataSuite


class OutputJSONsuite(DataSuite):
    files = ["outputjson.test"]

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_output_json(testcase)


def test_output_json(testcase: DataDrivenTestCase) -> None:
    """Run mypy through the API and check its JSON output."""
    program_text = "\n".join(testcase.input)
    flags_match = re.search("# flags: (.*)$", program_text, flags=re.MULTILINE)
    if flags_match is not None:
        mypy_cmdline = flags_match.group(1).split()
    else:
        mypy_cmdline = ["--output=json"]
    mypy_cmdline.append(f"--python-version={'.'.join(map(str, PYTHON3_VERSION))}")

    # Write the program to a file.
    program_path = os.path.join(test_temp_dir, "main")
    mypy_cmdline.append(program_path)
    with open(program_path, "w", encoding="utf8") as file:
        for s in testcase.input:
            file.write(f"{s}\n")

    output = []
    # Type check the program.
    # Workers run in the test's temporary directory, so make the same mypy
    # installation as pytest available to their subprocesses.
    mypy_path = os.path.dirname(os.path.abspath(mypy.__path__[0]))
    with mock.patch.dict(os.environ, {"PYTHONPATH": mypy_path}):
        out, err, returncode = api.run(mypy_cmdline)
    # split lines, remove newlines, and remove directory of test case
    for line in (out + err).rstrip("\n").splitlines():
        if line.startswith(test_temp_dir + os.sep):
            output.append(line[len(test_temp_dir + os.sep) :].rstrip("\r\n"))
        else:
            output.append(line.rstrip("\r\n"))

    if returncode > 1:
        output.append("!!! Mypy crashed !!!")

    # Remove temp file.
    os.remove(program_path)

    # JSON encodes every `\` character into `\\`, so we need to remove `\\` from windows paths
    # and `/` from POSIX paths
    json_os_separator = os.sep.replace("\\", "\\\\")
    normalized_output = [line.replace(test_temp_dir + json_os_separator, "") for line in output]

    assert normalized_output == testcase.output
