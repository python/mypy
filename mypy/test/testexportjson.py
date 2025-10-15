"""Test cases for the mypy cache JSON export tool."""

from __future__ import annotations

import os
import json
import re
import pprint
import sys

from mypy import build
from mypy.errors import CompileError
from mypy.modulefinder import BuildSource
from mypy.options import Options
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.exportjson import convert_binary_cache_to_json


class TypeExportSuite(DataSuite):
    required_out_section = True
    files = ["exportjson.test"]

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        try:
            src = "\n".join(testcase.input)
            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.allow_empty_bodies = True
            options.fixed_format_cache = True
            fnam = os.path.join(self.base_path, "main.py")
            with open(fnam, "w") as f:
                f.write(src)
            result = build.build(
                sources=[BuildSource(fnam, "main")],
                options=options,
                alt_lib_path=test_temp_dir,
            )
            a = result.errors

            major, minor = sys.version_info[:2]
            cache_dir = os.path.join(".mypy_cache", f"{major}.{minor}")

            for module in result.files:
                if module in ("builtins", "typing", "_typeshed"):
                    continue
                fnam = os.path.join(cache_dir, f"{module}.data.ff")
                with open(fnam, "rb") as f:
                    json_data = convert_binary_cache_to_json(f.read(), implicit_names=False)
                for line in json.dumps(json_data, indent=4).splitlines():
                    if '"path": ' in line:
                        # We source file path is unpredictable, so filter it out
                        line = re.sub(r'"[^"]+\.pyi?"', "...", line)
                    a.append(line)
                print(fnam)
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            testcase.output,
            a,
            f"Invalid output ({testcase.file}, line {testcase.line})",
        )
