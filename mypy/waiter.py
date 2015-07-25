from typing import Dict, List, Optional, Tuple

import os
from subprocess import Popen
import sys


class WaiterError(Exception):
    pass

class LazySubprocess:

    def __init__(self, name: str, args: List[str], *, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> None:
        self.name = name
        self.args = args
        self.cwd = cwd
        self.env = env

    def __call__(self) -> Popen:
        return Popen(self.args, cwd=self.cwd, env=self.env)


class Waiter:
    """Run subprocesses in parallel and wait for them.

    Usage:

    waiter = Waiter()
    waiter.add('sleep 9')
    waiter.add('sleep 10')
    if not waiter.run():
        print('error')
    """
    def __init__(self, limit: int = 0, xfail: List[str] = []) -> None:
        self.queue = [] # type: List[LazySubprocess]
        self.next = 0
        self.current = {} # type: Dict[int, Tuple[int, Popen]]
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
        print('%-8s %d' % ('PARALLEL', limit))
        sys.stdout.flush()
        self.xfail = set(xfail)

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
        print('%-8s #%d %s' % ('START', num, name))
        sys.stdout.flush()
        self.next += 1

    def _wait1(self) -> List[str]:
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
        print('%-8s #%d %s' % (msg, num, name))
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

        if fail_type is not None:
            return ['%8s %s' % (fail_type, name)]
        else:
            return []
        print(' FAILURE %s' % name)
        sys.stdout.flush()

    def run(self) -> None:
        print('SUMMARY  %d tasks selected' % len(self.queue))
        sys.stdout.flush()
        failures = [] # type: List[str]
        while self.current or self.next < len(self.queue):
            while len(self.current) < self.limit and self.next < len(self.queue):
                self._start1()
            failures += self._wait1()
        if failures:
            print('SUMMARY  %d/%d tasks failed' % (len(failures), len(self.queue)))
            for f in failures:
                print(f)
            print('SUMMARY  %d/%d tasks failed' % (len(failures), len(self.queue)))
            sys.stdout.flush()
            if any('XFAIL' not in f for f in failures):
                sys.exit(1)
        else:
            print('SUMMARY  all %d tasks passed' % len(self.queue))
            sys.stdout.flush()
