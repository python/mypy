#!/bin/bash

set -e
set -x

cd "$(dirname $0)/.."

# Install dependencies, demo project and mypy
python -m pip install -r test-requirements.txt
python -m pip install ./test-data/pybind11_mypy_demo
python -m pip install .

# Remove expected stubs and generate new inplace
STUBGEN_OUTPUT_FOLDER=./test-data/pybind11_mypy_demo/stubgen
rm -rf $STUBGEN_OUTPUT_FOLDER/*
stubgen -p pybind11_mypy_demo -o $STUBGEN_OUTPUT_FOLDER

# Compare generated stubs to expected ones
git diff --exit-code $STUBGEN_OUTPUT_FOLDER
