#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
import statistics
import subprocess
import textwrap
import time
from typing import Callable


class Command:
    def __init__(self, setup: Callable[[], None], command: Callable[[], None]) -> None:
        self.setup = setup
        self.command = command


def print_offset(text: str, indent_length: int = 4) -> None:
    print()
    print(textwrap.indent(text, " " * indent_length))
    print()


def delete_folder(folder_path: str) -> None:
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)


def execute(command: list[str]) -> None:
    proc = subprocess.Popen(
        " ".join(command), stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
    )
    stdout_bytes, stderr_bytes = proc.communicate()
    stdout, stderr = stdout_bytes.decode("utf-8"), stderr_bytes.decode("utf-8")
    if proc.returncode != 0:
        print("EXECUTED COMMAND:", repr(command))
        print("RETURN CODE:", proc.returncode)
        print()
        print("STDOUT:")
        print_offset(stdout)
        print("STDERR:")
        print_offset(stderr)
        raise RuntimeError("Unexpected error from external tool.")


def trial(num_trials: int, command: Command) -> list[float]:
    trials = []
    for i in range(num_trials):
        command.setup()
        start = time.time()
        command.command()
        delta = time.time() - start
        trials.append(delta)
    return trials


def report(name: str, times: list[float]) -> None:
    print(f"{name}:")
    print(f"  Times: {times}")
    print(f"  Mean:  {statistics.mean(times)}")
    print(f"  Stdev: {statistics.stdev(times)}")
    print()


def main() -> None:
    trials = 3

    print("Testing baseline")
    baseline = trial(
        trials, Command(lambda: None, lambda: execute(["python3", "-m", "mypy", "mypy"]))
    )
    report("Baseline", baseline)

    print("Testing cold cache")
    cold_cache = trial(
        trials,
        Command(
            lambda: delete_folder(".mypy_cache"),
            lambda: execute(["python3", "-m", "mypy", "-i", "mypy"]),
        ),
    )
    report("Cold cache", cold_cache)

    print("Testing warm cache")
    execute(["python3", "-m", "mypy", "-i", "mypy"])
    warm_cache = trial(
        trials, Command(lambda: None, lambda: execute(["python3", "-m", "mypy", "-i", "mypy"]))
    )
    report("Warm cache", warm_cache)


if __name__ == "__main__":
    main()
