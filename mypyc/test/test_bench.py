"""Benchmark run test cases that don't run by default

All of the real code for this lives in test_run.py.
"""

# We can't "import TestRun from ..." because that will cause pytest
# to collect the non-caching tests when running this file.
import mypyc.test.test_run


class TestBench(mypyc.test.test_run.TestRun):
    benchmark = True
    files = ['run-bench.test']
