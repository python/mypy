#!/bin/bash
# This script is expected to be run from root of the mypy repo

# Install dependencies, demo project and mypy
python -m pip install -r test-requirements.txt
python -m pip install pybind11-mypy-demo==0.0.1
python -m pip install .

# Remove expected stubs and generate new inplace
rm -rf test-data/stubgen/pybind11_mypy_demo
stubgen -p pybind11_mypy_demo -o test-data/stubgen/

# Compare generated stubs to expected ones
git diff --exit-code test-data/stubgen/pybind11_mypy_demo
