"""
This setup file installs packages to test mypy's PEP 561 implementation
"""

from distutils.core import setup

setup(
    name='typedpkg_ns_b-stubs',
    author="The mypy team",
    version='0.1',
    namespace_packages=['typedpkg_ns-stubs'],
    package_data={'typedpkg_ns-stubs.b': ['__init__.pyi', 'bbb.pyi']},
    packages=['typedpkg_ns-stubs.b'],
)
