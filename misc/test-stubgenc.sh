#!/bin/bash

set -e
set -x

cd "$(dirname "$0")/.."

# Install dependencies, demo project and mypy
python -m pip install -r test-requirements.txt
python -m pip install ./test-data/pybind11_mypy_demo
python -m pip install .

EXIT=0

# performs the stubgenc test
# first argument is the test result folder
# everything else is passed to stubgen as its arguments
function stubgenc_test() {
    # Remove expected stubs and generate new inplace
    STUBGEN_OUTPUT_FOLDER=./test-data/pybind11_mypy_demo/$1
    rm -rf "${STUBGEN_OUTPUT_FOLDER:?}/*"
    stubgen -o "$STUBGEN_OUTPUT_FOLDER" "${@:2}"

    # Compare generated stubs to expected ones
    if ! git diff --exit-code "$STUBGEN_OUTPUT_FOLDER";
    then
        EXIT=$?
    fi
}

# create stubs without docstrings
stubgenc_test stubgen -p pybind11_mypy_demo
# create stubs with docstrings
stubgenc_test stubgen-include-docs -p pybind11_mypy_demo --include-docstrings
exit $EXIT
