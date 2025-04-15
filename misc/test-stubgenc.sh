#!/bin/bash

set -e
set -x

cd "$(dirname "$0")/.."

# Install dependencies, demo project and mypy
python -m pip install -r test-requirements.txt
python -m pip install ./test-data/pybind11_fixtures
python -m pip install .

EXIT=0

# performs the stubgenc test
# first argument is the test result folder
# everything else is passed to stubgen as its arguments
function stubgenc_test() {
    # Remove expected stubs and generate new inplace
    STUBGEN_OUTPUT_FOLDER=./test-data/pybind11_fixtures/$1
    rm -rf "${STUBGEN_OUTPUT_FOLDER:?}"

    stubgen -o "$STUBGEN_OUTPUT_FOLDER" "${@:2}"

    # Check if generated stubs can actually be type checked by mypy
    if ! mypy "$STUBGEN_OUTPUT_FOLDER";
    then
        echo "Stubgen test failed, because generated stubs failed to type check."
        EXIT=1
    fi

    # Compare generated stubs to expected ones
    if ! git diff --exit-code "$STUBGEN_OUTPUT_FOLDER";
    then
        echo "Stubgen test failed, because generated stubs differ from expected outputs."
        EXIT=1
    fi
}

# create stubs without docstrings
stubgenc_test expected_stubs_no_docs -p pybind11_fixtures
# create stubs with docstrings
stubgenc_test expected_stubs_with_docs -p pybind11_fixtures --include-docstrings

exit $EXIT
