"""
This setup file install packages to test mypy's PEP 561 implementation
"""

from distutils.core import setup

setup(
    name='typedpkg_stubs',
    author="The mypy team",
    version='0.1',
    package_data={'typedpkg_stubs': ['py.typed', 'sample.pyi', '__init__.pyi']},
    packages=['typedpkg_stubs'],
)