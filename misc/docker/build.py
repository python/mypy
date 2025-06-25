"""Build a "mypy-test" Linux Docker container for running mypy/mypyc tests.

This allows running Linux tests under a non-Linux operating system. Mypyc
tests can also run much faster under Linux that the host OS.

NOTE: You may need to run this as root (using sudo).

Run with "--no-cache" to force reinstallation of mypy dependencies.
Run with "--pull" to force update of the Linux (Ubuntu) base image.

After you've built the container, use "run.sh" to run tests. Example:

  misc/docker/run.sh pytest mypyc/
"""

import argparse
import os
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="""Build a 'mypy-test' Docker container for running mypy/mypyc tests. You may
                       need to run this as root (using sudo)."""
    )
    parser.add_argument("--no-cache", action="store_true", help="Force rebuilding")
    parser.add_argument("--pull", action="store_true", help="Force pulling fresh Linux base image")
    args = parser.parse_args()

    dockerdir = os.path.dirname(os.path.abspath(__file__))
    dockerfile = os.path.join(dockerdir, "Dockerfile")
    rootdir = os.path.join(dockerdir, "..", "..")

    cmdline = ["docker", "build", "-t", "mypy-test", "-f", dockerfile]
    if args.no_cache:
        cmdline.append("--no-cache")
    if args.pull:
        cmdline.append("--pull")
    cmdline.append(rootdir)
    result = subprocess.run(cmdline)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
