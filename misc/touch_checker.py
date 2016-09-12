#!/usr/bin/env python3

from typing import Callable, List, Tuple, Optional

import sys
import glob
import os
import shutil
import statistics
import subprocess
import textwrap
import time


def print_offset(text: str, indent_length: int = 4) -> None:
    print()
    print(textwrap.indent(text, ' ' * indent_length))
    print()


def delete_folder(folder_path: str) -> None:
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)


def execute(command: List[str]) -> None:
    proc = subprocess.Popen(
        ' '.join(command),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=True)
    stdout_bytes, stderr_bytes = proc.communicate()  # type: Tuple[bytes, bytes]
    stdout, stderr = stdout_bytes.decode('utf-8'), stderr_bytes.decode('utf-8')
    if proc.returncode != 0:
        print('EXECUTED COMMAND:', repr(command))
        print('RETURN CODE:', proc.returncode)
        print()
        print('STDOUT:')
        print_offset(stdout)
        print('STDERR:')
        print_offset(stderr)
        print()


Command = Callable[[], None]


def test(setup: Command, command: Command, teardown: Command) -> float:
    setup()
    start = time.time()
    command()
    end = time.time() - start
    teardown()
    return end


def make_touch_wrappers(filename: str) -> Tuple[Command, Command]:
    def setup() -> None:
        execute(["touch", filename])
    def teardown() -> None:
        pass
    return setup, teardown


def make_change_wrappers(filename: str) -> Tuple[Command, Command]:
    copy = None  # type: Optional[str]

    def setup() -> None:
        nonlocal copy
        with open(filename, 'r') as stream:
            copy = stream.read()
        with open(filename, 'a') as stream:
            stream.write('\n\nfoo = 3')

    def teardown() -> None:
        assert copy is not None
        with open(filename, 'w') as stream:
            stream.write(copy)

        # Re-run to reset cache
        execute(["python3", "-m", "mypy", "-i", "mypy"]),

    return setup, teardown

def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {'touch', 'change'}:
        print("First argument should be 'touch' or 'change'")
        return

    if sys.argv[1] == 'touch':
        make_wrappers = make_touch_wrappers
        verb = "Touching"
    elif sys.argv[1] == 'change':
        make_wrappers = make_change_wrappers
        verb = "Changing"
    else:
        raise AssertionError()

    print("Setting up...")

    baseline = test(
        lambda: None,
        lambda: execute(["python3", "-m", "mypy", "mypy"]),
        lambda: None)
    print("Baseline:   {}".format(baseline))

    cold = test(
        lambda: delete_folder(".mypy_cache"),
        lambda: execute(["python3", "-m", "mypy", "-i", "mypy"]),
        lambda: None)
    print("Cold cache: {}".format(cold))

    warm = test(
        lambda: None,
        lambda: execute(["python3", "-m", "mypy", "-i", "mypy"]),
        lambda: None)
    print("Warm cache: {}".format(warm))

    print()

    deltas = []
    for filename in glob.iglob("mypy/**/*.py", recursive=True):
        print("{} {}".format(verb, filename))
        
        setup, teardown = make_wrappers(filename)
        delta = test(
            setup,
            lambda: execute(["python3", "-m", "mypy", "-i", "mypy"]),
            teardown)
        print("    Time: {}".format(delta))
        deltas.append(delta)
    print()

    print("Initial:")
    print("    Baseline:   {}".format(baseline))
    print("    Cold cache: {}".format(cold))
    print("    Warm cache: {}".format(warm))
    print()
    print("Aggregate:")
    print("    Times:      {}".format(deltas))
    print("    Mean:       {}".format(statistics.mean(deltas)))
    print("    Median:     {}".format(statistics.median(deltas)))
    print("    Stdev:      {}".format(statistics.stdev(deltas)))
    print("    Min:        {}".format(min(deltas)))
    print("    Max:        {}".format(max(deltas)))
    print("    Total:      {}".format(sum(deltas)))
    print()

if __name__ == '__main__':
    main()

