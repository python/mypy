"""Parallel subprocess task runner.

This is used for running mypy tests.
"""

from typing import Dict, List, Optional, Set, Tuple

import os
import pipes
import re
from subprocess import Popen, STDOUT
import sys
import tempfile
import time


class WaiterError(Exception):
    pass


class LazySubprocess:
    """Wrapper around a subprocess that runs a test task."""

    def __init__(self, name: str, args: List[str], *, cwd: str = None,
                 env: Dict[str, str] = None) -> None:
        self.name = name
        self.args = args
        self.cwd = cwd
        self.env = env
        self.start_time = None  # type: float
        self.end_time = None  # type: float

    def start(self) -> None:
        self.outfile = tempfile.TemporaryFile()
        self.start_time = time.time()
        self.process = Popen(self.args, cwd=self.cwd, env=self.env,
                             stdout=self.outfile, stderr=STDOUT)
        self.pid = self.process.pid

    def wait(self) -> int:
        return self.process.wait()

    def status(self) -> Optional[int]:
        return self.process.returncode

    def read_output(self) -> str:
        file = self.outfile
        file.seek(0)
        # Assume it's ascii to avoid unicode headaches (and portability issues).
        return file.read().decode('ascii')

    @property
    def elapsed_time(self) -> float:
        return self.end_time - self.start_time


class Noter:
    """Update stats about running jobs.

    Only used when verbosity == 0.
    """

    def __init__(self, total: int) -> None:
        # Total number of tasks.
        self.total = total
        self.running = set()  # type: Set[int]
        # Passed tasks.
        self.passes = 0
        # Failed tasks.
        self.fails = 0

    def start(self, job: int) -> None:
        self.running.add(job)
        self.update()

    def stop(self, job: int, failed: bool) -> None:
        self.running.remove(job)
        if failed:
            self.fails += 1
        else:
            self.passes += 1
        self.update()

    def message(self, msg: str) -> None:
        # Using a CR instead of NL will overwrite the line.
        sys.stdout.write('%-80s\r' % msg)
        sys.stdout.flush()

    def update(self) -> None:
        pending = self.total - self.passes - self.fails - len(self.running)
        args = (self.passes, self.fails, pending, len(self.running))
        msg = 'passed %d, failed %d, pending %d; running %d' % args
        self.message(msg)

    def clear(self) -> None:
        self.message('')


