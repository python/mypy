"""
This setup file installs packages to test mypy's PEP 561 implementation
"""

from setuptools import setup

setup(
    name='typedpkg-stubs',
    author="The mypy team",
    version='0.1',
    package_data={'typedpkg-stubs': ['sample.pyi', '__init__.pyi', 'py.typed']},
    packages=['typedpkg-stubs'],
)
