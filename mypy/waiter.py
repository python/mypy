"""Parallel subprocess task runner.

This is used for running mypy tests.
"""

from typing import Dict, List, Optional, Tuple

import os
import pipes
import re
from subprocess import Popen, PIPE, STDOUT
import sys


class WaiterError(Exception):
    pass


class LazySubprocess:

    def __init__(self, name: str, args: List[str], *, cwd: Optional[str] = None,
            env: Optional[Dict[str, str]] = None) -> None:
        self.name = name
        self.args = args
        self.cwd = cwd
        self.env = env

    def __call__(self) -> Popen:
        return Popen(self.args, cwd=self.cwd, env=self.env, stdout=PIPE, stderr=STDOUT)


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
        running = ', '.join('#%d' % r for r in sorted(self.running))
        args = (self.passes, self.fails, pending, running)
        msg = 'passed %d, failed %d, pending %d; running {%s}' % args
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
        self.next = 0
        self.current = {}  # type: Dict[int, Tuple[int, Popen]]
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

    def add(self, cmd: LazySubprocess) -> int:
        rv = len(self.queue)
        self.queue.append(cmd)
        return rv

    def _start1(self) -> None:
        cmd = self.queue[self.next]
        name = cmd.name
        proc = cmd()
        num = self.next
        self.current[proc.pid] = (num, proc)
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

    def _wait_single(self) -> Tuple[List[str], int, int]:
        """Wait for a single task to finish.

        Return tuple (list of failed tasks, number test cases, number of failed tests).
        """
        pid, status = os.waitpid(-1, 0)
        num, proc = self.current.pop(pid)

        # Inlined subprocess._handle_exitstatus, it's not a public API.
        assert proc.returncode is None
        if os.WIFSIGNALED(status):
            proc.returncode = -os.WTERMSIG(status)
        elif os.WIFEXITED(status):
            proc.returncode = os.WEXITSTATUS(status)
        else:
            # Should never happen
            raise RuntimeError("Unknown child exit status!")
        assert proc.returncode is not None

        name = self.queue[num].name
        rc = proc.wait()
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

        # Get task output. Assume it's ascii to avoid unicode headaches (and portability issues).
        output = proc.stdout.read().decode('ascii')
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

    def run(self) -> None:
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
                self._start1()
            fails, tests, test_fails = self._wait_single()
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
                sys.exit(1)
        else:
            print('SUMMARY  all %d tasks and %d tests passed' % (
                len(self.queue), total_tests))
            print('*** OK ***')
            sys.stdout.flush()


def parse_test_stats_from_output(output: str, fail_type: Optional[str]) -> Tuple[int, int]:
    """Parse tasks output and determine test counts.

    Return tuple (number of tests, number of test failures). Default
    to the entire task representing a single test as a fallback.
    """
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
