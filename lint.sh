#!/bin/bash

# Run the flake8 linter against the implementation.
#
# Note that stubs are not checked; we'd need a separate set of
# settings for stubs, as they follow a different set of conventions.

SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
cd "$SCRIPT_DIR"

flake8 *.py mypy scripts/mypy