class Waiter:
    """Run subprocesses in parallel and wait for them.

    Usage:

    waiter = Waiter()
    waiter.add('sleep 9')
    waiter.add('sleep 10')
    if not waiter.run():
        print('error')
    """
    def __init__(self, limit: int = 0, *, verbosity: int = 0, xfail: List[str] = []) -> None:
        self.verbosity = verbosity
        self.queue = []  # type: List[LazySubprocess]
        # Index of next task to run in the queue.
        self.next = 0
        self.current = {}  # type: Dict[int, Tuple[int, LazySubprocess]]
        if limit == 0:
            try:
                sched_getaffinity = os.sched_getaffinity
            except AttributeError:
                limit = 2
            else:
                # Note: only count CPUs we are allowed to use. It is a
                # major mistake to count *all* CPUs on the machine.
                limit = len(sched_getaffinity(0))
        self.limit = limit
        assert limit > 0
        self.xfail = set(xfail)
        self._note = None  # type: Noter
        self.times1 = {}  # type: Dict[str, float]
        self.times2 = {}  # type: Dict[str, float]

    def add(self, cmd: LazySubprocess) -> int:
        rv = len(self.queue)
        self.queue.append(cmd)
        return rv

    def _start_next(self) -> None:
        num = self.next
        cmd = self.queue[num]
        name = cmd.name
        cmd.start()
        self.current[cmd.pid] = (num, cmd)
        if self.verbosity >= 1:
            print('%-8s #%d %s' % ('START', num, name))
            if self.verbosity >= 2:
                print('%-8s #%d %s' % ('CWD', num, cmd.cwd or '.'))
                cmd_str = ' '.join(pipes.quote(a) for a in cmd.args)
                print('%-8s #%d %s' % ('COMMAND', num, cmd_str))
            sys.stdout.flush()
        elif self.verbosity >= 0:
            self._note.start(num)
        self.next += 1

    def _record_time(self, name: str, elapsed_time: float) -> None:
        # The names we use are space-separated series of rather arbitrary words.
        # They tend to start general and get more specific, so use that.
        name1 = re.sub(' .*', '', name)  # First word.
        self.times1[name1] = elapsed_time + self.times1.get(name1, 0)
        name2 = re.sub('( .*?) .*', r'\1', name)  # First two words.
        self.times2[name2] = elapsed_time + self.times2.get(name2, 0)

    def _poll_current(self) -> Tuple[int, int]:
        while True:
            time.sleep(.05)
            for pid in self.current:
                cmd = self.current[pid][1]
                code = cmd.process.poll()
                if code is not None:
                    cmd.end_time = time.time()
                    return pid, code

    def _wait_next(self) -> Tuple[List[str], int, int]:
        """Wait for a single task to finish.

        Return tuple (list of failed tasks, number test cases, number of failed tests).
        """
        pid, status = self._poll_current()
        num, cmd = self.current.pop(pid)
        name = cmd.name

        self._record_time(cmd.name, cmd.elapsed_time)

        rc = cmd.wait()
        if rc >= 0:
            msg = 'EXIT %d' % rc
        else:
            msg = 'SIG %d' % -rc
        if self.verbosity >= 1:
            print('%-8s #%d %s' % (msg, num, name))
            sys.stdout.flush()
        elif self.verbosity >= 0:
            self._note.stop(num, bool(rc))
        elif self.verbosity >= -1:
            sys.stdout.write('.' if rc == 0 else msg[0])
            num_complete = self.next - len(self.current)
            if num_complete % 50 == 0 or num_complete == len(self.queue):
                sys.stdout.write(' %d/%d\n' % (num_complete, len(self.queue)))
            elif num_complete % 10 == 0:
                sys.stdout.write(' ')
            sys.stdout.flush()

        if rc != 0:
            if name not in self.xfail:
                fail_type = 'FAILURE'
            else:
                fail_type = 'XFAIL'
        else:
            if name not in self.xfail:
                fail_type = None
            else:
                fail_type = 'UPASS'

        # Get task output.
        output = cmd.read_output()
        num_tests, num_tests_failed = parse_test_stats_from_output(output, fail_type)

        if fail_type is not None or self.verbosity >= 1:
            self._report_task_failure(fail_type, num, name, output)

        if fail_type is not None:
            failed_tasks = ['%8s %s' % (fail_type, name)]
        else:
            failed_tasks = []

        return failed_tasks, num_tests, num_tests_failed

    def _report_task_failure(self, fail_type: Optional[str], num: int, name: str,
                             output: str) -> None:
        if self.verbosity <= 0:
            sys.stdout.write('\n')
        sys.stdout.write('\n%-8s #%d %s\n\n' % (fail_type or 'PASS', num, name))
        sys.stdout.write(output + '\n')
        sys.stdout.flush()

    def run(self) -> int:
        if self.verbosity >= -1:
            print('%-8s %d' % ('PARALLEL', self.limit))
            sys.stdout.flush()
        if self.verbosity == 0:
            self._note = Noter(len(self.queue))
        print('SUMMARY  %d tasks selected' % len(self.queue))
        sys.stdout.flush()
        # Failed tasks.
        all_failures = []  # type: List[str]
        # Number of test cases. Some tasks can involve multiple test cases.
        total_tests = 0
        # Number of failed test cases.
        total_failed_tests = 0
        while self.current or self.next < len(self.queue):
            while len(self.current) < self.limit and self.next < len(self.queue):
                self._start_next()
            fails, tests, test_fails = self._wait_next()
            all_failures += fails
            total_tests += tests
            total_failed_tests += test_fails
        if self.verbosity == 0:
            self._note.clear()
        if all_failures:
            summary = 'SUMMARY  %d/%d tasks and %d/%d tests failed' % (
                len(all_failures), len(self.queue), total_failed_tests, total_tests)
            print(summary)
            for f in all_failures:
                print(f)
            print(summary)
            print('*** FAILURE ***')
            sys.stdout.flush()
            if any('XFAIL' not in f for f in all_failures):
                return 1
        else:
            print('SUMMARY  all %d tasks and %d tests passed' % (
                len(self.queue), total_tests))
            print('*** OK ***')
            sys.stdout.flush()

        return 0


def parse_test_stats_from_output(output: str, fail_type: Optional[str]) -> Tuple[int, int]:
    """Parse tasks output and determine test counts.

    Return tuple (number of tests, number of test failures). Default
    to the entire task representing a single test as a fallback.
    """

    # pytest
    m = re.search('^=+ (.*) in [0-9.]+ seconds =+\n\Z', output, re.MULTILINE)
    if m:
        counts = {}
        for part in m.group(1).split(', '):  # e.g., '3 failed, 32 passed, 345 deselected'
            count, key = part.split()
            counts[key] = int(count)
        return (sum(c for k, c in counts.items() if k != 'deselected'),
                counts.get('failed', 0))

    # myunit
    m = re.search('^([0-9]+)/([0-9]+) test cases failed(, ([0-9]+) skipped)?.$', output,
                  re.MULTILINE)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search('^([0-9]+) test cases run(, ([0-9]+) skipped)?, all passed.$', output,
                  re.MULTILINE)
    if m:
        return int(m.group(1)), 0

    # Couldn't find test counts, so fall back to single test per tasks.
    if fail_type is not None:
        return 1, 1
    else:
        return 1, 0
