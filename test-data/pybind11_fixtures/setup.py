# pybind11 is available at setup time due to pyproject.toml
from pybind11.setup_helpers import Pybind11Extension
from setuptools import setup

# Documentation: https://pybind11.readthedocs.io/en/stable/compiling.html
ext_modules = [
    Pybind11Extension(
        "pybind11_fixtures",
        ["src/main.cpp"],
        cxx_std=17,
    ),
]

setup(
    name="pybind11_fixtures",
    version="0.0.1",
    ext_modules=ext_modules,
)
