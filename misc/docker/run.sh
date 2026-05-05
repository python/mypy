#!/bin/bash
# Run mypy or mypyc tests in a Docker container that was built using misc/docker/build.py.
#
# Usage: misc/docker/run.sh <command> <arg>...
#
# For example, run mypyc tests like this:
#
#   misc/docker/run.sh pytest mypyc
#
# NOTE: You may need to run this as root (using sudo).

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)
MYPY_DIR="$SCRIPT_DIR/../.."

docker run -ti --rm -v "$MYPY_DIR:/repo" mypy-test /repo/misc/docker/run-wrapper.sh "$@"
